-- FR FINANCE M34400-M34800: CI-only verified member admission intent.
-- No production operation; no real user, membership, quota, invoice or Pix writes.
-- NEVER use on Termux 5433, OCI staging, or production.
BEGIN;
DO $guard$ BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'postgres'
 OR current_setting('is_superuser')<>'on'
 OR current_setting('frcaixinha.admission_intent_ci',true) IS DISTINCT FROM '1'
 OR NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_saas_admission_intent_ci'
  AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreatedb AND NOT rolcreaterole
 ) THEN RAISE EXCEPTION 'M34400_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.saas_member_admission_intents_staging (
 request_id uuid PRIMARY KEY,
 claim_id uuid NOT NULL UNIQUE REFERENCES public.saas_capacity_claims_staging(request_id) ON DELETE RESTRICT,
 invitation_id uuid NOT NULL UNIQUE REFERENCES public.invitations(id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 admin_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 target_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 document_id uuid NOT NULL REFERENCES public.contract_documents(id) ON DELETE RESTRICT,
 contract_acceptance_id uuid NOT NULL REFERENCES public.contract_acceptances(id) ON DELETE RESTRICT,
 email_proof_id uuid NOT NULL REFERENCES public.invite_email_verification(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 ci_only boolean NOT NULL DEFAULT true CHECK(ci_only),
 provider_readback_verified boolean NOT NULL DEFAULT false CHECK(NOT provider_readback_verified),
 real_member_created boolean NOT NULL DEFAULT false CHECK(NOT real_member_created),
 real_quota_created boolean NOT NULL DEFAULT false CHECK(NOT real_quota_created),
 real_charge_created boolean NOT NULL DEFAULT false CHECK(NOT real_charge_created),
 real_pix_enabled boolean NOT NULL DEFAULT false CHECK(NOT real_pix_enabled)
);
CREATE INDEX saas_admission_intent_tenant_ci
 ON public.saas_member_admission_intents_staging(tenant_id,created_at DESC);
ALTER TABLE public.saas_member_admission_intents_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_member_admission_intents_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_member_admission_intents_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_saas_admission_ci,frcaixinha_saas_admission_intent_ci;

CREATE FUNCTION public.saas_member_admission_intent_ci(
 p_request uuid,p_tenant uuid,p_admin uuid,p_target uuid,
 p_invitation uuid,p_document uuid,p_claim uuid,p_proof uuid
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE t uuid; old record; user_data record; invite_data record;
 license_data record; limits record; count_members bigint; count_quotas bigint;
 remaining_members bigint; remaining_quotas bigint; doc_acceptance uuid;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_admission_intent_ci'
 OR current_setting('frcaixinha.admission_intent_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M34400_WORKER_DENIED' USING ERRCODE='42501'; END IF;

 IF p_request IS NULL OR p_request='00000000-0000-0000-0000-000000000000'::uuid
 OR p_tenant IS NULL OR p_admin IS NULL OR p_target IS NULL
 OR p_invitation IS NULL OR p_document IS NULL OR p_claim IS NULL OR p_proof IS NULL
 OR p_target=p_admin
 THEN RETURN jsonb_build_object('state','INVALID_ARGUMENTS','activation_authorized',false); END IF;

 -- Lock tenant BEFORE checking request replay, invite and capacity.
 -- All capacity HOLD/CLAIM/RELEASE operations use the same lock.
 SELECT id INTO t FROM public.tenants WHERE id=p_tenant FOR UPDATE;
 IF NOT FOUND OR NOT public.saas_capacity_actor_ci(p_tenant,p_admin)
 THEN RETURN jsonb_build_object('state','ACTOR_DENIED','activation_authorized',false); END IF;

 SELECT * INTO old FROM public.saas_member_admission_intents_staging
 WHERE request_id=p_request FOR UPDATE;
 IF FOUND THEN
   IF old.tenant_id=p_tenant AND old.admin_user_id=p_admin
   AND old.target_user_id=p_target AND old.invitation_id=p_invitation
   AND old.document_id=p_document AND old.claim_id=p_claim
   AND old.email_proof_id=p_proof
   THEN RETURN jsonb_build_object('state','REPLAY_CI_NO_ACTIVATION','activation_authorized',false); END IF;
   RETURN jsonb_build_object('state','REQUEST_COLLISION_DENIED','activation_authorized',false);
 END IF;

 IF EXISTS (
  SELECT 1 FROM public.saas_member_admission_intents_staging
  WHERE claim_id=p_claim OR invitation_id=p_invitation
 ) THEN RETURN jsonb_build_object('state','PROOF_OR_CAPACITY_ALREADY_USED','activation_authorized',false); END IF;

 -- Only a previously established, active, synthetically reconciled license.
 -- A DB record is NOT independent payment-provider confirmation.
 SELECT c.request_id,c.hold_event_id,c.entitlement_id,c.quantity,
        e.valid_until,e.plan_tier
 INTO license_data
 FROM public.saas_capacity_claims_staging c
 JOIN public.saas_license_entitlements e
  ON e.id=c.entitlement_id AND e.tenant_id=c.tenant_id
 JOIN public.saas_subscription_preparations s
  ON s.id=e.preparation_id AND s.tenant_id=c.tenant_id
  AND s.plan_tier=e.plan_tier AND s.admin_user_id=c.admin_user_id
 JOIN public.saas_payment_intents i
  ON i.id=e.payment_intent_id AND i.tenant_id=c.tenant_id
  AND i.admin_user_id=c.admin_user_id AND i.preparation_id=s.id
 JOIN public.saas_capacity_budgets_staging b
  ON b.tenant_id=c.tenant_id AND b.plan_tier=e.plan_tier
 WHERE c.request_id=p_claim AND c.tenant_id=p_tenant
  AND c.admin_user_id=p_admin AND c.category='MEMBER'
  AND c.quantity=1 AND c.ci_only AND NOT c.real_member_created
  AND NOT c.real_quota_created AND NOT c.real_charge_created
  AND b.ci_only AND NOT b.production_enabled
  AND e.status='ACTIVE' AND e.valid_from<=clock_timestamp()
  AND e.valid_until>clock_timestamp()
  AND i.status='APPROVED' AND i.reconciled_at IS NOT NULL
  AND NOT i.live_mode
 FOR UPDATE OF c;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','LICENSE_OR_MEMBER_CLAIM_DENIED','activation_authorized',false); END IF;

 -- Explicit target identity, delivered invitation, ownership challenge,
 -- contract acceptance all must point to SAME tenant and target. No CPF leak.
 SELECT u.email,u.is_master INTO user_data FROM public.users u
 WHERE u.id=p_target AND u.status='ACTIVE'
 AND u.email_verified_at IS NOT NULL
 AND u.email_verified_at<=clock_timestamp();
 IF NOT FOUND OR user_data.is_master
 THEN RETURN jsonb_build_object('state','IDENTITY_DENIED','activation_authorized',false); END IF;
 IF EXISTS(SELECT 1 FROM public.memberships m WHERE m.tenant_id=p_tenant
  AND m.user_id=p_target AND m.role='TENANT_MEMBER'
  AND m.status IN ('ATIVA','SUSPENSA'))
 THEN RETURN jsonb_build_object('state','ALREADY_MEMBER_DENIED','activation_authorized',false); END IF;

 SELECT id,target_email INTO invite_data FROM public.invitations
 WHERE id=p_invitation AND tenant_id=p_tenant AND inviter_user_id=p_admin
  AND target_role='TENANT_MEMBER' AND required_document_id=p_document
  AND delivery_status='DELIVERED' AND delivered_at IS NOT NULL
  AND delivered_at<=clock_timestamp()
  AND expires_at>clock_timestamp() AND accepted_at IS NULL
  AND revoked_at IS NULL FOR UPDATE;
 IF NOT FOUND OR lower(invite_data.target_email)<>lower(user_data.email)
 THEN RETURN jsonb_build_object('state','INVITATION_DENIED','activation_authorized',false); END IF;

 IF NOT EXISTS (
  SELECT 1 FROM public.invite_email_verification v
  WHERE v.id=p_proof AND v.invitation_id=p_invitation
   AND lower(v.recipient_email)=lower(user_data.email)
   AND v.consumed_at IS NOT NULL AND v.revoked_at IS NULL
   AND v.consumed_at>=v.created_at AND v.consumed_at<=v.expires_at
   AND v.consumed_at<=clock_timestamp()
 ) THEN RETURN jsonb_build_object('state','EMAIL_OWNERSHIP_DENIED','activation_authorized',false); END IF;

 SELECT a.id INTO doc_acceptance
 FROM public.contract_acceptances a
 JOIN public.contract_documents d ON d.id=a.document_id
 WHERE a.document_id=p_document AND a.document_kind='TENANT_MEMBERSHIP'
  AND a.tenant_id=p_tenant AND a.user_id=p_target
  AND a.evidence_method='CI_VERIFIED_IDENTITY'
  AND a.evidence_hash ~ '^[0-9a-f]{64}$'
  AND d.document_kind='TENANT_MEMBERSHIP'
  AND d.published_at IS NOT NULL AND d.published_at<=clock_timestamp()
  AND a.accepted_at>=d.published_at
 LIMIT 1;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','CONTRACT_DENIED','activation_authorized',false); END IF;

 SELECT p.members_limit,p.quotas_limit INTO limits
 FROM public.platform_license_plans p WHERE p.tier=license_data.plan_tier
 AND p.status='ACTIVE' AND p.members_limit>0 AND p.quotas_limit>0;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','PLAN_DENIED','activation_authorized',false); END IF;

 SELECT count(*) INTO count_members FROM public.memberships
 WHERE tenant_id=p_tenant AND role='TENANT_MEMBER' AND status='ATIVA';
 SELECT count(*) INTO count_quotas FROM public.quotas
 WHERE tenant_id=p_tenant AND status='ATIVA';
 SELECT coalesce(sum(h.quantity),0) INTO remaining_members
 FROM public.saas_capacity_events_staging h
 WHERE h.tenant_id=p_tenant AND h.category='MEMBER' AND h.action='HOLD'
 AND NOT EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r
  WHERE r.action='RELEASE' AND r.related_hold_event_id=h.event_id);
 SELECT coalesce(sum(h.quantity),0) INTO remaining_quotas
 FROM public.saas_capacity_events_staging h
 WHERE h.tenant_id=p_tenant AND h.category='QUOTA' AND h.action='HOLD'
 AND NOT EXISTS(SELECT 1 FROM public.saas_capacity_events_staging r
  WHERE r.action='RELEASE' AND r.related_hold_event_id=h.event_id);
 IF count_members+remaining_members>limits.members_limit
 OR count_quotas+remaining_quotas>limits.quotas_limit
 THEN RETURN jsonb_build_object('state','CAPACITY_DENIED','activation_authorized',false); END IF;

 INSERT INTO public.saas_member_admission_intents_staging
 (request_id,claim_id,invitation_id,tenant_id,admin_user_id,target_user_id,
  document_id,contract_acceptance_id,email_proof_id)
 VALUES(p_request,p_claim,p_invitation,p_tenant,p_admin,p_target,
  p_document,doc_acceptance,p_proof);
 RETURN jsonb_build_object('state','VERIFIED_INTENT_CI_NO_ACTIVATION',
  'activation_authorized',false,'provider_verified_live',false,
  'membership_created',false,'quota_created',false,'pix_enabled',false);
END $fn$;

CREATE FUNCTION public.saas_admission_intent_immutable_ci()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN RAISE EXCEPTION 'M34700_ADMISSION_INTENT_IMMUTABLE'; END $fn$;
CREATE TRIGGER saas_admission_intent_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_member_admission_intents_staging
 FOR EACH ROW EXECUTE FUNCTION public.saas_admission_intent_immutable_ci();
CREATE TRIGGER saas_admission_intent_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_member_admission_intents_staging
 FOR EACH STATEMENT EXECUTE FUNCTION public.saas_admission_intent_immutable_ci();
REVOKE ALL ON FUNCTION public.saas_member_admission_intent_ci(
 uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid),
 public.saas_admission_intent_immutable_ci()
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_saas_admission_ci,frcaixinha_saas_admission_intent_ci;
GRANT EXECUTE ON FUNCTION public.saas_member_admission_intent_ci(
 uuid,uuid,uuid,uuid,uuid,uuid,uuid,uuid)
 TO frcaixinha_saas_admission_intent_ci;
COMMIT;
