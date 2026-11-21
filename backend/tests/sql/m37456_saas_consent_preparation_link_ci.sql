-- FR Finance M37456: correlate a CI-only consent receipt with a SaaS preparation.
-- Test fixture SQL only. NEVER apply on Termux PostgreSQL 5433 or any OCI DB.
-- A successful link is explicitly POST-PREPARATION and NOT LEGAL CONSENT.
BEGIN;
DO $m37456_guard$
BEGIN
  IF current_database() <> 'frcaixinha_staging'
     OR session_user <> 'postgres'
     OR current_setting('is_superuser') <> 'on'
     OR current_setting('frcaixinha.saas_consent_ci',true) IS DISTINCT FROM '1'
     OR NOT EXISTS (
       SELECT 1 FROM pg_roles
       WHERE rolname = 'frcaixinha_saas_consent_ci'
       AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
     )
     OR to_regclass('public.saas_consent_receipts_m37455_ci') IS NULL
     OR to_regclass('public.saas_consent_challenges_m37455_ci') IS NULL
     OR to_regclass('public.saas_enrollment_requests_staging') IS NULL
  THEN RAISE EXCEPTION 'M37456_DISPOSABLE_CI_ONLY'; END IF;
END $m37456_guard$;

CREATE TABLE public.saas_consent_preparation_links_m37456_ci (
  link_id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  request_id uuid NOT NULL UNIQUE
    REFERENCES public.saas_enrollment_requests_staging(request_id) ON DELETE RESTRICT,
  preparation_id uuid NOT NULL UNIQUE
    REFERENCES public.saas_subscription_preparations(id) ON DELETE RESTRICT,
  challenge_id uuid NOT NULL UNIQUE
    REFERENCES public.saas_consent_receipts_m37455_ci(challenge_id) ON DELETE RESTRICT,
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  administrator_id uuid NOT NULL REFERENCES public.users(id),
  price_version_id uuid NOT NULL REFERENCES public.platform_license_price_versions(id),
  document_id uuid NOT NULL REFERENCES public.contract_documents(id),
  receipt_digest char(64) NOT NULL CHECK(receipt_digest ~ '^[0-9a-f]{64}$'),
  evidence_state varchar(60) NOT NULL
    DEFAULT 'POST_PREPARATION_CI_UNATTESTED'
    CHECK(evidence_state='POST_PREPARATION_CI_UNATTESTED'),
  legal_consent_verified boolean NOT NULL DEFAULT false CHECK(NOT legal_consent_verified),
  payment_authorized boolean NOT NULL DEFAULT false CHECK(NOT payment_authorized),
  license_authorized boolean NOT NULL DEFAULT false CHECK(NOT license_authorized),
  real_activation_authorized boolean NOT NULL DEFAULT false CHECK(NOT real_activation_authorized),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
ALTER TABLE public.saas_consent_preparation_links_m37456_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_consent_preparation_links_m37456_ci FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_consent_preparation_links_m37456_ci
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_consent_ci;

CREATE TRIGGER m37456_link_no_update_delete_ci
  BEFORE UPDATE OR DELETE ON public.saas_consent_preparation_links_m37456_ci
  FOR EACH ROW EXECUTE FUNCTION public.m37455_reject_mutation_ci();
CREATE TRIGGER m37456_link_no_truncate_ci
  BEFORE TRUNCATE ON public.saas_consent_preparation_links_m37456_ci
  FOR EACH STATEMENT EXECUTE FUNCTION public.m37455_reject_mutation_ci();

CREATE FUNCTION public.m37456_link_consent_to_preparation_ci(
  p_request uuid, p_preparation uuid, p_challenge uuid,
  p_tenant uuid, p_admin uuid, p_price uuid, p_digest text
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog,public,pg_temp AS $m37456_function$
DECLARE
  existing record;
  inserted integer;
BEGIN
  IF current_database()<>'frcaixinha_staging'
     OR session_user<>'frcaixinha_saas_consent_ci'
     OR current_setting('frcaixinha.saas_consent_ci',true) IS DISTINCT FROM '1'
  THEN RAISE EXCEPTION 'M37456_WORKER_CI_ONLY'; END IF;

  IF p_request IS NULL OR p_request='00000000-0000-0000-0000-000000000000'::uuid
     OR p_preparation IS NULL OR p_challenge IS NULL
     OR p_tenant IS NULL OR p_admin IS NULL OR p_price IS NULL
     OR p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
  THEN RETURN 'DENIED_CI'; END IF;

  -- Tenant lock serializes any competing insert for this preparation.
  PERFORM 1 FROM public.tenants t
    WHERE t.id=p_tenant AND t.admin_user_id=p_admin AND t.status='ATIVO'
    FOR UPDATE;
  IF NOT FOUND THEN RETURN 'DENIED_CI'; END IF;

  -- These checks establish *referential coherence only*, not consent.
  -- The existing acceptance hash is a placeholder distinct from the receipt.
  IF NOT EXISTS (
      SELECT 1
      FROM public.saas_enrollment_requests_staging e
      JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id
      JOIN public.contract_acceptances a ON a.id=e.contract_acceptance_id
      JOIN public.contract_documents d ON d.id=a.document_id
      JOIN public.platform_license_price_versions v ON v.id=e.price_version_id
      JOIN public.platform_license_plans p ON p.tier=v.plan_tier
      JOIN public.saas_consent_challenges_m37455_ci c ON c.request_id=e.request_id
      JOIN public.saas_consent_receipts_m37455_ci r ON r.challenge_id=c.challenge_id
      JOIN public.users u ON u.id=e.admin_user_id
      WHERE e.request_id=p_request AND e.preparation_id=p_preparation
        AND e.tenant_id=p_tenant AND e.admin_user_id=p_admin
        AND e.price_version_id=p_price AND e.payment_created=false
        AND e.entitlement_created=false
        AND s.id=p_preparation AND s.tenant_id=e.tenant_id
        AND s.admin_user_id=e.admin_user_id AND s.price_version_id=e.price_version_id
        AND s.contract_acceptance_id=e.contract_acceptance_id
        AND s.billing_period=e.billing_period AND s.plan_tier=v.plan_tier
        AND s.status='PENDING_PAYMENT'
        AND p.tier=s.plan_tier AND p.status='ACTIVE'
        AND a.user_id=p_admin AND a.tenant_id IS NULL
        AND a.document_kind='PLATFORM_LICENSE'
        AND a.evidence_method='CI_VERIFIED_IDENTITY'
        AND a.evidence_hash ~ '^[0-9a-f]{64}$'
        AND d.document_kind='PLATFORM_LICENSE'
        AND d.published_at IS NOT NULL AND d.published_at<=a.accepted_at
        AND a.accepted_at<=s.created_at
        AND u.status='ACTIVE'
        AND EXISTS (
          SELECT 1 FROM public.memberships m WHERE m.tenant_id=p_tenant
             AND m.user_id=p_admin AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
        )
        AND c.challenge_id=p_challenge AND c.tenant_id=p_tenant
        AND c.administrator_id=p_admin AND c.price_version_id=p_price
        AND c.document_id=d.id AND c.document_sha256=d.sha256
        AND c.session_id=r.session_id AND c.request_id=r.request_id
        AND r.tenant_id=p_tenant AND r.administrator_id=p_admin
        AND r.document_id=d.id AND r.document_sha256=d.sha256
        AND r.price_version_id=p_price
        AND r.confirmation_text='ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE'
        AND r.evidence_digest=p_digest
        AND r.recorded_at>=c.issued_at AND r.recorded_at<c.expires_at
        AND c.issued_at>=s.created_at
        AND r.recorded_at<=clock_timestamp()
        -- Fixture placeholder is intentionally not equal to new synthetic receipt.
        AND a.evidence_hash<>r.evidence_digest
    )
    OR EXISTS (
      SELECT 1 FROM public.saas_payment_intents i
      WHERE i.preparation_id=p_preparation
    )
    OR EXISTS (
      SELECT 1 FROM public.saas_license_entitlements l
      WHERE l.preparation_id=p_preparation
    )
  THEN RETURN 'DENIED_CI_UNATTESTED_OR_SCOPE_MISMATCH'; END IF;

  INSERT INTO public.saas_consent_preparation_links_m37456_ci (
    request_id,preparation_id,challenge_id,tenant_id,administrator_id,
    price_version_id,document_id,receipt_digest
  )
  SELECT p_request,p_preparation,p_challenge,p_tenant,p_admin,
         p_price,r.document_id,r.evidence_digest
    FROM public.saas_consent_receipts_m37455_ci r
    WHERE r.challenge_id=p_challenge
  ON CONFLICT DO NOTHING;

  GET DIAGNOSTICS inserted=ROW_COUNT;
  IF inserted=1 THEN RETURN 'LINKED_POST_PREPARATION_CI_UNATTESTED'; END IF;

  SELECT * INTO existing FROM public.saas_consent_preparation_links_m37456_ci
    WHERE request_id=p_request FOR UPDATE;
  IF FOUND AND existing.preparation_id=p_preparation
       AND existing.challenge_id=p_challenge
       AND existing.tenant_id=p_tenant
       AND existing.administrator_id=p_admin
       AND existing.price_version_id=p_price
       AND existing.receipt_digest=p_digest
       AND existing.evidence_state='POST_PREPARATION_CI_UNATTESTED'
       AND NOT existing.legal_consent_verified AND NOT existing.payment_authorized
       AND NOT existing.license_authorized AND NOT existing.real_activation_authorized
  THEN RETURN 'REPLAY_CI_NO_WRITE'; END IF;
  RETURN 'COLLISION_CI_DENIED';
END $m37456_function$;

REVOKE ALL ON FUNCTION public.m37456_link_consent_to_preparation_ci(
  uuid,uuid,uuid,uuid,uuid,uuid,text)
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_consent_ci;
GRANT EXECUTE ON FUNCTION public.m37456_link_consent_to_preparation_ci(
  uuid,uuid,uuid,uuid,uuid,uuid,text) TO frcaixinha_saas_consent_ci;
COMMIT;
