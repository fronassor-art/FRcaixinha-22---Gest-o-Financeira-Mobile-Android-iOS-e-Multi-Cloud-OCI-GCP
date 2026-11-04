-- FR CAIXINHA AI STUDIO ONLY: Staging OCI, migration 035 (NOT APPLIED).
-- Requires guarded, backed-up staging server and independent DBA approval.
-- NEVER RUN in Termux, frcaixinha_aistudio_dev, FRcaixinha 2.2 or production.
BEGIN;

DO $$
BEGIN
 IF current_database() <> 'frcaixinha_staging'
    OR current_setting('frcaixinha.mp_pix_automation_staging_authorized',true)
       IS DISTINCT FROM '1'
    OR current_setting('is_superuser') <> 'on'
    OR NOT EXISTS (SELECT 1 FROM pg_roles
                   WHERE rolname='frcaixinha_mp_financial_worker'
                     AND NOT rolsuper AND NOT rolbypassrls)
    OR to_regclass('public.contributions') IS NULL
    OR to_regclass('public.loan_installments') IS NULL
    OR to_regclass('public.ledger_entries') IS NULL
    OR to_regclass('public.tenants') IS NULL
    OR to_regclass('public.memberships') IS NULL THEN
    RAISE EXCEPTION 'M035 BLOQUEADA: OCI staging + DBA + schema + role requeridos';
 END IF;
END $$;

CREATE TABLE public.mp_pix_member_destinations_staging (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 membership_id uuid NOT NULL REFERENCES public.memberships(id) ON DELETE RESTRICT,
 -- ONLY an OCI Vault OCID; never Pix key / CPF / bank account in database.
 secret_ocid text NOT NULL CHECK(secret_ocid ~ '^ocid1[.]secret[.][A-Za-z0-9._-]{8,512}$'),
 masked_key varchar(80) NOT NULL,
 fingerprint char(64) NOT NULL CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
 owner_verification_ref varchar(128) NOT NULL,
 owner_verified_at timestamptz,
 consent_version varchar(100) NOT NULL,
 consent_at timestamptz NOT NULL,
 revoked_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,membership_id,id),
 CHECK (owner_verified_at IS NOT NULL AND (revoked_at IS NULL OR revoked_at >= consent_at))
);

CREATE TABLE public.mp_pix_collection_operations_staging (
 operation_id varchar(64) PRIMARY KEY CHECK(operation_id ~ '^[A-Za-z0-9_-]{8,64}$'),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 cycle_id uuid NOT NULL REFERENCES public.cycles(id) ON DELETE RESTRICT,
 membership_id uuid NOT NULL REFERENCES public.memberships(id) ON DELETE RESTRICT,
 obligation_id uuid NOT NULL,
 obligation_kind varchar(24) NOT NULL CHECK(obligation_kind IN('CONTRIBUTION','LOAN_INSTALLMENT')),
 loan_id uuid REFERENCES public.loans(id) ON DELETE RESTRICT,
 amount_cents bigint NOT NULL CHECK(amount_cents > 0),
 attempt smallint NOT NULL CHECK(attempt BETWEEN 1 AND 999),
 external_reference varchar(64) NOT NULL UNIQUE,
 idempotency_key varchar(64) NOT NULL UNIQUE,
 expected_collector_id varchar(40) NOT NULL CHECK(expected_collector_id ~ '^[0-9]{1,40}$'),
 terms_version varchar(100) NOT NULL,
 environment varchar(16) NOT NULL CHECK(environment IN('HOMOLOGACAO','PRODUCAO')),
 status varchar(32) NOT NULL DEFAULT 'PENDENTE'
     CHECK(status IN('PENDENTE','AGUARDANDO_PROVEDOR','PENDENTE_CONCILIACAO',
                     'LIQUIDADO_CONCILIADO','FALHOU','REVERTIDO')),
 provider_payment_id varchar(40) UNIQUE,
 qr_code text,
 qr_code_base64 text,
 ticket_url text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (obligation_kind='LOAN_INSTALLMENT' OR loan_id IS NULL),
 UNIQUE (tenant_id,obligation_kind,obligation_id,attempt)
);
CREATE INDEX mp_pix_collection_lookup ON public.mp_pix_collection_operations_staging
 (tenant_id,membership_id,created_at DESC);

CREATE TABLE public.mp_pix_settlement_evidence_staging (
 id uuid PRIMARY KEY,
 operation_id varchar(64) NOT NULL UNIQUE
    REFERENCES public.mp_pix_collection_operations_staging(operation_id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 provider_payment_id varchar(40) NOT NULL UNIQUE,
 collector_id varchar(40) NOT NULL,
 external_reference varchar(64) NOT NULL,
 gross_cents bigint NOT NULL CHECK(gross_cents>0),
 fee_cents bigint NOT NULL DEFAULT 0 CHECK(fee_cents>=0),
 net_cents bigint NOT NULL CHECK(net_cents>=0),
 statement_reference varchar(128) NOT NULL UNIQUE,
 statement_external_evidence_hash char(64) NOT NULL
    CHECK(statement_external_evidence_hash ~ '^[a-f0-9]{64}$'),
 provider_read_verified boolean NOT NULL CHECK(provider_read_verified=true),
 independent_settlement_verified boolean NOT NULL
    CHECK(independent_settlement_verified=true),
 currency char(3) NOT NULL DEFAULT 'BRL' CHECK(currency='BRL'),
 confirmed_at timestamptz NOT NULL,
 verified_at timestamptz NOT NULL DEFAULT now(),
 CHECK(net_cents + fee_cents = gross_cents)
);

CREATE TABLE public.mp_pix_receipts_staging (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 membership_id uuid NOT NULL REFERENCES public.memberships(id) ON DELETE RESTRICT,
 operation_id varchar(64) NOT NULL UNIQUE
    REFERENCES public.mp_pix_collection_operations_staging(operation_id) ON DELETE RESTRICT,
 provider_payment_id varchar(40) NOT NULL UNIQUE,
 statement_reference varchar(128) NOT NULL UNIQUE,
 obligation_id uuid NOT NULL,
 amount_cents bigint NOT NULL CHECK(amount_cents>0),
 interest_cents bigint NOT NULL DEFAULT 0 CHECK(interest_cents>=0),
 mora_cents bigint NOT NULL DEFAULT 0 CHECK(mora_cents>=0),
 fine_cents bigint NOT NULL DEFAULT 0 CHECK(fine_cents>=0),
 principal_cents bigint NOT NULL DEFAULT 0 CHECK(principal_cents>=0),
 ledger_transaction_id uuid NOT NULL UNIQUE REFERENCES public.ledger_transactions(id) ON DELETE RESTRICT,
 paid_at timestamptz NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK(interest_cents+mora_cents+fine_cents+principal_cents<=amount_cents)
);
CREATE INDEX mp_pix_receipt_tenant ON public.mp_pix_receipts_staging
 (tenant_id,membership_id,created_at DESC);

CREATE TABLE public.mp_pix_payout_operations_staging (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 cycle_id uuid NOT NULL REFERENCES public.cycles(id) ON DELETE RESTRICT,
 loan_id uuid NOT NULL UNIQUE REFERENCES public.loans(id) ON DELETE RESTRICT,
 membership_id uuid NOT NULL REFERENCES public.memberships(id) ON DELETE RESTRICT,
 destination_id uuid NOT NULL REFERENCES public.mp_pix_member_destinations_staging(id) ON DELETE RESTRICT,
 amount_cents bigint NOT NULL CHECK(amount_cents>0),
 business_operation_id varchar(64) NOT NULL UNIQUE,
 idempotency_key varchar(64) NOT NULL UNIQUE,
 account_id varchar(40) NOT NULL CHECK(account_id ~ '^[0-9]{1,40}$'),
 status varchar(32) NOT NULL DEFAULT 'RESERVADO'
   CHECK(status IN('RESERVADO','ENVIADO','PENDENTE_CONCILIACAO',
                   'CONFIRMADO','FALHOU','CANCELADO_COMPROVADO')),
 provider_payout_id varchar(80) UNIQUE,
 provider_status varchar(32),
 bank_proof_ref varchar(128) UNIQUE,
 confirmed_effective_at timestamptz,
 ledger_transaction_id uuid UNIQUE REFERENCES public.ledger_transactions(id) ON DELETE RESTRICT,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK ((status<>'CONFIRMADO') OR
        (provider_payout_id IS NOT NULL AND bank_proof_ref IS NOT NULL
         AND confirmed_effective_at IS NOT NULL AND ledger_transaction_id IS NOT NULL))
);

-- All tables deny direct access to the general app and public.
-- Isolated SQL worker must access via narrowly scoped SECURITY DEFINER functions
-- that check session_user, tenant mapping and write immutable evidence.
DO $$
DECLARE table_name text;
BEGIN
 FOREACH table_name IN ARRAY ARRAY[
   'mp_pix_member_destinations_staging',
   'mp_pix_collection_operations_staging',
   'mp_pix_settlement_evidence_staging',
   'mp_pix_receipts_staging',
   'mp_pix_payout_operations_staging'
 ] LOOP
   EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',table_name);
   EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',table_name);
   EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC,frcaixinha_mp_financial_worker',table_name);
 END LOOP;
END $$;

-- Auditable owner-scoped access. These RLS policies are for future read
-- roles explicitly GRANTED after staging RBAC review; no grants here.
CREATE POLICY mp_coll_tenant_read ON public.mp_pix_collection_operations_staging
 FOR SELECT USING (
    current_setting('app.current_tenant_id',true)=tenant_id::text
    AND current_setting('app.current_role',true) IN('TENANT_ADMIN','TENANT_MEMBER')
    AND (current_setting('app.current_role',true)='TENANT_ADMIN'
         OR membership_id IN (
            SELECT id FROM public.memberships
            WHERE tenant_id=mp_pix_collection_operations_staging.tenant_id
              AND user_id::text=current_setting('app.current_user_id',true)))
 );
CREATE POLICY mp_receipt_tenant_read ON public.mp_pix_receipts_staging
 FOR SELECT USING (
    current_setting('app.current_tenant_id',true)=tenant_id::text
    AND current_setting('app.current_role',true) IN('TENANT_ADMIN','TENANT_MEMBER')
    AND (current_setting('app.current_role',true)='TENANT_ADMIN'
         OR membership_id IN (
            SELECT id FROM public.memberships
            WHERE tenant_id=mp_pix_receipts_staging.tenant_id
              AND user_id::text=current_setting('app.current_user_id',true)))
 );
CREATE POLICY mp_payout_tenant_read ON public.mp_pix_payout_operations_staging
 FOR SELECT USING (
    current_setting('app.current_tenant_id',true)=tenant_id::text
    AND current_setting('app.current_role',true) IN('TENANT_ADMIN','TENANT_MEMBER')
    AND (current_setting('app.current_role',true)='TENANT_ADMIN'
         OR membership_id IN (
            SELECT id FROM public.memberships
            WHERE tenant_id=mp_pix_payout_operations_staging.tenant_id
              AND user_id::text=current_setting('app.current_user_id',true)))
 );
-- No INSERT/UPDATE/DELETE policies: no direct financial mutation from app.
COMMIT;
