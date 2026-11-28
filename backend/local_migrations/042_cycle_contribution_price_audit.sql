-- FR CAIXINHA AI STUDIO M20400 / migration 042.
-- Verified tenant-admin session is required; no direct financial settlement.
-- Local PG18 only; CI on disposable frcaixinha_ci only.
DO $guard$
BEGIN
 IF NOT (
  (current_database()='frcaixinha_aistudio_dev'
   AND current_user='frc_ai_owner' AND session_user='frc_ai_owner'
   AND inet_server_port()=5433
   AND current_setting('data_directory')=
    '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
   AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999)
  OR
  (current_database()='frcaixinha_ci'
   AND session_user='postgres'
   AND current_setting('is_superuser')='on'
   AND current_setting('frcaixinha.cycle_price_local_ci',true)='1')
 ) THEN RAISE EXCEPTION 'M20400: local 042 is not authorized on this cluster'; END IF;
 IF to_regclass('public.notification_inbox') IS NULL
 OR to_regclass('public.member_lifecycle_requests') IS NULL
 OR to_regclass('public.local_m041_notification_outbox') IS NULL
 THEN RAISE EXCEPTION 'M20400 requires M031/M19300/M20100 prior local schema'; END IF;
END $guard$;

CREATE TABLE public.cycle_contribution_price_audit (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 cycle_id uuid NOT NULL REFERENCES public.cycles(id) ON DELETE RESTRICT,
 policy_id uuid NOT NULL REFERENCES public.policies(id) ON DELETE RESTRICT,
 actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 idempotency_key uuid NOT NULL,
 old_price_cents bigint NOT NULL CHECK(old_price_cents>0),
 requested_price_cents bigint NOT NULL
   CHECK(requested_price_cents BETWEEN 100 AND 1000000),
 change_status varchar(24) NOT NULL CHECK(change_status IN('APPLIED','PENDING_REVIEW')),
 reason varchar(500) NOT NULL CHECK(length(btrim(reason)) BETWEEN 12 AND 500),
 occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,idempotency_key),
 CHECK(old_price_cents<>requested_price_cents)
);
CREATE INDEX cycle_contribution_price_audit_lookup
 ON public.cycle_contribution_price_audit(tenant_id,cycle_id,occurred_at DESC);
ALTER TABLE public.cycle_contribution_price_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cycle_contribution_price_audit FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.cycle_contribution_price_audit
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT SELECT ON public.cycle_contribution_price_audit TO frcaixinha_app_role;
CREATE POLICY cycle_contribution_price_audit_admin_read
 ON public.cycle_contribution_price_audit FOR SELECT TO frcaixinha_app_role
 USING (
 tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND public.rls_is_tenant_admin(
  NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id)
);

CREATE FUNCTION public.cycle_price_audit_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 RAISE EXCEPTION 'M20400: policy price audit is append-only';
END $fn$;
REVOKE ALL ON FUNCTION public.cycle_price_audit_immutable() FROM PUBLIC;
CREATE TRIGGER cycle_price_immutable_row
 BEFORE UPDATE OR DELETE ON public.cycle_contribution_price_audit
 FOR EACH ROW EXECUTE FUNCTION public.cycle_price_audit_immutable();
CREATE TRIGGER cycle_price_immutable_truncate
 BEFORE TRUNCATE ON public.cycle_contribution_price_audit
 FOR EACH STATEMENT EXECUTE FUNCTION public.cycle_price_audit_immutable();

CREATE FUNCTION public.cycle_price_admin_actor(
 p_raw_token text,p_tenant uuid
) RETURNS uuid
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE v_actor uuid;
BEGIN
 IF p_raw_token IS NULL OR length(p_raw_token) NOT BETWEEN 32 AND 512
 OR p_tenant IS NULL THEN
  RAISE EXCEPTION 'M20400: invalid admin authorization' USING ERRCODE='42501';
 END IF;
 SELECT s.user_id INTO v_actor
 FROM public.sessions s
 JOIN public.users u ON u.id=s.user_id AND u.status='ACTIVE'
 JOIN public.tenants t ON t.id=p_tenant
   AND t.status='ATIVO' AND t.admin_user_id=s.user_id
 JOIN public.memberships m ON m.tenant_id=t.id
   AND m.user_id=s.user_id AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 WHERE s.token_hash=encode(public.digest(p_raw_token,'sha256'),'hex')
 AND s.active_role='TENANT_ADMIN' AND s.active_tenant_id=p_tenant
 AND s.revoked_at IS NULL AND s.expires_at>clock_timestamp();
 IF v_actor IS NULL THEN
  RAISE EXCEPTION 'M20400: invalid admin authorization' USING ERRCODE='42501';
 END IF;
 RETURN v_actor;
END $fn$;
REVOKE ALL ON FUNCTION public.cycle_price_admin_actor(text,uuid)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;

CREATE FUNCTION public.cycle_price_status(p_raw_token text,p_tenant uuid)
RETURNS TABLE (
 tenant_id uuid,cycle_id uuid,cycle_year integer,
 start_date date,end_date date,
 amount_cents bigint,policy_version integer,
 registered_contributions bigint,can_edit boolean,blocked_reason text,
 pending_requested_cents bigint
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 v_actor uuid; v_cycle record; v_policy record; v_count bigint; v_amount bigint;
BEGIN
 v_actor:=public.cycle_price_admin_actor(p_raw_token,p_tenant);
 SELECT c.id,c.year,c.start_date,c.end_date,c.status INTO v_cycle
 FROM public.cycles c
 WHERE c.tenant_id=p_tenant AND c.status='ABERTO'
 ORDER BY c.start_date DESC LIMIT 1;
 IF NOT FOUND THEN RETURN; END IF;
 SELECT p.id,p.version,p.contribution_per_quota INTO v_policy
 FROM public.policies p WHERE p.tenant_id=p_tenant
 AND p.cycle_id=v_cycle.id AND p.status='ACTIVE';
 IF NOT FOUND OR
 (SELECT count(*) FROM public.policies p WHERE p.tenant_id=p_tenant
 AND p.cycle_id=v_cycle.id AND p.status='ACTIVE')<>1
 THEN RAISE EXCEPTION 'M20400: ambiguous active policy'; END IF;
 SELECT count(*) INTO v_count FROM public.contributions
 WHERE contributions.tenant_id=p_tenant AND contributions.cycle_id=v_cycle.id;
 v_amount:=(v_policy.contribution_per_quota*100)::bigint;
 RETURN QUERY SELECT
 p_tenant,v_cycle.id,v_cycle.year,v_cycle.start_date,v_cycle.end_date,
 v_amount,v_policy.version,v_count,
 (v_cycle.start_date>=current_date AND v_count=0),
 CASE WHEN v_count>0 THEN 'COMPETENCIAS_JA_REGISTRADAS'
      WHEN v_cycle.start_date<current_date THEN 'CICLO_JA_INICIADO'
      ELSE 'EDITAVEL_ANTES_DA_PRIMEIRA_COMPETENCIA' END::text,
 (SELECT a.requested_price_cents
  FROM public.cycle_contribution_price_audit a
  WHERE a.tenant_id=p_tenant AND a.cycle_id=v_cycle.id
   AND a.change_status='PENDING_REVIEW'
  ORDER BY a.occurred_at DESC,a.id DESC LIMIT 1);
END $fn$;
REVOKE ALL ON FUNCTION public.cycle_price_status(text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.cycle_price_status(text,uuid)
 TO frcaixinha_app_role;

CREATE FUNCTION public.cycle_price_change(
 p_raw_token text,p_tenant uuid,p_cycle uuid,p_amount_cents bigint,
 p_reason text,p_idempotency uuid
)
RETURNS TABLE (change_status text,amount_cents bigint,request_id uuid)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE v_actor uuid;v_cycle record;v_policy record;v_old bigint;
 v_existing record;v_audit uuid;v_status varchar(24);
BEGIN
 v_actor:=public.cycle_price_admin_actor(p_raw_token,p_tenant);
 IF p_cycle IS NULL OR p_idempotency IS NULL
 OR p_amount_cents NOT BETWEEN 100 AND 1000000
 OR p_reason IS NULL OR length(btrim(p_reason)) NOT BETWEEN 12 AND 500
 THEN RAISE EXCEPTION 'M20400: invalid price change request'; END IF;
 SELECT c.id,c.start_date,c.status INTO v_cycle
 FROM public.cycles c WHERE c.tenant_id=p_tenant AND c.id=p_cycle
 FOR UPDATE;
 IF NOT FOUND OR v_cycle.status<>'ABERTO' THEN
  RAISE EXCEPTION 'M20400: cycle unavailable'; END IF;
 SELECT p.id,p.version,p.contribution_per_quota INTO v_policy
 FROM public.policies p WHERE p.tenant_id=p_tenant AND p.cycle_id=p_cycle
 AND p.status='ACTIVE' FOR UPDATE;
 IF NOT FOUND OR (SELECT count(*) FROM public.policies p
   WHERE p.tenant_id=p_tenant AND p.cycle_id=p_cycle AND p.status='ACTIVE')<>1
 THEN RAISE EXCEPTION 'M20400: active policy mismatch'; END IF;
 v_old:=(v_policy.contribution_per_quota*100)::bigint;
 SELECT a.id,a.actor_user_id,a.requested_price_cents,a.change_status
 INTO v_existing
 FROM public.cycle_contribution_price_audit a
 WHERE a.tenant_id=p_tenant AND a.idempotency_key=p_idempotency;
 IF FOUND THEN
  IF v_existing.actor_user_id<>v_actor OR v_existing.requested_price_cents<>p_amount_cents
  THEN RAISE EXCEPTION 'M20400: idempotency conflict'; END IF;
  RETURN QUERY SELECT v_existing.change_status::text,
    (SELECT (p.contribution_per_quota*100)::bigint FROM public.policies p
     WHERE p.id=v_policy.id),v_existing.id;
  RETURN;
 END IF;
 IF v_old=p_amount_cents THEN
  RAISE EXCEPTION 'M20400: no price change'; END IF;
 IF v_cycle.start_date<current_date OR EXISTS (
  SELECT 1 FROM public.contributions c WHERE c.tenant_id=p_tenant
   AND c.cycle_id=p_cycle
 ) THEN
  v_status:='PENDING_REVIEW';
 ELSE
  v_status:='APPLIED';
  UPDATE public.policies SET
   contribution_per_quota=(p_amount_cents::numeric/100),
   version=version+1
  WHERE id=v_policy.id AND tenant_id=p_tenant AND cycle_id=p_cycle
  AND status='ACTIVE';
 END IF;
 INSERT INTO public.cycle_contribution_price_audit
 (tenant_id,cycle_id,policy_id,actor_user_id,idempotency_key,
  old_price_cents,requested_price_cents,change_status,reason)
 VALUES (p_tenant,p_cycle,v_policy.id,v_actor,p_idempotency,
  v_old,p_amount_cents,v_status,btrim(p_reason))
 RETURNING id INTO v_audit;
 RETURN QUERY SELECT v_status::text,
  (CASE WHEN v_status='APPLIED' THEN p_amount_cents ELSE v_old END),v_audit;
END $fn$;
REVOKE ALL ON FUNCTION public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)
 FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)
 TO frcaixinha_app_role;

DO $postguard$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_class WHERE oid=
   'public.cycle_contribution_price_audit'::regclass
   AND relrowsecurity AND relforcerowsecurity)
 OR has_table_privilege('frcaixinha_app_role','public.cycle_contribution_price_audit','INSERT')
 OR has_table_privilege('frcaixinha_auth_role','public.cycle_contribution_price_audit','SELECT')
 OR NOT has_function_privilege('frcaixinha_app_role',
  'public.cycle_price_status(text,uuid)','EXECUTE')
 OR NOT has_function_privilege('frcaixinha_app_role',
  'public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)','EXECUTE')
 OR has_function_privilege('frcaixinha_app_role',
  'public.cycle_price_admin_actor(text,uuid)','EXECUTE')
 THEN RAISE EXCEPTION 'M20400: unsafe audit policy permission'; END IF;
END $postguard$;
