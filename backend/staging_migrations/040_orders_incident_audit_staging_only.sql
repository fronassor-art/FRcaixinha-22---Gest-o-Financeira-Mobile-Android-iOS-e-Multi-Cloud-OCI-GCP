-- AI Studio M13100-M14000: append-only incident AUDIT staging proposal.
-- NEVER run on Termux, live OCI or production without separate approval.
-- The GitHub Actions harness applies this only to frcaixinha_staging,
-- cloned from 100% synthetic frcaixinha_ci. Actor/bank claims are UNVERIFIED.
-- Does not release hold, post ledger, mark paid, settle or call a provider.
BEGIN;

DO $guard$
BEGIN
 IF current_database() <> 'frcaixinha_staging'
    OR current_setting('frcaixinha.orders_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser') <> 'on'
    OR session_user <> 'postgres'
    OR NOT EXISTS(
        SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_mp_financial_worker'
         AND NOT rolsuper AND NOT rolbypassrls
    )
    OR to_regclass('public.mp_orders_reconciliation_holds_staging') IS NULL
    OR to_regclass('public.mp_pix_collection_operations_staging') IS NULL
    OR to_regprocedure('public.mp_orders_staging_record_hold(uuid,character varying,character varying,character varying)') IS NULL
 THEN
   RAISE EXCEPTION 'M040 DENIED: disposable CI/staging, M039 and DBA guard required';
 END IF;
END $guard$;

CREATE TABLE public.mp_orders_incident_audit_staging (
 tenant_id uuid NOT NULL,
 operation_id varchar(64) NOT NULL,
 reason_code varchar(40) NOT NULL,
 sequence integer NOT NULL CHECK(sequence BETWEEN 1 AND 1000),
 event_kind varchar(40) NOT NULL CHECK(event_kind IN(
   'OPENED','EVIDENCE_REVIEW_REQUESTED','SECURITY_ESCALATED',
   'DUAL_REVIEW_CLAIMED'
 )),
 claim_sha256 char(64) NOT NULL CHECK(claim_sha256 ~ '^[a-f0-9]{64}$'),
 previous_sha256 char(64) NOT NULL CHECK(previous_sha256 ~ '^[a-f0-9]{64}$'),
 event_sha256 char(64) NOT NULL CHECK(event_sha256 ~ '^[a-f0-9]{64}$'),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 hold_active boolean NOT NULL DEFAULT true CHECK(hold_active=true),
 operator_authenticated boolean NOT NULL DEFAULT false
   CHECK(operator_authenticated=false),
 bank_reconciled boolean NOT NULL DEFAULT false CHECK(bank_reconciled=false),
 financial_effect_applied boolean NOT NULL DEFAULT false
   CHECK(financial_effect_applied=false),
 ledger_written boolean NOT NULL DEFAULT false CHECK(ledger_written=false),
 payout_authorized boolean NOT NULL DEFAULT false
   CHECK(payout_authorized=false),
 PRIMARY KEY(tenant_id,operation_id,reason_code,sequence),
 UNIQUE(tenant_id,operation_id,reason_code,event_sha256),
 UNIQUE(tenant_id,operation_id,reason_code,previous_sha256,event_kind,claim_sha256),
 FOREIGN KEY(tenant_id,operation_id,reason_code)
  REFERENCES public.mp_orders_reconciliation_holds_staging(
    tenant_id,operation_id,reason_code
  ) ON DELETE RESTRICT
);

CREATE INDEX mp_orders_incident_audit_by_time
 ON public.mp_orders_incident_audit_staging(tenant_id,recorded_at DESC);

ALTER TABLE public.mp_orders_incident_audit_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_orders_incident_audit_staging FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.mp_orders_incident_audit_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_financial_worker,
 frcaixinha_mp_webhook_ingest;

CREATE OR REPLACE FUNCTION public.mp_orders_incident_audit_reject_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY INVOKER
SET search_path=pg_catalog,public,pg_temp AS $reject$
BEGIN
 RAISE EXCEPTION 'M040 DENIED: audit is append-only, no UPDATE/DELETE/TRUNCATE';
END $reject$;

CREATE TRIGGER mp_orders_incident_audit_immutable_row
 BEFORE UPDATE OR DELETE ON public.mp_orders_incident_audit_staging
 FOR EACH ROW EXECUTE FUNCTION public.mp_orders_incident_audit_reject_mutation();

CREATE TRIGGER mp_orders_incident_audit_immutable_truncate
 BEFORE TRUNCATE ON public.mp_orders_incident_audit_staging
 FOR EACH STATEMENT EXECUTE FUNCTION public.mp_orders_incident_audit_reject_mutation();

CREATE OR REPLACE FUNCTION public.mp_orders_staging_append_incident_audit(
 p_tenant uuid,p_operation varchar,p_reason varchar,
 p_event_kind varchar,p_claim_sha256 varchar,p_previous_sha256 varchar
) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE
 last_seq integer;
 last_digest char(64);
 old_digest char(64);
 next_digest text;
 last_previous char(64);
 last_kind varchar(40);
 last_claim char(64);
 next_seq integer;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_financial_worker'
    OR p_tenant IS NULL OR p_tenant='00000000-0000-0000-0000-000000000000'::uuid
    OR p_operation IS NULL OR p_operation !~ '^P_[a-f0-9]{32}$'
    OR p_reason IS NULL OR p_reason NOT IN (
      'TIMEOUT_UNKNOWN','PROVIDER_MISMATCH','BANK_MISSING',
      'FEE_MISMATCH','ORDER_REPLAY','REVERSAL_PENDING',
      'STATEMENT_DUPLICATE','STATUS_CONFLICT','SELLER_REVOKED')
    OR p_event_kind IS NULL OR p_event_kind NOT IN (
      'OPENED','EVIDENCE_REVIEW_REQUESTED','SECURITY_ESCALATED',
      'DUAL_REVIEW_CLAIMED')
    OR p_claim_sha256 IS NULL OR p_claim_sha256 !~ '^[a-f0-9]{64}$'
    OR p_previous_sha256 IS NULL OR p_previous_sha256 !~ '^[a-f0-9]{64}$'
    OR NOT EXISTS(
      SELECT 1 FROM public.mp_orders_reconciliation_holds_staging h
      JOIN public.mp_pix_collection_operations_staging op
        ON op.tenant_id=h.tenant_id AND op.operation_id=h.operation_id
      WHERE h.tenant_id=p_tenant AND h.operation_id=p_operation
        AND h.reason_code=p_reason AND op.environment='HOMOLOGACAO'
        AND h.hold_active IS DISTINCT FROM false
    )
 THEN
   RAISE EXCEPTION 'M040 DENIED: unauthenticated or unscoped incident append';
 END IF;

 PERFORM pg_advisory_xact_lock(pg_catalog.hashtextextended(
   'FRC-M040|'||p_tenant||'|'||p_operation||'|'||p_reason,0
 ));

 SELECT a.sequence,a.event_sha256,a.previous_sha256,
        a.event_kind,a.claim_sha256
 INTO last_seq,last_digest,last_previous,last_kind,last_claim
 FROM public.mp_orders_incident_audit_staging a
 WHERE a.tenant_id=p_tenant AND a.operation_id=p_operation
   AND a.reason_code=p_reason
 ORDER BY a.sequence DESC LIMIT 1 FOR UPDATE;

 -- Same last event and same predecessor is a harmless replay. Distinct
 -- predecessors cannot bypass the chain and cannot create a second payment.
 IF FOUND AND p_previous_sha256=last_previous
    AND p_event_kind=last_kind AND p_claim_sha256=last_claim THEN
   RETURN 'REPLAY:'||last_digest;
 END IF;

 IF NOT FOUND THEN
   IF p_previous_sha256<>repeat('0',64) THEN
     RAISE EXCEPTION 'M040 DENIED: invalid genesis';
   END IF;
   next_seq:=1;
 ELSE
   IF p_previous_sha256<>last_digest THEN
     RAISE EXCEPTION 'M040 DENIED: stale or forged predecessor';
   END IF;
   next_seq:=last_seq+1;
 END IF;
 IF next_seq>1000 THEN
   RAISE EXCEPTION 'M040 DENIED: sequence limit';
 END IF;

 next_digest:=encode(sha256(convert_to(
    concat_ws('|','AI_STUDIO_M040_UNVERIFIED_DB_HASH_V1',p_tenant,
      p_operation,p_reason,next_seq,p_event_kind,
      p_claim_sha256,p_previous_sha256,'HOLD_REMAINS_NO_FINANCIAL_EFFECT'),
    'UTF8')),'hex');

 INSERT INTO public.mp_orders_incident_audit_staging(
   tenant_id,operation_id,reason_code,sequence,event_kind,
   claim_sha256,previous_sha256,event_sha256
 ) VALUES(
   p_tenant,p_operation,p_reason,next_seq,p_event_kind,
   p_claim_sha256,p_previous_sha256,next_digest
 );
 RETURN 'NEW:'||next_digest;
END $fn$;

REVOKE ALL ON FUNCTION public.mp_orders_staging_append_incident_audit(
 uuid,varchar,varchar,varchar,varchar,varchar
) FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest;

GRANT EXECUTE ON FUNCTION public.mp_orders_staging_append_incident_audit(
 uuid,varchar,varchar,varchar,varchar,varchar
) TO frcaixinha_mp_financial_worker;

-- DB owner remains privileged; a DBA or compromised superuser can modify
-- schema, functions and triggers. This is NOT tamper-proof external audit.
-- No policy or grant permits general application/master to read audit rows.
COMMIT;
