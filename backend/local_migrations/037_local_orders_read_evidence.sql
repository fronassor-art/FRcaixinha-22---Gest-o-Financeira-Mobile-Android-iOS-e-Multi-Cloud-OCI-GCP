-- AI Studio LOCAL-SAFE M037: schema de evidência sintética, sem API de pagamentos.
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
   RAISE EXCEPTION 'M037 LOCAL PARITY DENIED: not AI Studio PG18 or disposable CI';
 END IF;
END $local_guard$;

DO $dep$ BEGIN
 IF to_regclass('public.local_m035_pix_dryrun') IS NULL
  OR to_regclass('public.local_m036_orders_inbox') IS NULL
 THEN RAISE EXCEPTION 'M037: 035/036 absent'; END IF;
END $dep$;
CREATE TABLE public.local_m037_order_evidence (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 dryrun_id uuid NOT NULL,
 order_event_id uuid NOT NULL,
 evidence_digest varchar(64) NOT NULL CHECK(evidence_digest ~ '^[a-f0-9]{64}$'),
 state varchar(28) NOT NULL DEFAULT 'UNVERIFIED_LOCAL' CHECK(state='UNVERIFIED_LOCAL'),
 real_provider_read boolean NOT NULL DEFAULT false CHECK(NOT real_provider_read),
 bank_reconciled boolean NOT NULL DEFAULT false CHECK(NOT bank_reconciled),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,dryrun_id) REFERENCES public.local_m035_pix_dryrun(tenant_id,id) ON DELETE RESTRICT,
 FOREIGN KEY(tenant_id,order_event_id) REFERENCES public.local_m036_orders_inbox(tenant_id,id) ON DELETE RESTRICT
);

ALTER TABLE public.local_m037_order_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.local_m037_order_evidence FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.local_m037_order_evidence
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
-- NO POLICIES: even SELECT is unavailable to app/auth role.
-- Only the local DB owner may inspect this isolated test structure.
DO $assert_priv$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class WHERE oid='public.local_m037_order_evidence'::regclass
    AND relrowsecurity AND relforcerowsecurity
 ) OR has_table_privilege('frcaixinha_app_role','public.local_m037_order_evidence','SELECT')
   OR has_table_privilege('frcaixinha_app_role','public.local_m037_order_evidence','INSERT')
   OR has_table_privilege('frcaixinha_auth_role','public.local_m037_order_evidence','SELECT')
 THEN RAISE EXCEPTION 'M037 ERROR: local sandbox isolation failed'; END IF;
END $assert_priv$;
