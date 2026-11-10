-- FR Finance M37502: synthetic sandbox payment hold evidence.
-- No provider, ledger settlement, license issue, Pix or payment execution.
BEGIN;
DO $guard$ BEGIN
 IF current_database() <> 'frcaixinha_staging'
 OR session_user <> 'postgres'
 OR current_setting('is_superuser') <> 'on'
 OR current_setting('frfinance.m37500_ci', true) IS DISTINCT FROM '1'
 THEN RAISE EXCEPTION 'M37502_DISPOSABLE_CI_ONLY'; END IF;
END $guard$;

CREATE TABLE public.fr_m37502_reconciliation_hold_ci (
 review_id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 request_digest char(64) NOT NULL CHECK (request_digest ~ '^[0-9a-f]{64}$'),
 order_digest char(64) NOT NULL CHECK (order_digest ~ '^[0-9a-f]{64}$'),
 provider_digest char(64) NOT NULL CHECK (provider_digest ~ '^[0-9a-f]{64}$'),
 ledger_digest char(64) NOT NULL CHECK (ledger_digest ~ '^[0-9a-f]{64}$'),
 amount_cents bigint NOT NULL CHECK (amount_cents > 0 AND amount_cents <= 1000000000000),
 currency char(3) NOT NULL DEFAULT 'BRL' CHECK (currency = 'BRL'),
 state varchar(24) NOT NULL DEFAULT 'HOLD_UNVERIFIED'
   CHECK (state = 'HOLD_UNVERIFIED'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 sandbox_only boolean NOT NULL DEFAULT true CHECK (sandbox_only),
 provider_settlement_verified boolean NOT NULL DEFAULT false
   CHECK (NOT provider_settlement_verified),
 ledger_written boolean NOT NULL DEFAULT false CHECK (NOT ledger_written),
 license_activated boolean NOT NULL DEFAULT false CHECK (NOT license_activated),
 pix_real_authorized boolean NOT NULL DEFAULT false CHECK (NOT pix_real_authorized),
 UNIQUE(tenant_id,request_digest)
);
ALTER TABLE public.fr_m37502_reconciliation_hold_ci ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fr_m37502_reconciliation_hold_ci FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.fr_m37502_reconciliation_hold_ci FROM PUBLIC;
CREATE TRIGGER fr_m37502_payment_no_update_delete_ci
BEFORE UPDATE OR DELETE ON public.fr_m37502_reconciliation_hold_ci
FOR EACH ROW EXECUTE FUNCTION public.fr_m37500_quarantine_immutable_ci();
CREATE TRIGGER fr_m37502_payment_no_truncate_ci
BEFORE TRUNCATE ON public.fr_m37502_reconciliation_hold_ci
FOR EACH STATEMENT EXECUTE FUNCTION public.fr_m37500_quarantine_immutable_ci();
COMMIT;
