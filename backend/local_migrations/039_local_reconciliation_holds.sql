-- AI Studio LOCAL-SAFE M039: schema de evidência sintética, sem API de pagamentos.
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
   RAISE EXCEPTION 'M039 LOCAL PARITY DENIED: not AI Studio PG18 or disposable CI';
 END IF;
END $local_guard$;

DO $dep$ BEGIN
 IF to_regclass('public.local_m038_order_reservation') IS NULL
 THEN RAISE EXCEPTION 'M039: 038 absent'; END IF;
END $dep$;
CREATE TABLE public.local_m039_reconciliation_hold (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 reservation_id uuid NOT NULL,
 reason varchar(36) NOT NULL CHECK(reason IN('TIMEOUT_UNKNOWN','PROVIDER_MISMATCH','BANK_MISSING','EVIDENCE_UNVERIFIED')),
 state varchar(32) NOT NULL DEFAULT 'SYNTHETIC_UNRESOLVED' CHECK(state='SYNTHETIC_UNRESOLVED'),
 real_bank_reconciled boolean NOT NULL DEFAULT false CHECK(NOT real_bank_reconciled),
 real_financial_effect boolean NOT NULL DEFAULT false CHECK(NOT real_financial_effect),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,reservation_id) REFERENCES public.local_m038_order_reservation(tenant_id,id) ON DELETE RESTRICT
);

ALTER TABLE public.local_m039_reconciliation_hold ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.local_m039_reconciliation_hold FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.local_m039_reconciliation_hold
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
-- NO POLICIES: even SELECT is unavailable to app/auth role.
-- Only the local DB owner may inspect this isolated test structure.
DO $assert_priv$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class WHERE oid='public.local_m039_reconciliation_hold'::regclass
    AND relrowsecurity AND relforcerowsecurity
 ) OR has_table_privilege('frcaixinha_app_role','public.local_m039_reconciliation_hold','SELECT')
   OR has_table_privilege('frcaixinha_app_role','public.local_m039_reconciliation_hold','INSERT')
   OR has_table_privilege('frcaixinha_auth_role','public.local_m039_reconciliation_hold','SELECT')
 THEN RAISE EXCEPTION 'M039 ERROR: local sandbox isolation failed'; END IF;
END $assert_priv$;
