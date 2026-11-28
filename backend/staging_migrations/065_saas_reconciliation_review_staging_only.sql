-- FR Finance M35900-M36300: CI-only append-only SaaS reconciliation review.
-- A candidate never confirms a payment or activates a license.
BEGIN;
DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'postgres'
 OR current_setting('is_superuser')<>'on'
 OR current_setting('frcaixinha.saas_review_ci',true) IS DISTINCT FROM '1'
 OR NOT EXISTS (SELECT 1 FROM pg_roles
   WHERE rolname='frcaixinha_saas_review_ci'
   AND NOT rolsuper AND NOT rolbypassrls AND NOT rolcreaterole AND NOT rolcreatedb)
 THEN RAISE EXCEPTION 'M35900_ONLY_DISPOSABLE_STAGING_CI'; END IF;
END $guard$;

CREATE TABLE public.saas_reconciliation_reviews_staging (
 id uuid PRIMARY KEY,
 payment_intent_id uuid NOT NULL REFERENCES public.saas_payment_intents(id),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id),
 provider_payment_id varchar(40) NOT NULL CHECK (provider_payment_id ~ '^[0-9]{1,40}$'),
 request_key varchar(100) NOT NULL UNIQUE CHECK (length(request_key)>=16),
 event_kind varchar(28) NOT NULL
   CHECK (event_kind IN ('GET_MATCH_CANDIDATE','REVERSAL_HOLD','PROVIDER_UNAVAILABLE_HOLD')),
 evidence_digest char(64) NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 ci_only boolean NOT NULL DEFAULT true CHECK (ci_only),
 provider_readback_live_attested boolean NOT NULL DEFAULT false
   CHECK (NOT provider_readback_live_attested),
 real_license_activated boolean NOT NULL DEFAULT false CHECK (NOT real_license_activated),
 real_payment_settled boolean NOT NULL DEFAULT false CHECK (NOT real_payment_settled),
 real_pix_authorized boolean NOT NULL DEFAULT false CHECK (NOT real_pix_authorized),
 UNIQUE(payment_intent_id,event_kind,evidence_digest)
);
CREATE INDEX saas_reviews_tenant_audit_ci ON public.saas_reconciliation_reviews_staging
 (tenant_id,payment_intent_id,created_at DESC);
ALTER TABLE public.saas_reconciliation_reviews_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_reconciliation_reviews_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.saas_reconciliation_reviews_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
      frcaixinha_saas_review_ci;

CREATE FUNCTION public.saas_reconciliation_review_ci(
 p_id uuid,p_payment uuid,p_tenant uuid,p_provider_id text,
 p_request_key text,p_kind text,p_evidence text
) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE stored record; prior record; locked_tenant uuid;
BEGIN
 IF current_database()<>'frcaixinha_staging'
 OR session_user<>'frcaixinha_saas_review_ci'
 OR current_setting('frcaixinha.saas_review_ci',true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M35900_REVIEW_WORKER_DENIED' USING ERRCODE='42501'; END IF;
 IF p_id IS NULL OR p_payment IS NULL OR p_tenant IS NULL
 OR p_provider_id !~ '^[0-9]{1,40}$'
 OR p_request_key !~ '^[A-Za-z0-9_-]{16,100}$'
 OR p_evidence !~ '^[0-9a-f]{64}$'
 OR p_kind NOT IN ('GET_MATCH_CANDIDATE','REVERSAL_HOLD','PROVIDER_UNAVAILABLE_HOLD')
 THEN RETURN jsonb_build_object('state','INVALID_SIMULATED_EVIDENCE',
   'activation_authorized',false); END IF;
 -- The same tenant row lock serializes candidate and reversal decisions.
 SELECT id INTO locked_tenant FROM public.tenants WHERE id=p_tenant FOR UPDATE;
 IF NOT FOUND THEN RETURN jsonb_build_object('state','TENANT_NOT_FOUND',
   'activation_authorized',false); END IF;
 SELECT id,tenant_id,provider_payment_id,status,live_mode,provider
 INTO stored FROM public.saas_payment_intents
 WHERE id=p_payment AND tenant_id=p_tenant FOR UPDATE;
 IF NOT FOUND OR stored.provider_payment_id IS DISTINCT FROM p_provider_id
 OR stored.provider<>'MERCADO_PAGO' OR stored.live_mode IS DISTINCT FROM false
 OR stored.status NOT IN ('PENDING','APPROVED')
 THEN RETURN jsonb_build_object('state','PAYMENT_SCOPE_OR_TEST_MODE_DENIED',
   'activation_authorized',false); END IF;
 SELECT * INTO prior FROM public.saas_reconciliation_reviews_staging
 WHERE id=p_id OR request_key=p_request_key FOR UPDATE;
 IF FOUND THEN
  IF prior.id=p_id AND prior.payment_intent_id=p_payment
   AND prior.tenant_id=p_tenant AND prior.provider_payment_id=p_provider_id
   AND prior.request_key=p_request_key AND prior.event_kind=p_kind
   AND prior.evidence_digest=p_evidence
  THEN RETURN jsonb_build_object('state','REPLAY_NO_FINANCIAL_WRITE',
   'activation_authorized',false); END IF;
  RETURN jsonb_build_object('state','REVIEW_REQUEST_COLLISION_DENIED',
   'activation_authorized',false);
 END IF;
 IF EXISTS (SELECT 1 FROM public.saas_reconciliation_reviews_staging
   WHERE payment_intent_id=p_payment AND event_kind=p_kind
    AND evidence_digest=p_evidence)
 THEN RETURN jsonb_build_object('state','DUPLICATE_EVIDENCE_DENIED',
   'activation_authorized',false); END IF;
 -- Once a reversal is seen, no subsequent "approved" candidate can
 -- override it. Recovery requires a NEW review flow, not a spoofed GET.
 IF p_kind='GET_MATCH_CANDIDATE' AND EXISTS (
   SELECT 1 FROM public.saas_reconciliation_reviews_staging
   WHERE payment_intent_id=p_payment AND event_kind='REVERSAL_HOLD'
 ) THEN RETURN jsonb_build_object('state','REVERSAL_HOLD_ACTIVE',
   'activation_authorized',false); END IF;
 INSERT INTO public.saas_reconciliation_reviews_staging
 (id,payment_intent_id,tenant_id,provider_payment_id,request_key,event_kind,evidence_digest)
 VALUES (p_id,p_payment,p_tenant,p_provider_id,p_request_key,p_kind,p_evidence);
 RETURN jsonb_build_object(
   'state',CASE WHEN p_kind='GET_MATCH_CANDIDATE' THEN 'READBACK_CANDIDATE_RECORDED_CI'
     ELSE 'HOLD_RECORDED_CI' END,
   'activation_authorized',false,'license_activated',false,
   'payment_settled',false,'pix_authorized',false);
END $fn$;

CREATE FUNCTION public.saas_review_immutable_ci()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN RAISE EXCEPTION 'M36200_REVIEW_APPEND_ONLY'; END $fn$;
CREATE TRIGGER saas_review_no_update_delete_ci
 BEFORE UPDATE OR DELETE ON public.saas_reconciliation_reviews_staging
 FOR EACH ROW EXECUTE FUNCTION public.saas_review_immutable_ci();
CREATE TRIGGER saas_review_no_truncate_ci
 BEFORE TRUNCATE ON public.saas_reconciliation_reviews_staging
 FOR EACH STATEMENT EXECUTE FUNCTION public.saas_review_immutable_ci();
REVOKE ALL ON FUNCTION public.saas_review_immutable_ci() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.saas_reconciliation_review_ci(
 uuid,uuid,uuid,text,text,text,text)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_saas_review_ci;
GRANT EXECUTE ON FUNCTION public.saas_reconciliation_review_ci(
 uuid,uuid,uuid,text,text,text,text) TO frcaixinha_saas_review_ci;
COMMIT;
