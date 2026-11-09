-- FR Finance M31900-M32300. ONLY frcaixinha_staging disposable GitHub CI.
-- NEVER Termux 5433 or OCI. REVIEW != payment or entitlement extension.
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
 OR current_setting('is_superuser')<>'on'
 OR current_setting('frcaixinha.saas_renewal_ci',true) IS DISTINCT FROM '1'
 OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_renewal_ci'
  AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M32300_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;
CREATE TABLE public.saas_renewal_reviews_staging (
 request_id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 admin_user_id uuid NOT NULL REFERENCES public.users(id),
 entitlement_id uuid NOT NULL REFERENCES public.saas_license_entitlements(id),
 price_version_id uuid NOT NULL REFERENCES public.platform_license_price_versions(id),
 acceptance_id uuid NOT NULL REFERENCES public.contract_acceptances(id),
 billing_period varchar(10) NOT NULL CHECK(billing_period IN ('MONTHLY','ANNUAL')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 real_charge_created boolean NOT NULL DEFAULT false CHECK(NOT real_charge_created),
 entitlement_extended boolean NOT NULL DEFAULT false CHECK(NOT entitlement_extended),
 UNIQUE(tenant_id,entitlement_id,billing_period)
);
ALTER TABLE public.saas_renewal_reviews_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_renewal_reviews_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_renewal_reviews_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_renewal_ci;
CREATE FUNCTION public.saas_renewal_review_ci(
 p_request uuid,p_tenant uuid,p_admin uuid,p_entitlement uuid,
 p_price uuid,p_acceptance uuid,p_period varchar
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE locked uuid; prev record; e record; offer record;
 members bigint; quotas bigint; held_m bigint; held_q bigint;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_renewal_ci'
 OR current_setting('frcaixinha.saas_renewal_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M32300_CI_ROLE_DENIED'; END IF;
 IF p_request IS NULL OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 OR p_tenant IS NULL OR p_admin IS NULL OR p_entitlement IS NULL OR p_price IS NULL
 OR p_acceptance IS NULL OR p_period NOT IN ('MONTHLY','ANNUAL')
 THEN RETURN jsonb_build_object('state','DENIED','charge_authorized',false); END IF;
 SELECT t.id INTO locked FROM public.tenants t WHERE t.id=p_tenant FOR UPDATE;
 IF NOT FOUND OR NOT public.saas_capacity_actor_ci(p_tenant,p_admin)
 THEN RETURN jsonb_build_object('state','DENIED','charge_authorized',false); END IF;
 SELECT * INTO prev FROM public.saas_renewal_reviews_staging
 WHERE request_id=p_request FOR UPDATE;
 IF FOUND THEN
  IF prev.tenant_id=p_tenant AND prev.admin_user_id=p_admin
   AND prev.entitlement_id=p_entitlement AND prev.price_version_id=p_price
   AND prev.acceptance_id=p_acceptance AND prev.billing_period=p_period
  THEN RETURN jsonb_build_object('state','REPLAY_CI_NO_CHARGE','charge_authorized',false); END IF;
  RETURN jsonb_build_object('state','REQUEST_COLLISION_DENIED','charge_authorized',false);
 END IF;
 SELECT e.id INTO e FROM public.saas_license_entitlements e
 JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id
 JOIN public.saas_payment_intents i ON i.id=e.payment_intent_id
 WHERE e.id=p_entitlement AND e.tenant_id=p_tenant AND s.tenant_id=p_tenant
 AND s.admin_user_id=p_admin AND i.tenant_id=p_tenant AND i.admin_user_id=p_admin
 AND i.preparation_id=s.id AND i.status='APPROVED' AND NOT i.live_mode
 AND e.status='ACTIVE' AND e.valid_from<=clock_timestamp()
 AND e.valid_until>clock_timestamp();
 IF NOT FOUND THEN RETURN jsonb_build_object('state','LICENSE_UNVERIFIED','charge_authorized',false); END IF;
 SELECT v.plan_tier,p.status,p.members_limit,p.quotas_limit,v.monthly_price,v.annual_price
 INTO offer FROM public.platform_license_price_versions v
 JOIN public.platform_license_plans p ON p.tier=v.plan_tier WHERE v.id=p_price;
 IF NOT FOUND OR offer.status<>'ACTIVE' OR offer.members_limit IS NULL
 OR offer.quotas_limit IS NULL OR offer.monthly_price<=0 OR offer.annual_price<=0
 THEN RETURN jsonb_build_object('state','OFFER_UNVERIFIED','charge_authorized',false); END IF;
 IF NOT EXISTS(SELECT 1 FROM public.contract_acceptances a
 JOIN public.contract_documents d ON d.id=a.document_id
 WHERE a.id=p_acceptance AND a.user_id=p_admin AND a.tenant_id IS NULL
 AND a.document_kind='PLATFORM_LICENSE' AND d.document_kind='PLATFORM_LICENSE'
 AND d.published_at IS NOT NULL AND a.accepted_at>=d.published_at
 AND a.evidence_hash ~ '^[0-9a-f]{64}$')
 THEN RETURN jsonb_build_object('state','CONSENT_UNVERIFIED','charge_authorized',false); END IF;
 SELECT count(*) INTO members FROM public.memberships
 WHERE tenant_id=p_tenant AND role='TENANT_MEMBER' AND status='ATIVA';
 SELECT count(*) INTO quotas FROM public.quotas
 WHERE tenant_id=p_tenant AND status='ATIVA';
 SELECT coalesce(sum(h.quantity),0) INTO held_m FROM public.saas_capacity_events_staging h
 WHERE h.tenant_id=p_tenant AND h.category='MEMBER' AND h.action='HOLD'
 AND NOT EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r
 WHERE r.action='RELEASE' AND r.related_hold_event_id=h.event_id);
 SELECT coalesce(sum(h.quantity),0) INTO held_q FROM public.saas_capacity_events_staging h
 WHERE h.tenant_id=p_tenant AND h.category='QUOTA' AND h.action='HOLD'
 AND NOT EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r
 WHERE r.action='RELEASE' AND r.related_hold_event_id=h.event_id);
 IF members+held_m>offer.members_limit OR quotas+held_q>offer.quotas_limit
 THEN RETURN jsonb_build_object('state','RENEWAL_UNDERCAPACITY','charge_authorized',false); END IF;
 IF EXISTS(SELECT 1 FROM public.saas_renewal_reviews_staging
 WHERE tenant_id=p_tenant AND entitlement_id=p_entitlement AND billing_period=p_period)
 THEN RETURN jsonb_build_object('state','DUPLICATE_TERM_DENIED','charge_authorized',false); END IF;
 INSERT INTO public.saas_renewal_reviews_staging
 (request_id,tenant_id,admin_user_id,entitlement_id,price_version_id,acceptance_id,billing_period)
 VALUES (p_request,p_tenant,p_admin,p_entitlement,p_price,p_acceptance,p_period);
 RETURN jsonb_build_object('state','RENEWAL_REVIEW_CI_NO_CHARGE',
 'charge_authorized',false,'entitlement_authorized',false);
END $fn$;
CREATE FUNCTION public.saas_renewal_immutable_ci()
RETURNS trigger LANGUAGE plpgsql AS $fn$
BEGIN RAISE EXCEPTION 'M32300_APPEND_ONLY'; END $fn$;
CREATE TRIGGER saas_renewal_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_renewal_reviews_staging
 FOR EACH ROW EXECUTE FUNCTION public.saas_renewal_immutable_ci();
REVOKE ALL ON FUNCTION public.saas_renewal_review_ci(
 uuid,uuid,uuid,uuid,uuid,uuid,varchar),public.saas_renewal_immutable_ci()
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_renewal_ci;
GRANT EXECUTE ON FUNCTION public.saas_renewal_review_ci(
 uuid,uuid,uuid,uuid,uuid,uuid,varchar) TO frcaixinha_saas_renewal_ci;
COMMIT;
