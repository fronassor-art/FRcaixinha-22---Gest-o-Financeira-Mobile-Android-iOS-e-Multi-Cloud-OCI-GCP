-- M37455: synthetic SaaS contract confirmation in disposable PostgreSQL CI ONLY.
-- This is a test schema, not a production migration, legal consent, or licence.
-- NEVER execute from Termux, OCI staging, production or any permanent database.
BEGIN;
DO $gate$
BEGIN
 IF current_database() <> 'frcaixinha_staging'
 OR session_user <> 'postgres'
 OR current_setting('is_superuser') <> 'on'
 OR current_setting('frcaixinha.saas_consent_ci',true) IS DISTINCT FROM '1'
 OR NOT EXISTS (
     SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_consent_ci'
      AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreaterole AND NOT rolcreatedb
 )
 OR to_regclass('public.saas_enrollment_requests_staging') IS NULL
 THEN
   RAISE EXCEPTION 'M37455_DISPOSABLE_CI_ONLY';
 END IF;
END $gate$;

CREATE TABLE public.saas_consent_challenges_m37455_ci (
 challenge_id uuid PRIMARY KEY,
 request_id uuid NOT NULL UNIQUE REFERENCES public.saas_enrollment_requests_staging(request_id),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 administrator_id uuid NOT NULL REFERENCES public.users(id),
 session_id uuid NOT NULL,
 document_id uuid NOT NULL REFERENCES public.contract_documents(id),
 document_sha256 char(64) NOT NULL CHECK(document_sha256 ~ '^[0-9a-f]{64}$'),
 price_version_id uuid NOT NULL REFERENCES public.platform_license_price_versions(id),
 issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 expires_at timestamptz NOT NULL DEFAULT (clock_timestamp() + interval '10 minutes'),
 CHECK(expires_at > issued_at AND expires_at <= issued_at + interval '10 minutes 5 seconds')
);
CREATE TABLE public.saas_consent_receipts_m37455_ci (
 challenge_id uuid PRIMARY KEY REFERENCES public.saas_consent_challenges_m37455_ci(challenge_id),
 request_id uuid NOT NULL UNIQUE REFERENCES public.saas_enrollment_requests_staging(request_id),
 tenant_id uuid NOT NULL,
 administrator_id uuid NOT NULL,
 session_id uuid NOT NULL,
 document_id uuid NOT NULL,
 document_sha256 char(64) NOT NULL CHECK(document_sha256 ~ '^[0-9a-f]{64}$'),
 price_version_id uuid NOT NULL,
 confirmation_text text NOT NULL
   CHECK(confirmation_text='ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE'),
 evidence_digest char(64) NOT NULL CHECK(evidence_digest ~ '^[0-9a-f]{64}$'),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.saas_consent_challenges_m37455_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_consent_challenges_m37455_ci FORCE ROW LEVEL SECURITY;
ALTER TABLE public.saas_consent_receipts_m37455_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_consent_receipts_m37455_ci FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_consent_challenges_m37455_ci,public.saas_consent_receipts_m37455_ci
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_consent_ci;

-- Explicit append-only protection even against accidental owner DML.
CREATE FUNCTION public.m37455_reject_mutation_ci()
RETURNS trigger LANGUAGE plpgsql
SET search_path=pg_catalog,public,pg_temp AS $func$
BEGIN
 RAISE EXCEPTION 'M37455_APPEND_ONLY_CI';
END $func$;
CREATE TRIGGER m37455_challenge_immutable_ci
 BEFORE UPDATE OR DELETE ON public.saas_consent_challenges_m37455_ci
 FOR EACH ROW EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37455_receipt_immutable_ci
 BEFORE UPDATE OR DELETE ON public.saas_consent_receipts_m37455_ci
 FOR EACH ROW EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37455_challenge_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_consent_challenges_m37455_ci
 FOR EACH STATEMENT EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37455_receipt_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_consent_receipts_m37455_ci
 FOR EACH STATEMENT EXECUTE FUNCTION public.m37455_reject_mutation_ci();

CREATE FUNCTION public.m37455_issue_challenge_ci(
 p_challenge uuid, p_request uuid, p_tenant uuid, p_admin uuid,
 p_session uuid, p_document uuid, p_document_sha text, p_price uuid
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $func$
DECLARE
 existing record;
 inserted integer;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_consent_ci'
 OR current_setting('frcaixinha.saas_consent_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M37455_WORKER_CI_ONLY'; END IF;
 IF p_challenge IS NULL OR p_challenge='00000000-0000-0000-0000-000000000000'::uuid
 OR p_request IS NULL OR p_tenant IS NULL OR p_admin IS NULL
 OR p_session IS NULL OR p_session='00000000-0000-0000-0000-000000000000'::uuid
 OR p_document IS NULL OR p_price IS NULL
 OR p_document_sha IS NULL OR p_document_sha !~ '^[0-9a-f]{64}$'
 THEN RETURN 'DENIED_CI'; END IF;

 -- Lock the preparation tenant, preventing concurrent request conflicts.
 PERFORM 1 FROM public.tenants t
 WHERE t.id=p_tenant AND t.admin_user_id=p_admin AND t.status='ATIVO'
 FOR UPDATE;
 IF NOT FOUND OR NOT EXISTS (
   SELECT 1 FROM public.users u WHERE u.id=p_admin AND u.status='ACTIVE'
 ) OR NOT EXISTS (
   SELECT 1 FROM public.memberships m WHERE m.tenant_id=p_tenant
    AND m.user_id=p_admin AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 ) OR NOT EXISTS (
   SELECT 1
   FROM public.saas_enrollment_requests_staging e
   JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id
   JOIN public.contract_acceptances a ON a.id=e.contract_acceptance_id
   JOIN public.contract_documents d ON d.id=a.document_id
   JOIN public.platform_license_price_versions v ON v.id=e.price_version_id
   JOIN public.platform_license_plans pl ON pl.tier=v.plan_tier
   WHERE e.request_id=p_request AND e.tenant_id=p_tenant
    AND e.admin_user_id=p_admin AND e.price_version_id=p_price
    AND e.payment_created=false AND e.entitlement_created=false
    AND s.tenant_id=e.tenant_id AND s.admin_user_id=e.admin_user_id
    AND s.price_version_id=e.price_version_id
    AND s.contract_acceptance_id=e.contract_acceptance_id
    AND s.status='PENDING_PAYMENT' AND s.plan_tier=v.plan_tier
    AND pl.status='ACTIVE' AND e.billing_period=s.billing_period
    AND d.id=p_document AND d.document_kind='PLATFORM_LICENSE'
    AND d.sha256=p_document_sha AND d.published_at IS NOT NULL
    AND d.published_at <= a.accepted_at AND a.accepted_at<=clock_timestamp()
    AND a.user_id=p_admin AND a.document_kind='PLATFORM_LICENSE'
    AND a.tenant_id IS NULL AND a.evidence_method='CI_VERIFIED_IDENTITY'
 )
 THEN RETURN 'DENIED_CI'; END IF;
 IF EXISTS(SELECT 1 FROM public.saas_payment_intents i
    JOIN public.saas_enrollment_requests_staging e ON e.preparation_id=i.preparation_id
    WHERE e.request_id=p_request)
 OR EXISTS(SELECT 1 FROM public.saas_license_entitlements l
    JOIN public.saas_enrollment_requests_staging e ON e.preparation_id=l.preparation_id
    WHERE e.request_id=p_request)
 THEN RETURN 'DENIED_CI'; END IF;

 INSERT INTO public.saas_consent_challenges_m37455_ci(
   challenge_id,request_id,tenant_id,administrator_id,session_id,
   document_id,document_sha256,price_version_id
 ) VALUES(
   p_challenge,p_request,p_tenant,p_admin,p_session,
   p_document,p_document_sha,p_price
 ) ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 IF inserted=1 THEN RETURN 'ISSUED_CI_NO_REAL_INVITATION'; END IF;

 SELECT * INTO existing FROM public.saas_consent_challenges_m37455_ci
 WHERE challenge_id=p_challenge FOR UPDATE;
 IF FOUND AND existing.request_id=p_request
   AND existing.tenant_id=p_tenant AND existing.administrator_id=p_admin
   AND existing.session_id=p_session AND existing.document_id=p_document
   AND existing.document_sha256=p_document_sha
   AND existing.price_version_id=p_price
   AND clock_timestamp()<existing.expires_at
 THEN RETURN 'REPLAY_ISSUE_CI_NO_WRITE'; END IF;
 RETURN 'COLLISION_CI_DENIED';
END $func$;

CREATE FUNCTION public.m37455_record_affirmation_ci(
 p_challenge uuid, p_request uuid, p_tenant uuid, p_admin uuid,
 p_session uuid, p_document uuid, p_document_sha text,
 p_price uuid, p_confirmation text, p_digest text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $func$
DECLARE
 c record; prior record;
 inserted integer;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_consent_ci'
 OR current_setting('frcaixinha.saas_consent_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M37455_WORKER_CI_ONLY'; END IF;
 IF p_confirmation IS DISTINCT FROM 'ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE'
 OR p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
 OR p_document_sha IS NULL OR p_document_sha !~ '^[0-9a-f]{64}$'
 OR p_challenge IS NULL OR p_request IS NULL OR p_tenant IS NULL
 OR p_admin IS NULL OR p_session IS NULL OR p_document IS NULL OR p_price IS NULL
 THEN RETURN 'DENIED_CI'; END IF;

 SELECT * INTO c FROM public.saas_consent_challenges_m37455_ci
 WHERE challenge_id=p_challenge FOR UPDATE;
 IF NOT FOUND OR clock_timestamp()>=c.expires_at
 OR c.request_id<>p_request OR c.tenant_id<>p_tenant
 OR c.administrator_id<>p_admin OR c.session_id<>p_session
 OR c.document_id<>p_document OR c.document_sha256<>p_document_sha
 OR c.price_version_id<>p_price
 THEN RETURN 'DENIED_CI'; END IF;
 -- The claimed digest is a CI test value and is not identity verification.
 INSERT INTO public.saas_consent_receipts_m37455_ci(
   challenge_id,request_id,tenant_id,administrator_id,session_id,
   document_id,document_sha256,price_version_id,
   confirmation_text,evidence_digest
 ) VALUES (
   p_challenge,p_request,p_tenant,p_admin,p_session,
   p_document,p_document_sha,p_price,p_confirmation,p_digest
 ) ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 IF inserted=1 THEN RETURN 'RECORDED_CI_NOT_LEGAL_CONSENT'; END IF;

 SELECT * INTO prior FROM public.saas_consent_receipts_m37455_ci
 WHERE challenge_id=p_challenge;
 IF FOUND AND prior.request_id=p_request AND prior.tenant_id=p_tenant
   AND prior.administrator_id=p_admin AND prior.session_id=p_session
   AND prior.document_id=p_document AND prior.document_sha256=p_document_sha
   AND prior.price_version_id=p_price AND prior.confirmation_text=p_confirmation
   AND prior.evidence_digest=p_digest
 THEN RETURN 'REPLAY_CI_NO_WRITE'; END IF;
 RETURN 'RECEIPT_COLLISION_CI_DENIED';
END $func$;
REVOKE ALL ON FUNCTION public.m37455_reject_mutation_ci() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.m37455_issue_challenge_ci(
 uuid,uuid,uuid,uuid,uuid,uuid,text,uuid)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role;
REVOKE ALL ON FUNCTION public.m37455_record_affirmation_ci(
 uuid,uuid,uuid,uuid,uuid,uuid,text,uuid,text,text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role;
GRANT EXECUTE ON FUNCTION public.m37455_issue_challenge_ci(
 uuid,uuid,uuid,uuid,uuid,uuid,text,uuid) TO frcaixinha_saas_consent_ci;
GRANT EXECUTE ON FUNCTION public.m37455_record_affirmation_ci(
 uuid,uuid,uuid,uuid,uuid,uuid,text,uuid,text,text) TO frcaixinha_saas_consent_ci;
COMMIT;
