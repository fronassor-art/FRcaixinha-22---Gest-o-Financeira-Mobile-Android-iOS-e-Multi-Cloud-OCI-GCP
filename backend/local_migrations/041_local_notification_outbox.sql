-- AI Studio LOCAL-SAFE M041: schema de evidência sintética, sem API de pagamentos.
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
   RAISE EXCEPTION 'M041 LOCAL PARITY DENIED: not AI Studio PG18 or disposable CI';
 END IF;
END $local_guard$;

DO $dep$ BEGIN
 IF to_regclass('public.notification_inbox') IS NULL
 OR to_regclass('public.local_m040_incident_audit') IS NULL
 THEN RAISE EXCEPTION 'M041: 031/040 absent'; END IF;
END $dep$;
CREATE TABLE public.local_m041_notification_outbox (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id uuid REFERENCES public.tenants(id) ON DELETE RESTRICT,
 recipient_user_id uuid NOT NULL REFERENCES public.users(id) ON DELETE RESTRICT,
 recipient_role varchar(20) NOT NULL CHECK(recipient_role IN('MASTER','TENANT_ADMIN','TENANT_MEMBER')),
 fake_event_id uuid NOT NULL CHECK(fake_event_id<>'00000000-0000-0000-0000-000000000000'::uuid),
 category varchar(32) NOT NULL CHECK(category IN('SECURITY_INFO','CONTRIBUTION_INFO','CYCLE_INFO','SUPPORT_INFO')),
 status varchar(32) NOT NULL DEFAULT 'UNDELIVERED_SIMULATED' CHECK(status='UNDELIVERED_SIMULATED'),
 external_delivery_enabled boolean NOT NULL DEFAULT false CHECK(NOT external_delivery_enabled),
 inbox_delivery_confirmed boolean NOT NULL DEFAULT false CHECK(NOT inbox_delivery_confirmed),
 payment_effect boolean NOT NULL DEFAULT false CHECK(NOT payment_effect),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(recipient_user_id,fake_event_id),
 CHECK ((recipient_role='MASTER' AND tenant_id IS NULL)
 OR (recipient_role<>'MASTER' AND tenant_id IS NOT NULL))
);

ALTER TABLE public.local_m041_notification_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.local_m041_notification_outbox FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.local_m041_notification_outbox
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
-- NO POLICIES: even SELECT is unavailable to app/auth role.
-- Only the local DB owner may inspect this isolated test structure.
DO $assert_priv$
BEGIN
 IF NOT EXISTS (
   SELECT 1 FROM pg_class WHERE oid='public.local_m041_notification_outbox'::regclass
    AND relrowsecurity AND relforcerowsecurity
 ) OR has_table_privilege('frcaixinha_app_role','public.local_m041_notification_outbox','SELECT')
   OR has_table_privilege('frcaixinha_app_role','public.local_m041_notification_outbox','INSERT')
   OR has_table_privilege('frcaixinha_auth_role','public.local_m041_notification_outbox','SELECT')
 THEN RAISE EXCEPTION 'M041 ERROR: local sandbox isolation failed'; END IF;
END $assert_priv$;
