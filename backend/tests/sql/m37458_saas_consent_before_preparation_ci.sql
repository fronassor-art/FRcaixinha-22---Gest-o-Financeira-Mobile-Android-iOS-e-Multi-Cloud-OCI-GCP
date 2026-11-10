-- M37458 — CI-only, consent BEFORE draft SaaS preparation.
-- Isolated disposable PostgreSQL. Not a product migration or legal consent.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
 OR current_setting('is_superuser')<>'on'
 OR current_setting('frcaixinha.saas_preprep_ci',true) IS DISTINCT FROM '1'
 OR to_regclass('public.saas_enrollment_requests_staging') IS NULL
 OR NOT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_preprep_ci'
   AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M37458_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.saas_preprep_sessions_m37458_ci (
 session_id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 admin_id uuid NOT NULL REFERENCES public.users(id),
 role text NOT NULL CHECK(role='TENANT_ADMIN'),
 session_active boolean NOT NULL CHECK(session_active),
 email_verified boolean NOT NULL CHECK(email_verified),
 server_issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 server_expires_at timestamptz NOT NULL DEFAULT (clock_timestamp()+interval '1 hour'),
 CHECK(server_expires_at>server_issued_at)
);
CREATE TABLE public.saas_preprep_challenges_m37458_ci (
 challenge_id uuid PRIMARY KEY,
 request_id uuid NOT NULL UNIQUE,
 session_id uuid NOT NULL REFERENCES public.saas_preprep_sessions_m37458_ci(session_id),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 admin_id uuid NOT NULL REFERENCES public.users(id),
 document_id uuid NOT NULL REFERENCES public.contract_documents(id),
 document_sha char(64) NOT NULL CHECK(document_sha ~ '^[0-9a-f]{64}$'),
 price_version_id uuid NOT NULL REFERENCES public.platform_license_price_versions(id),
 billing_period text NOT NULL CHECK(billing_period IN ('MONTHLY','ANNUAL')),
 server_issued_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 server_expires_at timestamptz NOT NULL DEFAULT(clock_timestamp()+interval '5 minutes'),
 CHECK(server_expires_at>server_issued_at AND
       server_expires_at<=server_issued_at+interval '5 minutes 5 seconds')
);
CREATE TABLE public.saas_preprep_receipts_m37458_ci (
 challenge_id uuid PRIMARY KEY REFERENCES public.saas_preprep_challenges_m37458_ci(challenge_id),
 request_id uuid NOT NULL UNIQUE,
 session_id uuid NOT NULL,
 tenant_id uuid NOT NULL,
 admin_id uuid NOT NULL,
 document_id uuid NOT NULL,
 document_sha char(64) NOT NULL CHECK(document_sha ~ '^[0-9a-f]{64}$'),
 price_version_id uuid NOT NULL,
 billing_period text NOT NULL,
 confirmation_text text NOT NULL
   CHECK(confirmation_text='ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE'),
 server_recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 evidence_source text NOT NULL DEFAULT 'CI_SYNTHETIC_NOT_LEGAL_CONSENT'
   CHECK(evidence_source='CI_SYNTHETIC_NOT_LEGAL_CONSENT')
);
CREATE TABLE public.saas_preprep_drafts_m37458_ci (
 request_id uuid PRIMARY KEY,
 challenge_id uuid NOT NULL UNIQUE REFERENCES public.saas_preprep_receipts_m37458_ci(challenge_id),
 tenant_id uuid NOT NULL,
 admin_id uuid NOT NULL,
 document_id uuid NOT NULL,
 price_version_id uuid NOT NULL,
 billing_period text NOT NULL,
 server_prepared_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 status text NOT NULL DEFAULT 'CI_DRAFT_NO_PAYMENT'
   CHECK(status='CI_DRAFT_NO_PAYMENT'),
 legal_consent_verified boolean NOT NULL DEFAULT false CHECK(NOT legal_consent_verified),
 payment_authorized boolean NOT NULL DEFAULT false CHECK(NOT payment_authorized),
 license_authorized boolean NOT NULL DEFAULT false CHECK(NOT license_authorized),
 activation_authorized boolean NOT NULL DEFAULT false CHECK(NOT activation_authorized)
);
ALTER TABLE public.saas_preprep_sessions_m37458_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_preprep_sessions_m37458_ci FORCE ROW LEVEL SECURITY;
ALTER TABLE public.saas_preprep_challenges_m37458_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_preprep_challenges_m37458_ci FORCE ROW LEVEL SECURITY;
ALTER TABLE public.saas_preprep_receipts_m37458_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_preprep_receipts_m37458_ci FORCE ROW LEVEL SECURITY;
ALTER TABLE public.saas_preprep_drafts_m37458_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_preprep_drafts_m37458_ci FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_preprep_sessions_m37458_ci,
 public.saas_preprep_challenges_m37458_ci,
 public.saas_preprep_receipts_m37458_ci,
 public.saas_preprep_drafts_m37458_ci
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_preprep_ci;

-- Neither worker nor application gets raw DML. Append-only even for owner.
CREATE TRIGGER m37458_session_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_preprep_sessions_m37458_ci
 FOR EACH ROW EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37458_challenge_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_preprep_challenges_m37458_ci
 FOR EACH ROW EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37458_receipt_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_preprep_receipts_m37458_ci
 FOR EACH ROW EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37458_draft_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_preprep_drafts_m37458_ci
 FOR EACH ROW EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37458_session_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_preprep_sessions_m37458_ci
 FOR EACH STATEMENT EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37458_challenge_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_preprep_challenges_m37458_ci
 FOR EACH STATEMENT EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37458_receipt_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_preprep_receipts_m37458_ci
 FOR EACH STATEMENT EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37458_draft_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_preprep_drafts_m37458_ci
 FOR EACH STATEMENT EXECUTE FUNCTION public.m37455_reject_mutation_ci();

-- Only trusted CI fixture setup may write session claim records.
INSERT INTO public.saas_preprep_sessions_m37458_ci(
 session_id,tenant_id,admin_id,role,session_active,email_verified)
 VALUES('daba0000-0000-4000-8000-000000000581',
        'daba0000-0000-4000-8000-000000000010',
        'daba0000-0000-4000-8000-000000000001',
        'TENANT_ADMIN',true,true);

CREATE FUNCTION public.m37458_transition_ci(
 p_action text,p_session uuid,p_challenge uuid,p_request uuid,
 p_tenant uuid,p_admin uuid,p_document uuid,p_price uuid,
 p_period text,p_confirmation text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 ss record; cc record; rr record; dd record;
 inserted integer;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_preprep_ci'
 OR current_setting('frcaixinha.saas_preprep_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M37458_WORKER_CI_ONLY'; END IF;
 IF p_action NOT IN ('ISSUE','ACCEPT','PREPARE')
 OR p_session IS NULL OR p_challenge IS NULL OR p_request IS NULL
 OR p_tenant IS NULL OR p_admin IS NULL OR p_document IS NULL
 OR p_price IS NULL OR p_period NOT IN ('MONTHLY','ANNUAL')
 OR p_challenge='00000000-0000-0000-0000-000000000000'::uuid
 OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 THEN RETURN 'DENIED_CI'; END IF;

 -- Lock tenant before all steps; serializes different workers for one box.
 PERFORM 1 FROM public.tenants t
  WHERE t.id=p_tenant AND t.admin_user_id=p_admin AND t.status='ATIVO'
  FOR UPDATE;
 IF NOT FOUND OR NOT EXISTS(
  SELECT 1 FROM public.users u WHERE u.id=p_admin AND u.status='ACTIVE'
 ) OR NOT EXISTS(
  SELECT 1 FROM public.memberships m WHERE m.tenant_id=p_tenant
  AND m.user_id=p_admin AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 ) THEN RETURN 'DENIED_CI'; END IF;

 SELECT * INTO ss FROM public.saas_preprep_sessions_m37458_ci s
 WHERE s.session_id=p_session FOR UPDATE;
 IF NOT FOUND OR ss.tenant_id<>p_tenant OR ss.admin_id<>p_admin
 OR ss.role<>'TENANT_ADMIN' OR NOT ss.session_active OR NOT ss.email_verified
 OR clock_timestamp()>=ss.server_expires_at
 OR NOT EXISTS(
 SELECT 1 FROM public.contract_documents d
 JOIN public.platform_license_price_versions v ON v.id=p_price
 JOIN public.platform_license_plans p ON p.tier=v.plan_tier
 WHERE d.id=p_document AND d.document_kind='PLATFORM_LICENSE'
 AND d.published_at IS NOT NULL AND d.published_at<=clock_timestamp()
 AND d.sha256 ~ '^[0-9a-f]{64}$'
 AND p.status='ACTIVE' AND v.monthly_price>0
 AND v.annual_price=10*v.monthly_price
 )
 THEN RETURN 'DENIED_CI'; END IF;

 IF p_action='ISSUE' THEN
   INSERT INTO public.saas_preprep_challenges_m37458_ci(
     challenge_id,request_id,session_id,tenant_id,admin_id,document_id,
     document_sha,price_version_id,billing_period
   ) SELECT p_challenge,p_request,p_session,p_tenant,p_admin,p_document,
         d.sha256,p_price,p_period
     FROM public.contract_documents d WHERE d.id=p_document
   ON CONFLICT DO NOTHING;
   GET DIAGNOSTICS inserted=ROW_COUNT;
   IF inserted=1 THEN RETURN 'CHALLENGE_ISSUED_CI'; END IF;
   SELECT * INTO cc FROM public.saas_preprep_challenges_m37458_ci
    WHERE request_id=p_request;
   IF FOUND AND cc.challenge_id=p_challenge AND cc.session_id=p_session
      AND cc.tenant_id=p_tenant AND cc.admin_id=p_admin
      AND cc.document_id=p_document AND cc.price_version_id=p_price
      AND cc.billing_period=p_period
   THEN RETURN 'REPLAY_ISSUE_CI_NO_WRITE'; END IF;
   RETURN 'CHALLENGE_COLLISION_CI_DENIED';
 END IF;

 SELECT * INTO cc FROM public.saas_preprep_challenges_m37458_ci
   WHERE challenge_id=p_challenge FOR UPDATE;
 IF NOT FOUND OR cc.request_id<>p_request
 OR cc.session_id<>p_session OR cc.tenant_id<>p_tenant OR cc.admin_id<>p_admin
 OR cc.document_id<>p_document OR cc.price_version_id<>p_price
 OR cc.billing_period<>p_period
 OR cc.server_expires_at<=clock_timestamp()
 THEN RETURN 'DENIED_CI'; END IF;

 IF p_action='ACCEPT' THEN
   IF p_confirmation IS DISTINCT FROM 'ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE'
   THEN RETURN 'DENIED_CI'; END IF;
   INSERT INTO public.saas_preprep_receipts_m37458_ci(
     challenge_id,request_id,session_id,tenant_id,admin_id,document_id,
     document_sha,price_version_id,billing_period,confirmation_text
   ) VALUES(
     p_challenge,p_request,p_session,p_tenant,p_admin,p_document,
     cc.document_sha,p_price,p_period,p_confirmation
   ) ON CONFLICT DO NOTHING;
   GET DIAGNOSTICS inserted=ROW_COUNT;
   IF inserted=1 THEN RETURN 'CONSENT_RECORDED_CI_NO_LEGAL_PROOF'; END IF;
   SELECT * INTO rr FROM public.saas_preprep_receipts_m37458_ci
    WHERE challenge_id=p_challenge;
   IF FOUND AND rr.request_id=p_request AND rr.session_id=p_session
     AND rr.tenant_id=p_tenant AND rr.admin_id=p_admin
     AND rr.document_id=p_document AND rr.price_version_id=p_price
     AND rr.billing_period=p_period AND rr.confirmation_text=p_confirmation
   THEN RETURN 'REPLAY_ACCEPT_CI_NO_WRITE'; END IF;
   RETURN 'CONSENT_COLLISION_CI_DENIED';
 END IF;

 -- PREPARE cannot invent, backdate, or bypass the committed receipt.
 SELECT * INTO rr FROM public.saas_preprep_receipts_m37458_ci
   WHERE challenge_id=p_challenge;
 IF NOT FOUND OR rr.request_id<>p_request OR rr.session_id<>p_session
 OR rr.tenant_id<>p_tenant OR rr.admin_id<>p_admin
 OR rr.document_id<>p_document OR rr.price_version_id<>p_price
 OR rr.billing_period<>p_period
 OR rr.document_sha<>cc.document_sha
 OR rr.server_recorded_at<cc.server_issued_at
 OR rr.server_recorded_at>clock_timestamp()
 OR EXISTS(
   SELECT 1 FROM public.saas_payment_intents i WHERE i.tenant_id=p_tenant
 ) OR EXISTS(
   SELECT 1 FROM public.saas_license_entitlements e WHERE e.tenant_id=p_tenant
 )
 THEN RETURN 'CONSENT_BEFORE_PREPARATION_REQUIRED'; END IF;

 INSERT INTO public.saas_preprep_drafts_m37458_ci(
  request_id,challenge_id,tenant_id,admin_id,document_id,
  price_version_id,billing_period
 ) VALUES(p_request,p_challenge,p_tenant,p_admin,p_document,p_price,p_period)
 ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS inserted=ROW_COUNT;
 IF inserted=1 THEN RETURN 'DRAFT_PREPARED_CI_NO_PAYMENT'; END IF;
 SELECT * INTO dd FROM public.saas_preprep_drafts_m37458_ci
  WHERE request_id=p_request;
 IF FOUND AND dd.challenge_id=p_challenge AND dd.tenant_id=p_tenant
  AND dd.admin_id=p_admin AND dd.document_id=p_document
  AND dd.price_version_id=p_price AND dd.billing_period=p_period
  AND NOT dd.legal_consent_verified AND NOT dd.payment_authorized
  AND NOT dd.license_authorized AND NOT dd.activation_authorized
 THEN RETURN 'REPLAY_PREPARE_CI_NO_WRITE'; END IF;
 RETURN 'DRAFT_COLLISION_CI_DENIED';
END $fn$;
REVOKE ALL ON FUNCTION public.m37458_transition_ci(
 text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_preprep_ci;
GRANT EXECUTE ON FUNCTION public.m37458_transition_ci(
 text,uuid,uuid,uuid,uuid,uuid,uuid,uuid,text,text)
 TO frcaixinha_saas_preprep_ci;
COMMIT;
