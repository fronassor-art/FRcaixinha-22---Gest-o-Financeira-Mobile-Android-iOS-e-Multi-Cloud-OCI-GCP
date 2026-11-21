-- AI Studio LOCAL-SAFE M034: schema de evidência sintética, sem API de pagamentos.
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
   RAISE EXCEPTION 'M034 LOCAL PARITY DENIED: not AI Studio PG18 or disposable CI';
 END IF;
END $local_guard$;

CREATE TABLE public.local_m034_webhook_evidence (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 fake_event_id varchar(90) NOT NULL CHECK(length(fake_event_id)>=8),
 payload_sha256 varchar(64) NOT NULL CHECK(payload_sha256 ~ '^[a-f0-9]{64}$'),
 source varchar(16) NOT NULL DEFAULT 'LOCAL_SIMULATION' CHECK(source='LOCAL_SIMULATION'),
 signature_production_verified boolean NOT NULL DEFAULT false CHECK(NOT signature_production_verified),
 provider_connection_active boolean NOT NULL DEFAULT false CHECK(NOT provider_connection_active),
 payment_effect_applied boolean NOT NULL DEFAULT false CHECK(NOT payment_effect_applied),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,fake_event_id), UNIQUE(tenant_id,id)
);

ALTER TABLE public.local_m034_webhook_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.local_m034_webhook_evidence FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.local_m034_webhook_evidence
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
-- NO POLICIES: even SELECT is unavailable to app/auth role.
-- Only the local DB owner may inspect this isolated test structure.
DO $assert_priv$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class WHERE oid='public.local_m034_webhook_evidence'::regclass
    AND relrowsecurity AND relforcerowsecurity
 ) OR has_table_privilege('frcaixinha_app_role','public.local_m034_webhook_evidence','SELECT')
   OR has_table_privilege('frcaixinha_app_role','public.local_m034_webhook_evidence','INSERT')
   OR has_table_privilege('frcaixinha_auth_role','public.local_m034_webhook_evidence','SELECT')
 THEN RAISE EXCEPTION 'M034 ERROR: local sandbox isolation failed'; END IF;
END $assert_priv$;
