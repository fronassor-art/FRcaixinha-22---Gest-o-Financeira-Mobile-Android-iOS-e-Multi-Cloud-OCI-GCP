-- M30400-30800: append-only annual consent in DISPOSABLE CI, never production.
BEGIN;
DO $g$ BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
    OR current_setting('is_superuser')<>'on'
    OR current_setting('frcaixinha.annual_ci',true) IS DISTINCT FROM '1'
    OR NOT EXISTS (SELECT 1 FROM pg_roles
       WHERE rolname='frcaixinha_annual_ci' AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'M30400_DISPOSABLE_CI_ONLY'; END IF;
END $g$;
CREATE TABLE public.annual_self_loan_events_staging (
 seq bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 request_id uuid NOT NULL UNIQUE,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 cycle_year integer NOT NULL CHECK(cycle_year BETWEEN 2026 AND 2100),
 admin_id uuid NOT NULL REFERENCES public.users(id),
 membership_id uuid NOT NULL REFERENCES public.memberships(id),
 actor_id uuid NOT NULL REFERENCES public.users(id),
 terms_sha char(64) NOT NULL CHECK(terms_sha ~ '^[0-9a-f]{64}$'),
 decision varchar(8) NOT NULL CHECK(decision IN ('SIGNED','REVOKED')),
 evidence_sha char(64) NOT NULL CHECK(evidence_sha ~ '^[0-9a-f]{64}$'),
 occurred_at timestamptz NOT NULL,
 provider_verified boolean NOT NULL DEFAULT false CHECK(NOT provider_verified),
 payout_authorized boolean NOT NULL DEFAULT false CHECK(NOT payout_authorized)
);
CREATE INDEX annual_events_lookup_ci ON public.annual_self_loan_events_staging
(tenant_id,cycle_year,admin_id,terms_sha,membership_id,seq DESC);
ALTER TABLE public.annual_self_loan_events_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.annual_self_loan_events_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.annual_self_loan_events_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_annual_ci;
REVOKE ALL ON SEQUENCE public.annual_self_loan_events_staging_seq_seq
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_annual_ci;
CREATE FUNCTION public.annual_event_record_ci(
 p_request uuid,p_tenant uuid,p_year integer,p_admin uuid,p_membership uuid,
 p_actor uuid,p_terms varchar,p_decision varchar,p_digest varchar,p_at timestamptz
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $f$
DECLARE t record; member_user uuid; prior record;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_annual_ci'
 OR current_setting('frcaixinha.annual_ci',true) IS DISTINCT FROM '1'
 OR p_request IS NULL OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 OR p_tenant IS NULL OR p_admin IS NULL OR p_membership IS NULL OR p_actor IS NULL
 OR p_year IS NULL OR p_year NOT BETWEEN 2026 AND 2100
 OR p_terms IS NULL OR p_terms !~ '^[0-9a-f]{64}$'
 OR p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
 OR p_decision IS NULL OR p_decision NOT IN ('SIGNED','REVOKED')
 OR p_at IS NULL
 OR extract(year from p_at AT TIME ZONE 'America/Belem')::int<>p_year
 THEN RETURN 'DENIED'; END IF;
 SELECT status,admin_user_id INTO t FROM public.tenants
   WHERE id=p_tenant FOR UPDATE;
 IF NOT FOUND OR t.status<>'ATIVO' OR t.admin_user_id<>p_admin
 OR NOT EXISTS(SELECT 1 FROM public.memberships
   WHERE tenant_id=p_tenant AND user_id=p_admin
     AND role='TENANT_ADMIN' AND status='ATIVA')
 THEN RETURN 'DENIED'; END IF;
 SELECT user_id INTO member_user FROM public.memberships
 WHERE id=p_membership AND tenant_id=p_tenant AND role='TENANT_MEMBER'
   AND status='ATIVA' FOR UPDATE;
 IF NOT FOUND OR member_user<>p_actor OR member_user=p_admin
 THEN RETURN 'DENIED'; END IF;
 SELECT * INTO prior FROM public.annual_self_loan_events_staging
 WHERE request_id=p_request FOR UPDATE;
 IF FOUND THEN
  IF prior.tenant_id=p_tenant AND prior.cycle_year=p_year
   AND prior.admin_id=p_admin AND prior.membership_id=p_membership
   AND prior.actor_id=p_actor AND prior.terms_sha=p_terms
   AND prior.decision=p_decision AND prior.evidence_sha=p_digest
   AND prior.occurred_at=p_at THEN RETURN 'REPLAY_CI'; END IF;
  RETURN 'DENIED';
 END IF;
 INSERT INTO public.annual_self_loan_events_staging
 (request_id,tenant_id,cycle_year,admin_id,membership_id,actor_id,
 terms_sha,decision,evidence_sha,occurred_at)
 VALUES (p_request,p_tenant,p_year,p_admin,p_membership,p_actor,
 p_terms,p_decision,p_digest,p_at);
 RETURN 'RECORDED_CI_NOT_AUTHORIZED';
END $f$;
CREATE FUNCTION public.annual_event_review_ci(
 p_tenant uuid,p_year integer,p_admin uuid,p_terms varchar,p_at timestamptz
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $f$
DECLARE t record; needed int; signed int;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_annual_ci'
 OR current_setting('frcaixinha.annual_ci',true) IS DISTINCT FROM '1'
 OR p_tenant IS NULL OR p_admin IS NULL
 OR p_year IS NULL OR p_year NOT BETWEEN 2026 AND 2100
 OR p_terms IS NULL OR p_terms !~ '^[0-9a-f]{64}$'
 OR p_at IS NULL
 OR extract(year from p_at AT TIME ZONE 'America/Belem')::int<>p_year
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;
 SELECT status,admin_user_id INTO t FROM public.tenants WHERE id=p_tenant FOR UPDATE;
 IF NOT FOUND OR t.status<>'ATIVO' OR t.admin_user_id<>p_admin
 OR NOT EXISTS(SELECT 1 FROM public.memberships WHERE tenant_id=p_tenant
   AND user_id=p_admin AND role='TENANT_ADMIN' AND status='ATIVA')
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;
 SELECT count(*) INTO needed FROM public.memberships m
 WHERE m.tenant_id=p_tenant AND m.role='TENANT_MEMBER'
 AND m.status='ATIVA' AND m.user_id<>p_admin;
 SELECT count(*) INTO signed FROM public.memberships m
 WHERE m.tenant_id=p_tenant AND m.role='TENANT_MEMBER'
 AND m.status='ATIVA' AND m.user_id<>p_admin
 AND (SELECT e.decision FROM public.annual_self_loan_events_staging e
   WHERE e.tenant_id=p_tenant AND e.cycle_year=p_year AND e.admin_id=p_admin
   AND e.membership_id=m.id AND e.actor_id=m.user_id
   AND e.terms_sha=p_terms AND e.occurred_at<=p_at
   ORDER BY e.seq DESC LIMIT 1)='SIGNED';
 RETURN jsonb_build_object('state','CI_EVIDENCE_ONLY','required',needed,
   'signed',signed,'missing',needed-signed,
   'unanimous_synthetic',needed>0 AND signed=needed,
   'real_authorized',false,'loan_approval_authorized',false,
   'payout_authorized',false,'reserve_authorized',false);
END $f$;
CREATE FUNCTION public.annual_event_immutable_ci() RETURNS trigger LANGUAGE plpgsql AS $f$
BEGIN RAISE EXCEPTION 'M30400_APPEND_ONLY'; END $f$;
CREATE TRIGGER annual_event_immutable_ci BEFORE UPDATE OR DELETE ON
public.annual_self_loan_events_staging FOR EACH ROW EXECUTE
FUNCTION public.annual_event_immutable_ci();
REVOKE ALL ON FUNCTION public.annual_event_record_ci(
uuid,uuid,integer,uuid,uuid,uuid,varchar,varchar,varchar,timestamptz)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_annual_ci;
REVOKE ALL ON FUNCTION public.annual_event_review_ci(
uuid,integer,uuid,varchar,timestamptz)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_annual_ci;
GRANT EXECUTE ON FUNCTION public.annual_event_record_ci(
uuid,uuid,integer,uuid,uuid,uuid,varchar,varchar,varchar,timestamptz)
 TO frcaixinha_annual_ci;
GRANT EXECUTE ON FUNCTION public.annual_event_review_ci(
uuid,integer,uuid,varchar,timestamptz) TO frcaixinha_annual_ci;
REVOKE ALL ON FUNCTION public.annual_event_immutable_ci() FROM PUBLIC;
COMMIT;
