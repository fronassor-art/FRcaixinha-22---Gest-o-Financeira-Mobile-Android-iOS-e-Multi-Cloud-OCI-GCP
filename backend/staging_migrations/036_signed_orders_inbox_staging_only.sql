-- AI Studio M4500: ORDERS WEBHOOK STAGING, NEVER RUN AUTOMATICALLY.
-- Prerequisite: explicitly audited/approved OCI frcaixinha_staging with
-- migration 034 and dedicated frcaixinha_mp_webhook_ingest role.
-- This is NOT a migration for Termux PostgreSQL port 5433.
BEGIN;

DO $guard$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR current_setting('frcaixinha.orders_staging_authorized',true) IS DISTINCT FROM '1'
    OR current_setting('is_superuser')<>'on'
    OR NOT EXISTS (
       SELECT 1 FROM pg_roles
       WHERE rolname='frcaixinha_mp_webhook_ingest'
         AND NOT rolsuper AND NOT rolbypassrls)
    OR to_regclass('public.mp_seller_connections_staging') IS NULL
    OR to_regclass('public.tenants') IS NULL THEN
   RAISE EXCEPTION 'M4500 BLOCKED: staging OCI + M034 + DBA required';
 END IF;
END $guard$;

CREATE TABLE public.mp_signed_order_inbox_staging(
 event_id varchar(90) NOT NULL,
 tenant_id uuid NOT NULL,
 provider_account_id varchar(40) NOT NULL,
 request_id varchar(120) NOT NULL,
 order_id varchar(80) NOT NULL,
 event_action varchar(48) NOT NULL,
 observed_status varchar(40) NOT NULL,
 payload_sha256 char(64) NOT NULL,
 live_mode boolean NOT NULL,
 received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 source varchar(40) NOT NULL DEFAULT 'SIGNED_ORDER_WEBHOOK_UNSETTLED',
 bank_reconciled boolean NOT NULL DEFAULT false,
 ledger_written boolean NOT NULL DEFAULT false,
 payment_marked_paid boolean NOT NULL DEFAULT false,
 PRIMARY KEY(tenant_id,event_id),
 UNIQUE(tenant_id,request_id),
 FOREIGN KEY(tenant_id,provider_account_id)
    REFERENCES public.mp_seller_connections_staging(tenant_id,seller_id)
    ON DELETE RESTRICT,
 CHECK(event_id ~ '^N_[A-Za-z0-9_-]{1,80}$'),
 CHECK(provider_account_id ~ '^[0-9]{1,40}$'),
 CHECK(request_id ~ '^[A-Za-z0-9._:-]{1,120}$'),
 CHECK(order_id ~ '^ORD[A-Z0-9]{12,77}$'),
 CHECK(event_action IN('order.created','order.processed','order.canceled','order.failed')),
 CHECK(observed_status IN('action_required','processed','failed','canceled')),
 CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
 CHECK(source='SIGNED_ORDER_WEBHOOK_UNSETTLED'),
 CHECK(bank_reconciled=false),
 CHECK(ledger_written=false),
 CHECK(payment_marked_paid=false)
);
CREATE INDEX mp_signed_order_inbox_tenant_received
 ON public.mp_signed_order_inbox_staging(tenant_id,received_at DESC);

ALTER TABLE public.mp_signed_order_inbox_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_signed_order_inbox_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON public.mp_signed_order_inbox_staging
 FROM PUBLIC,frcaixinha_mp_webhook_ingest;

CREATE OR REPLACE FUNCTION public.mp_staging_append_signed_order(
 p_tenant uuid,p_provider varchar,p_event varchar,
 p_request varchar,p_order varchar,p_action varchar,
 p_status varchar,p_hash varchar,p_live boolean
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE prev public.mp_signed_order_inbox_staging%ROWTYPE;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_webhook_ingest'
    OR p_tenant IS NULL
    OR p_provider !~ '^[0-9]{1,40}$'
    OR p_event !~ '^N_[A-Za-z0-9_-]{1,80}$'
    OR p_request !~ '^[A-Za-z0-9._:-]{1,120}$'
    OR p_order !~ '^ORD[A-Z0-9]{12,77}$'
    OR p_action NOT IN('order.created','order.processed','order.canceled','order.failed')
    OR p_status NOT IN('action_required','processed','failed','canceled')
    OR p_hash !~ '^[0-9a-f]{64}$'
    OR p_live IS NULL
    OR NOT EXISTS (
      SELECT 1 FROM public.mp_seller_connections_staging sc
      WHERE sc.tenant_id=p_tenant AND sc.seller_id=p_provider
        AND sc.revoked_at IS NULL
    ) THEN
    RAISE EXCEPTION 'M4500 DENIED: order notification scope';
 END IF;
 PERFORM pg_advisory_xact_lock(pg_catalog.hashtextextended(
      'FRC-MP-ORDERS|'||p_tenant||'|'||p_event,0));
 SELECT * INTO prev FROM public.mp_signed_order_inbox_staging
  WHERE tenant_id=p_tenant AND event_id=p_event;
 IF FOUND THEN
   IF prev.provider_account_id<>p_provider OR prev.request_id<>p_request
     OR prev.order_id<>p_order OR prev.event_action<>p_action
     OR prev.observed_status<>p_status
     OR prev.payload_sha256<>p_hash OR prev.live_mode<>p_live THEN
      RAISE EXCEPTION 'M4500 DENIED: duplicate event conflict';
   END IF;
   RETURN 'REPLAY';
 END IF;
 INSERT INTO public.mp_signed_order_inbox_staging(
   event_id,tenant_id,provider_account_id,request_id,
   order_id,event_action,observed_status,payload_sha256,live_mode
 ) VALUES (
   p_event,p_tenant,p_provider,p_request,p_order,p_action,p_status,p_hash,p_live
 );
 RETURN 'INSERTED';
END $$;

REVOKE ALL ON FUNCTION public.mp_staging_append_signed_order(
 uuid,varchar,varchar,varchar,varchar,varchar,varchar,varchar,boolean
) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.mp_staging_append_signed_order(
 uuid,varchar,varchar,varchar,varchar,varchar,varchar,varchar,boolean
) TO frcaixinha_mp_webhook_ingest;

-- No privileges to the app, no direct INSERT/UPDATE/DELETE, no money effect.
COMMIT;
