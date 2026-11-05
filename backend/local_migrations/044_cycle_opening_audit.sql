-- AI Studio M21000: 044. Dedicated, explicit, authenticated cycle creation.
-- No contribution, ledger, Pix, payout, settlement or historic price mutation.
DO $guard$ BEGIN
 IF NOT (
  (current_database()='frcaixinha_aistudio_dev'
   AND current_user='frc_ai_owner' AND session_user='frc_ai_owner'
   AND inet_server_port()=5433
   AND current_setting('data_directory')='/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
   AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999)
  OR (current_database()='frcaixinha_ci'
    AND session_user='postgres' AND current_setting('is_superuser')='on'
    AND current_setting('frcaixinha.cycle_open_local_ci',true)='1')
 ) THEN RAISE EXCEPTION 'M21000 WRONG_ENVIRONMENT'; END IF;
 IF (SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public')<>45
 OR to_regclass('public.cycle_contribution_price_audit') IS NULL
 OR to_regclass('public.cycle_opening_audit') IS NOT NULL
 OR to_regprocedure('public.cycle_price_admin_actor(text,uuid)') IS NULL
 OR to_regprocedure('public.cycle_price_change_legacy_m20400(text,uuid,uuid,bigint,text,uuid)') IS NULL
 OR (SELECT count(*) FROM pg_constraint WHERE conname IN
  ('policy_minimum_150_new','quota_minimum_150_new') AND NOT convalidated)<>2
 THEN RAISE EXCEPTION 'M21000 M042/M043_REQUIRED'; END IF;
END $guard$;

CREATE TABLE public.cycle_opening_audit(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 cycle_id uuid NOT NULL UNIQUE REFERENCES public.cycles(id) ON DELETE RESTRICT,
 policy_id uuid NOT NULL UNIQUE REFERENCES public.policies(id) ON DELETE RESTRICT,
 actor_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 cycle_year integer NOT NULL CHECK(cycle_year BETWEEN 2027 AND 2100),
 amount_cents bigint NOT NULL CHECK(amount_cents BETWEEN 15000 AND 1000000),
 idempotency_key uuid NOT NULL,
 reason varchar(500) NOT NULL CHECK(length(btrim(reason)) BETWEEN 12 AND 500),
 occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,idempotency_key),UNIQUE(tenant_id,cycle_year)
);
CREATE INDEX cycle_opening_recent ON public.cycle_opening_audit(tenant_id,occurred_at DESC);
ALTER TABLE public.cycle_opening_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cycle_opening_audit FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.cycle_opening_audit
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT SELECT ON public.cycle_opening_audit TO frcaixinha_app_role;
CREATE POLICY cycle_opening_admin_read ON public.cycle_opening_audit
 FOR SELECT TO frcaixinha_app_role USING (
 tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
 AND current_setting('app.current_role',true)='TENANT_ADMIN'
 AND public.rls_is_tenant_admin(
 NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id));
CREATE FUNCTION public.cycle_opening_immutable() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $body$
BEGIN RAISE EXCEPTION 'M21000 IMMUTABLE_AUDIT'; END $body$;
REVOKE ALL ON FUNCTION public.cycle_opening_immutable() FROM PUBLIC;
CREATE TRIGGER cycle_opening_immutable_row BEFORE UPDATE OR DELETE
 ON public.cycle_opening_audit FOR EACH ROW
 EXECUTE FUNCTION public.cycle_opening_immutable();
CREATE TRIGGER cycle_opening_immutable_truncate BEFORE TRUNCATE
 ON public.cycle_opening_audit FOR EACH STATEMENT
 EXECUTE FUNCTION public.cycle_opening_immutable();

CREATE FUNCTION public.cycle_open_create(
 p_token text,p_tenant uuid,p_year integer,p_amount_cents bigint,
 p_reason text,p_idempotency uuid
) RETURNS TABLE(opened_cycle_id uuid,opened_policy_id uuid,
 opened_year integer,opened_amount_cents bigint,opening_status text)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE v_actor uuid;v_prior record;v_cycle uuid;v_policy uuid;
BEGIN
 v_actor:=public.cycle_price_admin_actor(p_token,p_tenant);
 IF p_year IS NULL OR p_year NOT BETWEEN 2027 AND 2100
 OR p_amount_cents IS NULL OR p_amount_cents NOT BETWEEN 15000 AND 1000000
 OR p_idempotency IS NULL OR p_reason IS NULL
 OR length(btrim(p_reason)) NOT BETWEEN 12 AND 500
 THEN RAISE EXCEPTION 'M21000 INVALID_OPENING' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM public.tenants t WHERE t.id=p_tenant AND t.status='ATIVO' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'M21000 TENANT_NOT_ACTIVE' USING ERRCODE='42501'; END IF;
 SELECT a.cycle_id,a.policy_id,a.cycle_year,a.amount_cents,a.actor_user_id,a.reason
 INTO v_prior FROM public.cycle_opening_audit a
 WHERE a.tenant_id=p_tenant AND a.idempotency_key=p_idempotency;
 IF FOUND THEN
  IF v_prior.actor_user_id<>v_actor OR v_prior.cycle_year<>p_year
  OR v_prior.amount_cents<>p_amount_cents OR v_prior.reason<>btrim(p_reason)
  THEN RAISE EXCEPTION 'M21000 IDEMPOTENCY_CONFLICT' USING ERRCODE='23505'; END IF;
  RETURN QUERY SELECT v_prior.cycle_id,v_prior.policy_id,v_prior.cycle_year,
     v_prior.amount_cents,'REPLAY'::text;
  RETURN;
 END IF;
 IF make_date(p_year,1,1)<=current_date
 THEN RAISE EXCEPTION 'M21000 YEAR_NOT_FUTURE' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM public.cycles c WHERE c.tenant_id=p_tenant AND c.year=p_year)
 THEN RAISE EXCEPTION 'M21000 YEAR_ALREADY_EXISTS' USING ERRCODE='23505'; END IF;
 IF EXISTS(SELECT 1 FROM public.cycles c
           WHERE c.tenant_id=p_tenant AND c.status<>'LIQUIDADO')
 THEN RAISE EXCEPTION 'M21000 PREVIOUS_CYCLE_OPEN' USING ERRCODE='42501'; END IF;
 INSERT INTO public.cycles(tenant_id,year,start_date,end_date,settlement_date,status)
 VALUES(p_tenant,p_year,make_date(p_year,1,1),make_date(p_year,12,31),
        make_date(p_year+1,1,10),'ABERTO') RETURNING id INTO v_cycle;
 INSERT INTO public.policies(tenant_id,cycle_id,version,contribution_per_quota,status)
 VALUES(p_tenant,v_cycle,1,p_amount_cents::numeric/100,'ACTIVE')
 RETURNING id INTO v_policy;
 INSERT INTO public.cycle_opening_audit(
 tenant_id,cycle_id,policy_id,actor_user_id,cycle_year,amount_cents,idempotency_key,reason)
 VALUES(p_tenant,v_cycle,v_policy,v_actor,p_year,p_amount_cents,p_idempotency,btrim(p_reason));
 RETURN QUERY SELECT v_cycle,v_policy,p_year,p_amount_cents,'CREATED'::text;
END $fn$;
REVOKE ALL ON FUNCTION public.cycle_open_create(text,uuid,integer,bigint,text,uuid)
 FROM PUBLIC,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.cycle_open_create(text,uuid,integer,bigint,text,uuid)
 TO frcaixinha_app_role;
DO $post$ BEGIN
 IF NOT EXISTS(SELECT 1 FROM pg_class WHERE oid='public.cycle_opening_audit'::regclass
 AND relrowsecurity AND relforcerowsecurity)
 OR (SELECT count(*) FROM pg_trigger WHERE
 tgname IN('cycle_opening_immutable_row','cycle_opening_immutable_truncate') AND tgenabled='O')<>2
 OR has_table_privilege('frcaixinha_app_role','public.cycle_opening_audit','INSERT')
 OR has_table_privilege('frcaixinha_auth_role','public.cycle_opening_audit','SELECT')
 OR NOT has_function_privilege('frcaixinha_app_role',
 'public.cycle_open_create(text,uuid,integer,bigint,text,uuid)','EXECUTE')
 OR has_function_privilege('frcaixinha_auth_role',
 'public.cycle_open_create(text,uuid,integer,bigint,text,uuid)','EXECUTE')
 THEN RAISE EXCEPTION 'M21000 UNSAFE_GRANTS'; END IF;
END $post$;
