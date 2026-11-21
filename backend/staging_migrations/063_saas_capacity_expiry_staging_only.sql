-- M32900-M33300: recover stale unclaimed capacity holds, disposable CI only.
-- NEVER apply to Termux 5433, OCI, staging real or production.
-- All writes are restricted to synthetic CI history tables.
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
 OR current_setting('is_superuser')<>'on'
 OR current_setting('frcaixinha.saas_expiry_ci',true) IS DISTINCT FROM '1'
 OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_capacity_ci'
   AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M32900_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.saas_capacity_expiry_events_staging(
 request_id uuid PRIMARY KEY,
 hold_event_id uuid NOT NULL UNIQUE REFERENCES public.saas_capacity_events_staging(event_id) ON DELETE RESTRICT,
 release_event_id uuid NOT NULL UNIQUE REFERENCES public.saas_capacity_events_staging(event_id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 admin_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 recovered_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 ci_only boolean NOT NULL DEFAULT true CHECK(ci_only),
 real_member_created boolean NOT NULL DEFAULT false CHECK(NOT real_member_created),
 real_quota_created boolean NOT NULL DEFAULT false CHECK(NOT real_quota_created),
 real_charge_created boolean NOT NULL DEFAULT false CHECK(NOT real_charge_created),
 real_ledger_changed boolean NOT NULL DEFAULT false CHECK(NOT real_ledger_changed)
);
CREATE INDEX saas_expiry_tenant_idx_ci ON public.saas_capacity_expiry_events_staging(tenant_id,recovered_at DESC);
ALTER TABLE public.saas_capacity_expiry_events_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_capacity_expiry_events_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_capacity_expiry_events_staging FROM PUBLIC,frcaixinha_app_role,
 frcaixinha_auth_role,frcaixinha_saas_capacity_ci,frcaixinha_saas_claim_ci;

CREATE FUNCTION public.saas_capacity_expire_ci(
 p_request uuid,p_tenant uuid,p_admin uuid,p_hold uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE locked_tenant uuid; prior record; held record; released jsonb; new_release uuid;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_capacity_ci'
 OR current_setting('frcaixinha.saas_capacity_ci',true) IS DISTINCT FROM '1'
 OR current_setting('frcaixinha.saas_expiry_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M32900_CI_WORKER_DENIED'; END IF;
 IF p_request IS NULL OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 OR p_tenant IS NULL OR p_admin IS NULL OR p_hold IS NULL
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;

 -- Same tenant lock as HOLD, RELEASE and CLAIM. No TOCTOU release.
 SELECT t.id INTO locked_tenant FROM public.tenants t WHERE t.id=p_tenant FOR UPDATE;
 IF NOT FOUND OR NOT public.saas_capacity_actor_ci(p_tenant,p_admin)
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;

 SELECT * INTO prior FROM public.saas_capacity_expiry_events_staging
 WHERE request_id=p_request FOR UPDATE;
 IF FOUND THEN
   IF prior.tenant_id=p_tenant AND prior.admin_user_id=p_admin
   AND prior.hold_event_id=p_hold
   THEN RETURN jsonb_build_object('state','REPLAY_RECOVERY_CI',
      'real_authorized',false); END IF;
   RETURN jsonb_build_object('state','REQUEST_COLLISION_DENIED','real_authorized',false);
 END IF;

 SELECT * INTO held FROM public.saas_capacity_events_staging h
 WHERE h.event_id=p_hold AND h.tenant_id=p_tenant AND h.admin_user_id=p_admin
 AND h.action='HOLD' FOR UPDATE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','INVALID_HOLD','real_authorized',false); END IF;
 IF held.created_at>clock_timestamp()-interval '60 minutes'
 THEN RETURN jsonb_build_object('state','TOO_EARLY','real_authorized',false); END IF;
 IF EXISTS(SELECT 1 FROM public.saas_capacity_claims_staging c
  WHERE c.hold_event_id=p_hold)
 THEN RETURN jsonb_build_object('state','CLAIMED_HOLD_DENIED','real_authorized',false); END IF;
 IF EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r
  WHERE r.action='RELEASE' AND r.related_hold_event_id=p_hold)
 THEN RETURN jsonb_build_object('state','ALREADY_RELEASED_DENIED','real_authorized',false); END IF;
 IF EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r WHERE r.request_id=p_request)
 THEN RETURN jsonb_build_object('state','REQUEST_COLLISION_DENIED','real_authorized',false); END IF;

 -- Existing CI release function rechecks authorization and claimed-hold trigger.
 -- Any failure rolls back BOTH release and recovery evidence atomically.
 released:=public.saas_capacity_release_ci(p_request,p_tenant,p_admin,p_hold);
 IF released->>'state'<>'RELEASED_CI'
 THEN RETURN jsonb_build_object('state','RELEASE_DENIED','real_authorized',false); END IF;
 new_release:=(released->>'event_id')::uuid;
 INSERT INTO public.saas_capacity_expiry_events_staging
 (request_id,hold_event_id,release_event_id,tenant_id,admin_user_id)
 VALUES(p_request,p_hold,new_release,p_tenant,p_admin);
 RETURN jsonb_build_object('state','RECOVERED_CI_NO_REAL_CREATION',
 'real_authorized',false,'real_member_created',false,'real_quota_created',false,
 'real_charge_created',false,'real_ledger_changed',false);
END $fn$;

CREATE FUNCTION public.saas_expiry_immutable_ci() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN RAISE EXCEPTION 'M33200_EXPIRY_HISTORY_IMMUTABLE'; END $fn$;
CREATE TRIGGER saas_expiry_no_update_delete_ci BEFORE UPDATE OR DELETE
 ON public.saas_capacity_expiry_events_staging FOR EACH ROW
 EXECUTE FUNCTION public.saas_expiry_immutable_ci();
CREATE TRIGGER saas_expiry_no_truncate_ci BEFORE TRUNCATE
 ON public.saas_capacity_expiry_events_staging FOR EACH STATEMENT
 EXECUTE FUNCTION public.saas_expiry_immutable_ci();
REVOKE ALL ON FUNCTION public.saas_capacity_expire_ci(uuid,uuid,uuid,uuid),
 public.saas_expiry_immutable_ci() FROM PUBLIC,frcaixinha_app_role,
 frcaixinha_auth_role,frcaixinha_saas_capacity_ci,frcaixinha_saas_claim_ci;
GRANT EXECUTE ON FUNCTION public.saas_capacity_expire_ci(uuid,uuid,uuid,uuid)
 TO frcaixinha_saas_capacity_ci;
COMMIT;
