-- FR Finance M30900-M31300 -- SaaS enrollment in disposable PostgreSQL CI ONLY.
-- NOT FOR TERMUX 5433, OCI STAGING, PRODUCTION OR REAL CLIENTS.
-- A committed preparation is NOT an invoice, payment, entitlement, or income.
BEGIN;
DO $guard$
BEGIN
 IF current_database() <> 'frcaixinha_staging'
 OR session_user <> 'postgres'
 OR current_setting('is_superuser') <> 'on'
 OR current_setting('frcaixinha.saas_enroll_staging_ci',true) IS DISTINCT FROM '1'
 OR NOT EXISTS(
  SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_enroll_ci'
  AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 )
 THEN RAISE EXCEPTION 'M30900_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.saas_enrollment_requests_staging (
 request_id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 admin_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 price_version_id uuid NOT NULL REFERENCES public.platform_license_price_versions(id),
 contract_acceptance_id uuid NOT NULL REFERENCES public.contract_acceptances(id),
 billing_period varchar(10) NOT NULL CHECK(billing_period IN ('MONTHLY','ANNUAL')),
 preparation_id uuid NOT NULL UNIQUE REFERENCES public.saas_subscription_preparations(id),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 payment_created boolean NOT NULL DEFAULT false CHECK (NOT payment_created),
 entitlement_created boolean NOT NULL DEFAULT false CHECK (NOT entitlement_created)
);
ALTER TABLE public.saas_enrollment_requests_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_enrollment_requests_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_enrollment_requests_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_enroll_ci;

CREATE FUNCTION public.saas_prepare_enrollment_staging_ci(
 p_request uuid,p_tenant uuid,p_admin uuid,p_price uuid,p_acceptance uuid,
 p_period varchar
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 t record; offer record; existing record; existing_prep uuid; new_prep uuid;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_enroll_ci'
 OR current_setting('frcaixinha.saas_enroll_staging_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M30900_CI_ROLE_DENIED'; END IF;

 IF p_request IS NULL OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 OR p_tenant IS NULL OR p_admin IS NULL OR p_price IS NULL OR p_acceptance IS NULL
 OR p_period IS NULL OR p_period NOT IN ('MONTHLY','ANNUAL')
 THEN RETURN jsonb_build_object('state','DENIED','billing_authorized',false); END IF;

 -- Tenant row lock serializes concurrent requests for the same box, including
 -- different request IDs. No app/client role has direct INSERT privileges.
 SELECT t1.admin_user_id,t1.status INTO t FROM public.tenants t1
 WHERE t1.id=p_tenant FOR UPDATE;
 IF NOT FOUND OR t.status<>'ATIVO' OR t.admin_user_id<>p_admin
 OR NOT EXISTS(
  SELECT 1 FROM public.users u WHERE u.id=p_admin AND u.status='ACTIVE'
 )
 OR NOT EXISTS(
  SELECT 1 FROM public.memberships m WHERE m.tenant_id=p_tenant
  AND m.user_id=p_admin AND m.role='TENANT_ADMIN' AND m.status='ATIVA'
 )
 THEN RETURN jsonb_build_object('state','DENIED','billing_authorized',false); END IF;

 -- The acceptance must be by this admin, of a published PLATFORM_LICENSE
 -- document. A tenant membership acceptance is not a platform SaaS license.
 IF NOT EXISTS(
  SELECT 1 FROM public.contract_acceptances a
  JOIN public.contract_documents d ON d.id=a.document_id
    AND d.document_kind='PLATFORM_LICENSE'
    AND d.published_at IS NOT NULL AND d.published_at<=clock_timestamp()
  WHERE a.id=p_acceptance AND a.user_id=p_admin
    AND a.document_kind='PLATFORM_LICENSE' AND a.tenant_id IS NULL
    AND a.accepted_at>=d.published_at
    AND a.evidence_hash ~ '^[0-9a-f]{64}$'
 )
 THEN RETURN jsonb_build_object('state','DENIED','billing_authorized',false); END IF;

 SELECT v.plan_tier,p.status AS plan_status,v.monthly_price,v.annual_price
 INTO offer FROM public.platform_license_price_versions v
 JOIN public.platform_license_plans p ON p.tier=v.plan_tier
 WHERE v.id=p_price;
 IF NOT FOUND OR offer.plan_status<>'ACTIVE'
 OR offer.monthly_price<=0 OR offer.annual_price<=0
 OR offer.monthly_price IS NULL OR offer.annual_price IS NULL
 THEN RETURN jsonb_build_object('state','DENIED','billing_authorized',false); END IF;

 SELECT * INTO existing FROM public.saas_enrollment_requests_staging
 WHERE request_id=p_request FOR UPDATE;
 IF FOUND THEN
  IF existing.tenant_id=p_tenant AND existing.admin_user_id=p_admin
   AND existing.price_version_id=p_price
   AND existing.contract_acceptance_id=p_acceptance
   AND existing.billing_period=p_period
   AND EXISTS(
     SELECT 1 FROM public.saas_subscription_preparations s
     WHERE s.id=existing.preparation_id AND s.tenant_id=p_tenant
       AND s.admin_user_id=p_admin AND s.status='PENDING_PAYMENT'
   ) THEN
   RETURN jsonb_build_object('state','REPLAY_CI_NO_PAYMENT',
     'preparation_id',existing.preparation_id,'billing_authorized',false);
  END IF;
  RETURN jsonb_build_object('state','DENIED','billing_authorized',false);
 END IF;

 SELECT s.id INTO existing_prep
 FROM public.saas_subscription_preparations s
 WHERE s.tenant_id=p_tenant AND s.admin_user_id=p_admin
 AND s.contract_acceptance_id=p_acceptance
 FOR UPDATE;
 IF FOUND THEN
  RETURN jsonb_build_object('state','EXISTING_PREPARATION_REQUIRES_REVIEW',
    'billing_authorized',false);
 END IF;

 INSERT INTO public.saas_subscription_preparations
 (tenant_id,admin_user_id,plan_tier,price_version_id,billing_period,
  contract_acceptance_id,status)
 VALUES(p_tenant,p_admin,offer.plan_tier,p_price,p_period,p_acceptance,'PENDING_PAYMENT')
 RETURNING id INTO new_prep;
 INSERT INTO public.saas_enrollment_requests_staging
 (request_id,tenant_id,admin_user_id,price_version_id,contract_acceptance_id,
  billing_period,preparation_id)
 VALUES(p_request,p_tenant,p_admin,p_price,p_acceptance,p_period,new_prep);
 RETURN jsonb_build_object('state','PREPARED_CI_NO_PAYMENT',
  'preparation_id',new_prep,'billing_authorized',false,
  'real_user_activated',false,'real_pix_enabled',false);
END $fn$;

CREATE FUNCTION public.saas_enrollment_immutable_staging_ci()
RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN RAISE EXCEPTION 'M30900_APPEND_ONLY_CI'; END $fn$;
CREATE TRIGGER saas_enrollment_no_update_delete_staging_ci
 BEFORE UPDATE OR DELETE ON public.saas_enrollment_requests_staging
 FOR EACH ROW EXECUTE FUNCTION public.saas_enrollment_immutable_staging_ci();

REVOKE ALL ON FUNCTION public.saas_prepare_enrollment_staging_ci(
 uuid,uuid,uuid,uuid,uuid,varchar)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_enroll_ci;
REVOKE ALL ON FUNCTION public.saas_enrollment_immutable_staging_ci()
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_enroll_ci;
GRANT EXECUTE ON FUNCTION public.saas_prepare_enrollment_staging_ci(
 uuid,uuid,uuid,uuid,uuid,varchar) TO frcaixinha_saas_enroll_ci;
COMMIT;
