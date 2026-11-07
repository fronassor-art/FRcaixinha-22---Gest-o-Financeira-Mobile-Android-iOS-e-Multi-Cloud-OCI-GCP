-- FR Caixinha AI Studio M4700 / Orders Pix: staging contract extension.
-- NOT applied. Must run only on approved OCI frcaixinha_staging, after
-- M034 M035 M036 independent preflight (with DBA, backup and role audit).
BEGIN;

DO $guard$
BEGIN
  IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.orders_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser')<>'on'
    OR to_regclass('public.mp_pix_collection_operations_staging') IS NULL
    OR to_regclass('public.mp_pix_receipts_staging') IS NULL
    OR to_regclass('public.mp_signed_order_inbox_staging') IS NULL THEN
    RAISE EXCEPTION 'M4700 BLOCKED: staging Orders schema missing';
  END IF;
END $guard$;

ALTER TABLE public.mp_pix_collection_operations_staging
 ADD COLUMN provider_order_id varchar(80) UNIQUE
 CHECK(provider_order_id IS NULL OR provider_order_id ~ '^ORD[A-Z0-9]{12,77}$');

ALTER TABLE public.mp_pix_receipts_staging
 ADD COLUMN provider_order_id varchar(80)
 CHECK(provider_order_id IS NULL OR provider_order_id ~ '^ORD[A-Z0-9]{12,77}$');

-- Note: receipts for legacy Payment transactions may omit provider_order_id.
-- New Orders posting must bind provider_order_id in trusted worker.
CREATE UNIQUE INDEX mp_pix_receipt_provider_order_id_ux
 ON public.mp_pix_receipts_staging(provider_order_id)
 WHERE provider_order_id IS NOT NULL;

CREATE TABLE public.mp_orders_provider_reads_staging(
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 operation_id varchar(64) NOT NULL
   REFERENCES public.mp_pix_collection_operations_staging(operation_id) ON DELETE RESTRICT,
 order_id varchar(80) NOT NULL CHECK(order_id ~ '^ORD[A-Z0-9]{12,77}$'),
 payment_id varchar(80) NOT NULL CHECK(payment_id ~ '^PAY[A-Z0-9]{12,77}$'),
 provider_account_id varchar(40) NOT NULL CHECK(provider_account_id ~ '^[0-9]{1,40}$'),
 status varchar(40) NOT NULL,
 status_detail varchar(48) NOT NULL,
 payment_status varchar(40) NOT NULL,
 payment_status_detail varchar(48) NOT NULL,
 amount_cents bigint NOT NULL CHECK(amount_cents>0),
 external_reference varchar(64) NOT NULL,
 get_checked_at timestamptz NOT NULL DEFAULT now(),
 bank_reconciled boolean NOT NULL DEFAULT false CHECK(bank_reconciled=false),
 ledger_written boolean NOT NULL DEFAULT false CHECK(ledger_written=false),
 PRIMARY KEY(tenant_id,operation_id),
 UNIQUE(tenant_id,order_id),
 UNIQUE(tenant_id,payment_id),
 CHECK(status IN('action_required','processed','canceled','failed')),
 CHECK(payment_status IN('action_required','processed','canceled','failed')),
 CHECK(external_reference ~ '^[A-Za-z0-9_-]{8,64}$')
);
ALTER TABLE public.mp_orders_provider_reads_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_orders_provider_reads_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.mp_orders_provider_reads_staging FROM PUBLIC;

-- No artificial "paid" update. Production worker still requires:
-- authenticated GET Orders, independent settlement evidence, ledger
-- balanced double-entry commit, RLS, replay/rollback and reversals.
COMMIT;
