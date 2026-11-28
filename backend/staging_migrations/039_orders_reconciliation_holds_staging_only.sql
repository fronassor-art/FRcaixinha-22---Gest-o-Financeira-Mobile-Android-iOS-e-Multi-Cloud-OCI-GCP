-- AI STUDIO M6500: durably record UNKNOWN/REJECTED reconciliation.
-- OCI STAGING ONLY: never Termux/production. No payment, ledger or status
-- updates. Bank reconciliation is NOT implied by an incident row.
BEGIN;

DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.orders_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser') <> 'on'
    OR NOT EXISTS (SELECT 1 FROM pg_roles
       WHERE rolname='frcaixinha_mp_financial_worker'
       AND NOT rolsuper AND NOT rolbypassrls)
    OR to_regclass('public.mp_pix_collection_operations_staging') IS NULL
    OR to_regclass('public.mp_seller_connections_staging') IS NULL
    OR to_regprocedure('public.mp_orders_staging_reserve(uuid,uuid,uuid,uuid,character varying,uuid,bigint,smallint,character varying,character varying,character varying,character varying,character varying,character varying)') IS NULL
 THEN
   RAISE EXCEPTION 'M039 DENIED: OCI staging + M034-M038 + DBA + role required';
 END IF;
END $guard$;

CREATE TABLE public.mp_orders_reconciliation_holds_staging (
 tenant_id uuid NOT NULL,
 operation_id varchar(64) NOT NULL,
 reason_code varchar(40) NOT NULL
   CHECK(reason_code IN(
     'TIMEOUT_UNKNOWN','PROVIDER_MISMATCH','BANK_MISSING',
     'FEE_MISMATCH','ORDER_REPLAY','REVERSAL_PENDING',
     'STATEMENT_DUPLICATE','STATUS_CONFLICT','SELLER_REVOKED'
   )),
 evidence_fingerprint char(64) NOT NULL
    CHECK(evidence_fingerprint ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 source varchar(40) NOT NULL DEFAULT 'RECONCILIATION_HOLD_UNSETTLED'
    CHECK(source='RECONCILIATION_HOLD_UNSETTLED'),
 financial_effect_applied boolean NOT NULL DEFAULT false
    CHECK(financial_effect_applied=false),
 ledger_written boolean NOT NULL DEFAULT false CHECK(ledger_written=false),
 bank_reconciled boolean NOT NULL DEFAULT false CHECK(bank_reconciled=false),
 payout_authorized boolean NOT NULL DEFAULT false CHECK(payout_authorized=false),
 PRIMARY KEY(tenant_id,operation_id,reason_code),
 FOREIGN KEY(tenant_id,operation_id)
  REFERENCES public.mp_pix_collection_operations_staging(tenant_id,operation_id)
  ON DELETE RESTRICT
);
CREATE INDEX mp_orders_reconciliation_holds_tenant_created
 ON public.mp_orders_reconciliation_holds_staging(tenant_id,created_at DESC);
ALTER TABLE public.mp_orders_reconciliation_holds_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_orders_reconciliation_holds_staging FORCE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.mp_orders_reconciliation_holds_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_financial_worker,
 frcaixinha_mp_webhook_ingest;

CREATE OR REPLACE FUNCTION public.mp_orders_staging_record_hold(
 p_tenant uuid,p_operation varchar,
 p_reason varchar,p_evidence_fingerprint varchar
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $fn$
DECLARE previous_fingerprint char(64);
BEGIN
 IF current_database()<>'frcaixinha_staging'
   OR session_user<>'frcaixinha_mp_financial_worker'
   OR p_tenant IS NULL
   OR p_operation IS NULL OR p_operation !~ '^P_[0-9a-f]{32}$'
   OR p_reason IS NULL OR p_reason NOT IN (
     'TIMEOUT_UNKNOWN','PROVIDER_MISMATCH','BANK_MISSING',
     'FEE_MISMATCH','ORDER_REPLAY','REVERSAL_PENDING',
     'STATEMENT_DUPLICATE','STATUS_CONFLICT','SELLER_REVOKED')
   OR p_evidence_fingerprint IS NULL
   OR p_evidence_fingerprint !~ '^[a-f0-9]{64}$'
   OR NOT EXISTS (
     SELECT 1
     FROM public.mp_pix_collection_operations_staging c
     WHERE c.tenant_id=p_tenant AND c.operation_id=p_operation
       AND c.environment='HOMOLOGACAO'
       AND c.status NOT IN ('LIQUIDADO_CONCILIADO','REVERTIDO')
       AND EXISTS (
         SELECT 1 FROM public.mp_seller_connections_staging s
         WHERE s.tenant_id=c.tenant_id
           AND s.seller_id=c.expected_collector_id
       )
   ) THEN
   RAISE EXCEPTION 'M039 DENIED: unresolved Orders evidence or tenant scope';
 END IF;

 PERFORM pg_advisory_xact_lock(pg_catalog.hashtextextended(
    'FRC-M039|'||p_tenant||'|'||p_operation||'|'||p_reason,0
 ));
 SELECT h.evidence_fingerprint INTO previous_fingerprint
 FROM public.mp_orders_reconciliation_holds_staging h
 WHERE h.tenant_id=p_tenant AND h.operation_id=p_operation
   AND h.reason_code=p_reason FOR UPDATE;
 IF FOUND THEN
    IF previous_fingerprint<>p_evidence_fingerprint THEN
      RAISE EXCEPTION 'M039 DENIED: conflicting reconciliation evidence';
    END IF;
    RETURN 'REPLAY';
 END IF;
 INSERT INTO public.mp_orders_reconciliation_holds_staging (
   tenant_id,operation_id,reason_code,evidence_fingerprint
 ) VALUES (p_tenant,p_operation,p_reason,p_evidence_fingerprint);
 RETURN 'NEW';
END $fn$;

REVOKE ALL ON FUNCTION public.mp_orders_staging_record_hold(
 uuid,varchar,varchar,varchar
) FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest;

GRANT EXECUTE ON FUNCTION public.mp_orders_staging_record_hold(
 uuid,varchar,varchar,varchar
) TO frcaixinha_mp_financial_worker;
-- No release function, no direct UPDATE, no economic posting authority.
COMMIT;
