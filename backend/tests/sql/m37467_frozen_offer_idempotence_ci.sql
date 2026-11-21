-- M37467: disposable only; freeze published offer hash and price at ISSUE.
-- This is synthetic consent and does not authorize billing, license or Pix.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
  OR session_user<>'postgres'
  OR current_setting('is_superuser')<>'on'
  OR current_setting('frcaixinha.saas_frozen_ci',true) IS DISTINCT FROM '1'
  OR to_regprocedure('public.m37464_atomic_consent_ci(text,text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)') IS NULL
  OR to_regclass('public.saas_preprep_challenges_m37458_ci') IS NULL
  OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_preprep_ci'
    AND NOT rolsuper AND NOT rolbypassrls)
 THEN RAISE EXCEPTION 'M37467_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.saas_frozen_offer_m37467_ci (
 request_id uuid PRIMARY KEY,
 challenge_id uuid NOT NULL UNIQUE,
 session_id uuid NOT NULL,
 tenant_id uuid NOT NULL,
 admin_id uuid NOT NULL,
 document_id uuid NOT NULL,
 document_sha text NOT NULL CHECK(document_sha~'^[0-9a-f]{64}$'),
 price_version_id uuid NOT NULL,
 billing_period text NOT NULL CHECK(billing_period IN ('MONTHLY','ANNUAL')),
 frozen_price_cents bigint NOT NULL CHECK(frozen_price_cents>0),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 evidence_source text NOT NULL DEFAULT 'CI_FROZEN_SYNTHETIC_NOT_LEGAL'
  CHECK(evidence_source='CI_FROZEN_SYNTHETIC_NOT_LEGAL')
);
ALTER TABLE public.saas_frozen_offer_m37467_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_frozen_offer_m37467_ci FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_frozen_offer_m37467_ci FROM PUBLIC,
 frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_preprep_ci;
CREATE TRIGGER m37467_frozen_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_frozen_offer_m37467_ci
 FOR EACH ROW EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37467_frozen_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_frozen_offer_m37467_ci
 FOR EACH STATEMENT EXECUTE FUNCTION public.m37455_reject_mutation_ci();

-- A separate disposable test session, not the revoked M37464 fixture.
INSERT INTO public.sessions(
 id,token_hash,user_id,active_role,active_tenant_id,expires_at
) VALUES(
 'daba0000-0000-4000-8000-000000000686',
 encode(public.digest('m37467-ci-frozen-offer-NEVER-REAL-01','sha256'),'hex'),
 'daba0000-0000-4000-8000-000000000001',
 'TENANT_ADMIN','daba0000-0000-4000-8000-000000000010',
 clock_timestamp()+interval '40 minutes');
INSERT INTO public.saas_preprep_sessions_m37458_ci(
 session_id,tenant_id,admin_id,role,session_active,email_verified
) VALUES(
 'daba0000-0000-4000-8000-000000000686',
 'daba0000-0000-4000-8000-000000000010',
 'daba0000-0000-4000-8000-000000000001',
 'TENANT_ADMIN',true,true);

CREATE FUNCTION public.m37467_frozen_offer_transition_ci(
 p_action text,p_token_hash text,p_session uuid,p_challenge uuid,
 p_request uuid,p_tenant uuid,p_admin uuid,p_document uuid,
 p_price uuid,p_period text,p_confirmation text,
 p_document_sha text,p_expected_price_cents bigint
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $frozen$
DECLARE
 v_offer record;
 v_frozen record;
 v_result text;
 v_cents numeric;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_preprep_ci'
 OR current_setting('frcaixinha.saas_frozen_ci',true) IS DISTINCT FROM '1'
 OR current_setting('frcaixinha.saas_atomic_ci',true) IS DISTINCT FROM '1'
 OR current_setting('frcaixinha.saas_preprep_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M37467_WRONG_CI_WORKER'; END IF;

 IF p_action IS NULL OR p_action NOT IN ('ISSUE','ACCEPT','PREPARE')
 OR p_session IS NULL OR p_challenge IS NULL OR p_request IS NULL
 OR p_tenant IS NULL OR p_admin IS NULL OR p_document IS NULL
 OR p_price IS NULL OR p_period IS NULL
 OR p_period NOT IN ('MONTHLY','ANNUAL')
 OR p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$'
 OR p_document_sha IS NULL OR p_document_sha !~ '^[0-9a-f]{64}$'
 OR p_expected_price_cents IS NULL OR p_expected_price_cents<=0
 OR p_expected_price_cents>999999999999
 THEN RETURN 'DENIED_CI_FROZEN_OFFER_INVALID_INPUT'; END IF;

 -- HOLD locks on both published contract and price ROWS for the full
 -- worker transaction. An UPDATE cannot change either between ISSUE
 -- and ACCEPT. All values below come from the canonical server tables.
 SELECT d.id,d.sha256,d.document_kind,d.published_at,
        v.id AS price_id,v.monthly_price,v.annual_price,
        p.status AS plan_status,
        p.tier AS plan_tier
 INTO v_offer
 FROM public.contract_documents d
 JOIN public.platform_license_price_versions v ON v.id=p_price
 JOIN public.platform_license_plans p ON p.tier=v.plan_tier
 WHERE d.id=p_document
 FOR SHARE OF d,v;
 IF NOT FOUND OR v_offer.document_kind<>'PLATFORM_LICENSE'
 OR v_offer.published_at IS NULL
 OR v_offer.published_at>clock_timestamp()
 OR v_offer.plan_status<>'ACTIVE'
 OR v_offer.sha256 IS DISTINCT FROM p_document_sha
 OR v_offer.monthly_price IS NULL OR v_offer.monthly_price<=0
 OR v_offer.annual_price<>10*v_offer.monthly_price
 THEN RETURN 'DENIED_CI_FROZEN_PUBLISHED_OFFER_DRIFT'; END IF;

 v_cents:=(CASE WHEN p_period='MONTHLY' THEN v_offer.monthly_price
               ELSE v_offer.annual_price END)*100;
 IF v_cents<>trunc(v_cents)
 OR v_cents<>p_expected_price_cents
 THEN RETURN 'DENIED_CI_FROZEN_PUBLISHED_OFFER_DRIFT'; END IF;

 -- A replay MUST use the exact same challenge, session, administrator,
 -- document, digest, price version, amount and billing period.
 SELECT * INTO v_frozen
 FROM public.saas_frozen_offer_m37467_ci q
 WHERE q.request_id=p_request;
 IF FOUND AND (
    v_frozen.challenge_id<>p_challenge OR
    v_frozen.session_id<>p_session OR
    v_frozen.tenant_id<>p_tenant OR
    v_frozen.admin_id<>p_admin OR
    v_frozen.document_id<>p_document OR
    v_frozen.document_sha<>p_document_sha OR
    v_frozen.price_version_id<>p_price OR
    v_frozen.billing_period<>p_period OR
    v_frozen.frozen_price_cents<>p_expected_price_cents
 ) THEN RETURN 'DENIED_CI_FROZEN_REQUEST_COLLISION'; END IF;
 IF NOT FOUND AND p_action<>'ISSUE'
 THEN RETURN 'DENIED_CI_NO_FROZEN_ISSUE'; END IF;

 -- The canonical M37464 function revalidates token and row-locks
 -- public.sessions in THIS SAME transaction before any synthetic write.
 v_result:=public.m37464_atomic_consent_ci(
  p_action,p_token_hash,p_session,p_challenge,p_request,p_tenant,
  p_admin,p_document,p_price,p_period,p_confirmation);
 IF p_action='ISSUE' AND v_result IN (
   'CHALLENGE_ISSUED_CI','REPLAY_ISSUE_CI_NO_WRITE') THEN
   INSERT INTO public.saas_frozen_offer_m37467_ci(
    request_id,challenge_id,session_id,tenant_id,admin_id,
    document_id,document_sha,price_version_id,billing_period,
    frozen_price_cents
   ) VALUES(
    p_request,p_challenge,p_session,p_tenant,p_admin,p_document,
    p_document_sha,p_price,p_period,p_expected_price_cents
   ) ON CONFLICT DO NOTHING;
   SELECT * INTO v_frozen FROM public.saas_frozen_offer_m37467_ci
   WHERE request_id=p_request;
   IF NOT FOUND OR v_frozen.challenge_id<>p_challenge
    OR v_frozen.document_sha<>p_document_sha
    OR v_frozen.frozen_price_cents<>p_expected_price_cents
    OR v_frozen.price_version_id<>p_price
   THEN RAISE EXCEPTION 'M37467_ATOMIC_FROZEN_RECEIPT_MISMATCH'; END IF;
 END IF;
 RETURN v_result;
END $frozen$;

REVOKE ALL ON FUNCTION public.m37467_frozen_offer_transition_ci(
 text,text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text,text,bigint)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_preprep_ci;
GRANT EXECUTE ON FUNCTION public.m37467_frozen_offer_transition_ci(
 text,text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text,text,bigint)
 TO frcaixinha_saas_preprep_ci;

DO $roles$
BEGIN
 IF has_table_privilege('frcaixinha_app_role',
  'public.saas_frozen_offer_m37467_ci','SELECT')
 OR has_table_privilege('frcaixinha_saas_preprep_ci',
  'public.saas_frozen_offer_m37467_ci','UPDATE')
 OR has_table_privilege('frcaixinha_saas_preprep_ci',
  'public.saas_frozen_offer_m37467_ci','INSERT')
 OR NOT has_function_privilege('frcaixinha_saas_preprep_ci',
  'public.m37467_frozen_offer_transition_ci(text,text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text,text,bigint)','EXECUTE')
 THEN RAISE EXCEPTION 'M37467_FROZEN_WORKER_PRIVILEGES'; END IF;
END $roles$;
COMMIT;
