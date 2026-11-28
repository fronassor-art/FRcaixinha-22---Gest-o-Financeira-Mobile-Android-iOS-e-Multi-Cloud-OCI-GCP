-- FR Finance M37500: REPLAYABLE OFFLINE RELEASE GATE QUARANTINE.
-- DISPOSABLE CI ONLY. NEVER apply to Termux 5433, OCI staging or production.
-- Cannot attest a real gate, create a user, payment or cloud resource.
BEGIN;
DO $guard$ BEGIN
 IF current_database() <> 'frcaixinha_staging'
 OR session_user <> 'postgres'
 OR current_setting('is_superuser') <> 'on'
 OR current_setting('frfinance.m37500_ci', true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M37500_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.fr_m37500_release_gate_quarantine_ci (
  event_id uuid PRIMARY KEY,
  workstream varchar(64) NOT NULL CHECK (workstream ~ '^[A-Z_]{4,64}$'),
  gate_id varchar(64) NOT NULL CHECK (gate_id ~ '^[A-Z_]{4,64}$'),
  source_digest char(64) NOT NULL CHECK (source_digest ~ '^[0-9a-f]{64}$'),
  status varchar(24) NOT NULL DEFAULT 'UNVERIFIED'
    CHECK (status = 'UNVERIFIED'),
  created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  sandbox_only boolean NOT NULL DEFAULT true CHECK (sandbox_only),
  real_gate_verified boolean NOT NULL DEFAULT false CHECK (NOT real_gate_verified),
  real_activation_authorized boolean NOT NULL DEFAULT false
    CHECK (NOT real_activation_authorized),
  real_payment_authorized boolean NOT NULL DEFAULT false
    CHECK (NOT real_payment_authorized),
  pix_real_authorized boolean NOT NULL DEFAULT false
    CHECK (NOT pix_real_authorized),
  UNIQUE (gate_id, source_digest)
);
ALTER TABLE public.fr_m37500_release_gate_quarantine_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fr_m37500_release_gate_quarantine_ci FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.fr_m37500_release_gate_quarantine_ci FROM PUBLIC;
CREATE FUNCTION public.fr_m37500_quarantine_immutable_ci()
RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,public,pg_temp
AS $trigger$ BEGIN
 RAISE EXCEPTION 'M37500_QUARANTINE_APPEND_ONLY';
END $trigger$;
CREATE TRIGGER fr_m37500_quarantine_no_update_delete_ci
BEFORE UPDATE OR DELETE ON public.fr_m37500_release_gate_quarantine_ci
FOR EACH ROW EXECUTE FUNCTION public.fr_m37500_quarantine_immutable_ci();
CREATE TRIGGER fr_m37500_quarantine_no_truncate_ci
BEFORE TRUNCATE ON public.fr_m37500_release_gate_quarantine_ci
FOR EACH STATEMENT EXECUTE FUNCTION public.fr_m37500_quarantine_immutable_ci();
REVOKE ALL ON FUNCTION public.fr_m37500_quarantine_immutable_ci() FROM PUBLIC;
COMMIT;
