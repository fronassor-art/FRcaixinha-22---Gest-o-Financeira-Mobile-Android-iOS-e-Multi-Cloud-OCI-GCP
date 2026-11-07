-- AI Studio LOCAL-SAFE M040: schema de evidência sintética, sem API de pagamentos.
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
   RAISE EXCEPTION 'M040 LOCAL PARITY DENIED: not AI Studio PG18 or disposable CI';
 END IF;
END $local_guard$;

DO $dep$ BEGIN
 IF to_regclass('public.local_m039_reconciliation_hold') IS NULL
 THEN RAISE EXCEPTION 'M040: 039 absent'; END IF;
END $dep$;
CREATE TABLE public.local_m040_incident_audit (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 hold_id uuid NOT NULL,
 local_seq bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
 evidence_sha256 varchar(64) NOT NULL CHECK(evidence_sha256 ~ '^[a-f0-9]{64}$'),
 source varchar(22) NOT NULL DEFAULT 'LOCAL_SYNTHETIC' CHECK(source='LOCAL_SYNTHETIC'),
 bank_claim_verified boolean NOT NULL DEFAULT false CHECK(NOT bank_claim_verified),
 financial_effect boolean NOT NULL DEFAULT false CHECK(NOT financial_effect),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,hold_id) REFERENCES public.local_m039_reconciliation_hold(tenant_id,id) ON DELETE RESTRICT
);
CREATE FUNCTION public.local_m040_deny_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp AS $fn$
BEGIN
 RAISE EXCEPTION 'M040: immutable local synthetic incident audit';
END $fn$;
REVOKE ALL ON FUNCTION public.local_m040_deny_mutation() FROM PUBLIC;
CREATE TRIGGER local_m040_immutable_row
BEFORE UPDATE OR DELETE ON public.local_m040_incident_audit
FOR EACH ROW EXECUTE FUNCTION public.local_m040_deny_mutation();
CREATE TRIGGER local_m040_immutable_truncate
BEFORE TRUNCATE ON public.local_m040_incident_audit
FOR EACH STATEMENT EXECUTE FUNCTION public.local_m040_deny_mutation();

ALTER TABLE public.local_m040_incident_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.local_m040_incident_audit FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.local_m040_incident_audit
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
-- NO POLICIES: even SELECT is unavailable to app/auth role.
-- Only the local DB owner may inspect this isolated test structure.
DO $assert_priv$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class WHERE oid='public.local_m040_incident_audit'::regclass
    AND relrowsecurity AND relforcerowsecurity
 ) OR has_table_privilege('frcaixinha_app_role','public.local_m040_incident_audit','SELECT')
   OR has_table_privilege('frcaixinha_app_role','public.local_m040_incident_audit','INSERT')
   OR has_table_privilege('frcaixinha_auth_role','public.local_m040_incident_audit','SELECT')
 THEN RAISE EXCEPTION 'M040 ERROR: local sandbox isolation failed'; END IF;
END $assert_priv$;
