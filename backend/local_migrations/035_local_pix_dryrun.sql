-- AI Studio LOCAL-SAFE M035: schema de evidência sintética, sem API de pagamentos.
-- Nunca aplicar SQL OCI/staging original ao banco Termux.
DO $local_guard$
BEGIN
 IF NOT (
   (current_database()='frcaixinha_aistudio_dev'
    AND session_user='frc_ai_owner' AND current_user='frc_ai_owner'
    AND inet_server_port()=5433
    AND current_setting('data_directory')=
      '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
    AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999)
   OR
   (current_database()='frcaixinha_ci'
    AND session_user='postgres'
    AND current_setting('is_superuser')='on'
    AND current_setting('frcaixinha.local_parity_ci',true)='1')
 ) THEN
   RAISE EXCEPTION 'M035 LOCAL PARITY DENIED: not AI Studio PG18 or disposable CI';
 END IF;
END $local_guard$;

DO $dep$ BEGIN
 IF to_regclass('public.local_m034_webhook_evidence') IS NULL
 THEN RAISE EXCEPTION 'M035: 034 absent'; END IF;
END $dep$;
CREATE TABLE public.local_m035_pix_dryrun (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 fake_idempotency uuid NOT NULL,
 amount_cents bigint NOT NULL CHECK(amount_cents>=0 AND amount_cents<=100000000000),
 intent_kind varchar(24) NOT NULL CHECK(intent_kind IN ('COLLECTION_DRYRUN','PAYOUT_DRYRUN')),
 state varchar(32) NOT NULL DEFAULT 'SIMULATED_NOT_SENT' CHECK(state='SIMULATED_NOT_SENT'),
 provider_order_id text,
 real_payment_enabled boolean NOT NULL DEFAULT false CHECK(NOT real_payment_enabled),
 ledger_written boolean NOT NULL DEFAULT false CHECK(NOT ledger_written),
 bank_reconciled boolean NOT NULL DEFAULT false CHECK(NOT bank_reconciled),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,fake_idempotency),UNIQUE(tenant_id,id),
 CHECK(provider_order_id IS NULL)
);

ALTER TABLE public.local_m035_pix_dryrun ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.local_m035_pix_dryrun FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.local_m035_pix_dryrun
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
-- NO POLICIES: even SELECT is unavailable to app/auth role.
-- Only the local DB owner may inspect this isolated test structure.
DO $assert_priv$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class WHERE oid='public.local_m035_pix_dryrun'::regclass
    AND relrowsecurity AND relforcerowsecurity
 ) OR has_table_privilege('frcaixinha_app_role','public.local_m035_pix_dryrun','SELECT')
   OR has_table_privilege('frcaixinha_app_role','public.local_m035_pix_dryrun','INSERT')
   OR has_table_privilege('frcaixinha_auth_role','public.local_m035_pix_dryrun','SELECT')
 THEN RAISE EXCEPTION 'M035 ERROR: local sandbox isolation failed'; END IF;
END $assert_priv$;
