-- M32400-M32800: synthetic capacity claim. CI-only; NEVER Termux 5433 or OCI.
-- No real member/quota, charge, entitlement extension, Pix or ledger write.
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging' OR session_user<>'postgres'
 OR current_setting('is_superuser')<>'on'
 OR current_setting('frcaixinha.saas_claim_ci',true) IS DISTINCT FROM '1'
 OR NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_claim_ci'
 AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole)
 THEN RAISE EXCEPTION 'M32400_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.saas_capacity_claims_staging (
 request_id uuid PRIMARY KEY,
 hold_event_id uuid NOT NULL UNIQUE REFERENCES public.saas_capacity_events_staging(event_id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 admin_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 entitlement_id uuid NOT NULL REFERENCES public.saas_license_entitlements(id) ON DELETE RESTRICT,
 category varchar(10) NOT NULL CHECK(category IN ('MEMBER','QUOTA')),
 quantity integer NOT NULL CHECK(quantity BETWEEN 1 AND 100),
 claimed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 ci_only boolean NOT NULL DEFAULT true CHECK(ci_only),
 real_member_created boolean NOT NULL DEFAULT false CHECK(NOT real_member_created),
 real_quota_created boolean NOT NULL DEFAULT false CHECK(NOT real_quota_created),
 real_charge_created boolean NOT NULL DEFAULT false CHECK(NOT real_charge_created),
 real_ledger_changed boolean NOT NULL DEFAULT false CHECK(NOT real_ledger_changed)
);
CREATE INDEX saas_claim_tenant_idx_ci ON public.saas_capacity_claims_staging(tenant_id,claimed_at DESC);
ALTER TABLE public.saas_capacity_claims_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_capacity_claims_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_capacity_claims_staging FROM PUBLIC,frcaixinha_app_role,
frcaixinha_auth_role,frcaixinha_saas_claim_ci,frcaixinha_saas_capacity_ci;

CREATE FUNCTION public.saas_capacity_claim_ci(
 p_request uuid,p_tenant uuid,p_admin uuid,p_entitlement uuid,p_hold uuid,p_category varchar
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 locked_tenant uuid; old_claim record; held_event record;
 licensed uuid; limits record;
 members bigint; quotas bigint; held_members bigint; held_quotas bigint;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_claim_ci'
 OR current_setting('frcaixinha.saas_claim_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M32400_CI_WORKER_DENIED'; END IF;
 IF p_request IS NULL OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 OR p_tenant IS NULL OR p_admin IS NULL OR p_entitlement IS NULL OR p_hold IS NULL
 OR p_category IS NULL OR p_category NOT IN ('MEMBER','QUOTA')
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;

 -- Serializes with original HOLD/RELEASE functions and competing CLAIMs.
 SELECT t.id INTO locked_tenant FROM public.tenants t WHERE t.id=p_tenant FOR UPDATE;
 IF NOT FOUND OR NOT public.saas_capacity_actor_ci(p_tenant,p_admin)
 THEN RETURN jsonb_build_object('state','DENIED','real_authorized',false); END IF;

 SELECT * INTO old_claim FROM public.saas_capacity_claims_staging
 WHERE request_id=p_request FOR UPDATE;
 IF FOUND THEN
  IF old_claim.tenant_id=p_tenant AND old_claim.admin_user_id=p_admin
   AND old_claim.entitlement_id=p_entitlement AND old_claim.hold_event_id=p_hold
   AND old_claim.category=p_category
  THEN RETURN jsonb_build_object('state','REPLAY_CI_NO_REAL_CREATION','real_authorized',false); END IF;
  RETURN jsonb_build_object('state','REQUEST_COLLISION_DENIED','real_authorized',false);
 END IF;

 SELECT h.event_id,h.category,h.quantity,h.created_at INTO held_event
 FROM public.saas_capacity_events_staging h
 WHERE h.event_id=p_hold AND h.tenant_id=p_tenant AND h.admin_user_id=p_admin
 AND h.action='HOLD' AND h.category=p_category FOR UPDATE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','INVALID_HOLD','real_authorized',false); END IF;
 IF EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r
  WHERE r.action='RELEASE' AND r.related_hold_event_id=p_hold)
 THEN RETURN jsonb_build_object('state','RELEASED_HOLD_DENIED','real_authorized',false); END IF;
 IF EXISTS(SELECT 1 FROM public.saas_capacity_claims_staging c
  WHERE c.hold_event_id=p_hold)
 THEN RETURN jsonb_build_object('state','HOLD_ALREADY_CLAIMED','real_authorized',false); END IF;
 -- A stale reservation cannot be claimed while recovery is pending.
 IF held_event.created_at<=clock_timestamp()-interval '60 minutes'
 THEN RETURN jsonb_build_object('state','EXPIRED_HOLD_DENIED','real_authorized',false); END IF;

 -- Existing payment record is synthetic CI fixture, NOT provider verification.
 SELECT e.id INTO licensed FROM public.saas_license_entitlements e
 JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id
 JOIN public.saas_payment_intents i ON i.id=e.payment_intent_id
 JOIN public.saas_capacity_budgets_staging b ON b.tenant_id=e.tenant_id
 WHERE e.id=p_entitlement AND e.tenant_id=p_tenant
 AND s.tenant_id=p_tenant AND s.admin_user_id=p_admin AND i.tenant_id=p_tenant
 AND i.admin_user_id=p_admin AND i.preparation_id=s.id
 AND i.status='APPROVED' AND NOT i.live_mode
 AND e.plan_tier=b.plan_tier AND b.ci_only AND NOT b.production_enabled
 AND e.status='ACTIVE' AND e.valid_from<=clock_timestamp()
 AND e.valid_until>clock_timestamp();
 IF NOT FOUND THEN RETURN jsonb_build_object('state','LICENSE_UNVERIFIED','real_authorized',false); END IF;

 SELECT p.members_limit,p.quotas_limit,p.status INTO limits
 FROM public.saas_capacity_budgets_staging b
 JOIN public.platform_license_plans p ON p.tier=b.plan_tier
 WHERE b.tenant_id=p_tenant AND b.ci_only AND NOT b.production_enabled;
 IF NOT FOUND OR limits.status<>'ACTIVE'
 OR limits.members_limit IS NULL OR limits.quotas_limit IS NULL
 THEN RETURN jsonb_build_object('state','PLAN_UNVERIFIED','real_authorized',false); END IF;
 SELECT count(*) INTO members FROM public.memberships
 WHERE tenant_id=p_tenant AND role='TENANT_MEMBER' AND status='ATIVA';
 SELECT count(*) INTO quotas FROM public.quotas
 WHERE tenant_id=p_tenant AND status='ATIVA';
 SELECT coalesce(sum(h.quantity),0) INTO held_members FROM public.saas_capacity_events_staging h
 WHERE h.tenant_id=p_tenant AND h.category='MEMBER' AND h.action='HOLD'
 AND NOT EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r
 WHERE r.action='RELEASE' AND r.related_hold_event_id=h.event_id);
 SELECT coalesce(sum(h.quantity),0) INTO held_quotas FROM public.saas_capacity_events_staging h
 WHERE h.tenant_id=p_tenant AND h.category='QUOTA' AND h.action='HOLD'
 AND NOT EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r
 WHERE r.action='RELEASE' AND r.related_hold_event_id=h.event_id);
 -- Do not double-count this hold; it is already included in held_*.
 IF members+held_members>limits.members_limit OR quotas+held_quotas>limits.quotas_limit
 THEN RETURN jsonb_build_object('state','CAPACITY_EXCEEDED','real_authorized',false); END IF;

 INSERT INTO public.saas_capacity_claims_staging
 (request_id,hold_event_id,tenant_id,admin_user_id,entitlement_id,category,quantity)
 VALUES(p_request,p_hold,p_tenant,p_admin,p_entitlement,held_event.category,held_event.quantity);
 RETURN jsonb_build_object('state','CLAIMED_CI_NO_REAL_CREATION',
 'quantity',held_event.quantity,'category',held_event.category,
 'real_authorized',false,'real_member_created',false,
 'real_quota_created',false,'real_charge_created',false,'real_ledger_changed',false);
END $fn$;

-- Original RELEASE locks the same tenant row. Deny releasing claimed holds.
CREATE FUNCTION public.saas_claim_prevent_release_ci()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 IF NEW.action='RELEASE' AND EXISTS(
  SELECT 1 FROM public.saas_capacity_claims_staging c
  WHERE c.hold_event_id=NEW.related_hold_event_id
 ) THEN RAISE EXCEPTION 'M32700_CLAIMED_HOLD_RELEASE_DENIED'; END IF;
 RETURN NEW;
END $fn$;
CREATE TRIGGER saas_claim_release_guard_ci
 BEFORE INSERT ON public.saas_capacity_events_staging
 FOR EACH ROW EXECUTE FUNCTION public.saas_claim_prevent_release_ci();

CREATE FUNCTION public.saas_claim_immutable_ci()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN RAISE EXCEPTION 'M32800_IMMUTABLE_CLAIM_HISTORY'; END $fn$;
CREATE TRIGGER saas_claim_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_capacity_claims_staging
 FOR EACH ROW EXECUTE FUNCTION public.saas_claim_immutable_ci();
CREATE TRIGGER saas_claim_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_capacity_claims_staging
 FOR EACH STATEMENT EXECUTE FUNCTION public.saas_claim_immutable_ci();
REVOKE ALL ON FUNCTION
 public.saas_capacity_claim_ci(uuid,uuid,uuid,uuid,uuid,varchar),
 public.saas_claim_prevent_release_ci(),public.saas_claim_immutable_ci()
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_saas_claim_ci,frcaixinha_saas_capacity_ci;
GRANT EXECUTE ON FUNCTION public.saas_capacity_claim_ci(
 uuid,uuid,uuid,uuid,uuid,varchar) TO frcaixinha_saas_claim_ci;
COMMIT;
