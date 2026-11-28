-- FR Finance M37501: synthetic mail evidence quarantine, CI disposable only.
-- No SMTP message is sent by this schema. No ownership/consent attestation.
BEGIN;
DO $guard$ BEGIN
 IF current_database() <> 'frcaixinha_staging'
 OR session_user <> 'postgres'
 OR current_setting('is_superuser') <> 'on'
 OR current_setting('frfinance.m37500_ci', true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M37501_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.fr_m37501_mail_quarantine_ci (
 event_id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
 recipient_digest char(64) NOT NULL CHECK (recipient_digest ~ '^[0-9a-f]{64}$'),
 envelope_digest char(64) NOT NULL CHECK (envelope_digest ~ '^[0-9a-f]{64}$'),
 status varchar(24) NOT NULL DEFAULT 'QUARANTINED'
   CHECK (status IN ('QUARANTINED','BOUNCED','RETRY_BLOCKED')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 real_mail_sent boolean NOT NULL DEFAULT false CHECK (NOT real_mail_sent),
 email_ownership_verified boolean NOT NULL DEFAULT false
   CHECK (NOT email_ownership_verified),
 user_activated boolean NOT NULL DEFAULT false CHECK (NOT user_activated),
 UNIQUE(tenant_id,request_digest)
);
ALTER TABLE public.fr_m37501_mail_quarantine_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fr_m37501_mail_quarantine_ci FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.fr_m37501_mail_quarantine_ci FROM PUBLIC;
CREATE TRIGGER fr_m37501_mail_no_update_delete_ci
BEFORE UPDATE OR DELETE ON public.fr_m37501_mail_quarantine_ci
FOR EACH ROW EXECUTE FUNCTION public.fr_m37500_quarantine_immutable_ci();
CREATE TRIGGER fr_m37501_mail_no_truncate_ci
BEFORE TRUNCATE ON public.fr_m37501_mail_quarantine_ci
FOR EACH STATEMENT EXECUTE FUNCTION public.fr_m37500_quarantine_immutable_ci();
COMMIT;
