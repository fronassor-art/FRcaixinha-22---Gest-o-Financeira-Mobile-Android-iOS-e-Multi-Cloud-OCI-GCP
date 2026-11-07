-- AI Studio LOCAL-SAFE M038: schema de evidência sintética, sem API de pagamentos.
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
   RAISE EXCEPTION 'M038 LOCAL PARITY DENIED: not AI Studio PG18 or disposable CI';
 END IF;
END $local_guard$;

DO $dep$ BEGIN
 IF to_regclass('public.local_m037_order_evidence') IS NULL
 THEN RAISE EXCEPTION 'M038: 037 absent'; END IF;
END $dep$;
CREATE TABLE public.local_m038_order_reservation (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 evidence_id uuid NOT NULL,
 fake_reservation_key uuid NOT NULL,
 state varchar(32) NOT NULL DEFAULT 'SIMULATED_HOLD' CHECK(state='SIMULATED_HOLD'),
 checkout_live boolean NOT NULL DEFAULT false CHECK(NOT checkout_live),
 payout_authorized boolean NOT NULL DEFAULT false CHECK(NOT payout_authorized),
 ledger_written boolean NOT NULL DEFAULT false CHECK(NOT ledger_written),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,fake_reservation_key),UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,evidence_id) REFERENCES public.local_m037_order_evidence(tenant_id,id) ON DELETE RESTRICT
);

ALTER TABLE public.local_m038_order_reservation ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.local_m038_order_reservation FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.local_m038_order_reservation
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
-- NO POLICIES: even SELECT is unavailable to app/auth role.
-- Only the local DB owner may inspect this isolated test structure.
DO $assert_priv$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class WHERE oid='public.local_m038_order_reservation'::regclass
    AND relrowsecurity AND relforcerowsecurity
 ) OR has_table_privilege('frcaixinha_app_role','public.local_m038_order_reservation','SELECT')
   OR has_table_privilege('frcaixinha_app_role','public.local_m038_order_reservation','INSERT')
   OR has_table_privilege('frcaixinha_auth_role','public.local_m038_order_reservation','SELECT')
 THEN RAISE EXCEPTION 'M038 ERROR: local sandbox isolation failed'; END IF;
END $assert_priv$;
