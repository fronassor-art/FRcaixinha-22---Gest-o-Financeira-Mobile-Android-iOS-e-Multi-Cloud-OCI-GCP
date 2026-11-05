-- AI Studio M2900: STAGING OCI ONLY. NOT Termux/CI/production.
-- Requires DBA-controlled isolated database and dedicated login created first.
-- CREATE ROLE frcaixinha_mp_webhook_ingest LOGIN ... NOBYPASSRLS NOSUPERUSER
-- Atomic from preflight through grants: any failure rolls back all objects.
BEGIN;
DO $guard$
BEGIN
 IF current_database() <> 'frcaixinha_staging'
    OR current_setting('frcaixinha.mp_staging_authorized',true) IS DISTINCT FROM '1'
    OR NOT EXISTS (
      SELECT 1 FROM pg_roles WHERE rolname='frcaixinha_mp_webhook_ingest'
        AND NOT rolsuper AND NOT rolbypassrls
    )
    OR current_setting('is_superuser') <> 'on' THEN
   RAISE EXCEPTION 'BLOQUEADO M034: somente DBA do staging OCI autorizado';
 END IF;
END $guard$;

CREATE TABLE public.mp_seller_connections_staging (
 tenant_id uuid NOT NULL REFERENCES public.tenants(id) ON DELETE RESTRICT,
 seller_id varchar(40) NOT NULL UNIQUE CHECK (seller_id ~ '^[0-9]{1,40}$'),
 webhook_secret_ocid text NOT NULL
   CHECK (webhook_secret_ocid ~ '^ocid1[.]secret[.][A-Za-z0-9._-]{8,512}$'),
 verified_at timestamptz NOT NULL,
 revoked_at timestamptz,
 PRIMARY KEY(tenant_id,seller_id),
 CHECK (revoked_at IS NULL OR revoked_at >= verified_at)
);
CREATE TABLE public.mp_signed_webhook_inbox_staging (
 notification_id varchar(100) PRIMARY KEY CHECK (notification_id ~ '^[A-Za-z0-9_-]{1,100}$'),
 tenant_id uuid NOT NULL,
 seller_id varchar(40) NOT NULL,
 request_id varchar(120) UNIQUE NOT NULL CHECK(request_id ~ '^[A-Za-z0-9._:-]{1,120}$'),
 resource_id varchar(100) NOT NULL CHECK(resource_id ~ '^[A-Za-z0-9_-]{1,100}$'),
 event_type varchar(16) NOT NULL CHECK(event_type IN('payment','mp-connect')),
 event_action varchar(48) NOT NULL CHECK(event_action IN(
    'payment.created','payment.updated','application.authorized','application.deauthorized')),
 payload_sha256 varchar(64) NOT NULL CHECK(payload_sha256 ~ '^[0-9a-f]{64}$'),
 live_mode boolean NOT NULL,
 received_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 source varchar(40) NOT NULL DEFAULT 'SIGNED_WEBHOOK_UNSETTLED'
  CHECK(source='SIGNED_WEBHOOK_UNSETTLED'),
 payment_marked_paid boolean NOT NULL DEFAULT false CHECK(payment_marked_paid=false),
 ledger_written boolean NOT NULL DEFAULT false CHECK(ledger_written=false),
 bank_reconciled boolean NOT NULL DEFAULT false CHECK(bank_reconciled=false),
 financial_closing_authorized boolean NOT NULL DEFAULT false CHECK(financial_closing_authorized=false),
 FOREIGN KEY(tenant_id,seller_id)
  REFERENCES public.mp_seller_connections_staging(tenant_id,seller_id) ON DELETE RESTRICT
);
CREATE INDEX mp_signed_webhook_inbox_tenant_date
 ON public.mp_signed_webhook_inbox_staging(tenant_id,received_at DESC);

ALTER TABLE public.mp_seller_connections_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_seller_connections_staging FORCE ROW LEVEL SECURITY;
ALTER TABLE public.mp_signed_webhook_inbox_staging ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.mp_signed_webhook_inbox_staging FORCE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.mp_seller_connections_staging,
 public.mp_signed_webhook_inbox_staging
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,
 frcaixinha_verifier_role,frcaixinha_mp_webhook_ingest;

CREATE FUNCTION public.mp_staging_resolve_seller(p_seller varchar)
RETURNS TABLE(tenant_id uuid,seller_id varchar,webhook_secret_ocid text)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_webhook_ingest' THEN
   RAISE EXCEPTION 'BLOQUEADO: staging webhook resolve';
 END IF;
 RETURN QUERY
 SELECT c.tenant_id,c.seller_id,c.webhook_secret_ocid
 FROM public.mp_seller_connections_staging c
 WHERE c.seller_id=p_seller AND c.revoked_at IS NULL;
END $$;

CREATE FUNCTION public.mp_staging_append_signed_webhook(
 p_tenant uuid,p_seller varchar,p_notification varchar,
 p_request varchar,p_resource varchar,p_type varchar,p_action varchar,
 p_sha varchar,p_live boolean
) RETURNS text
LANGUAGE plpgsql SECURITY DEFINER
SET search_path=pg_catalog,public,pg_temp AS $$
DECLARE old_row public.mp_signed_webhook_inbox_staging%ROWTYPE;
BEGIN
 IF current_database()<>'frcaixinha_staging'
    OR session_user<>'frcaixinha_mp_webhook_ingest'
    OR p_tenant IS NULL OR p_seller !~ '^[0-9]{1,40}$'
    OR p_notification !~ '^[A-Za-z0-9_-]{1,100}$'
    OR p_request !~ '^[A-Za-z0-9._:-]{1,120}$'
    OR p_resource !~ '^[A-Za-z0-9_-]{1,100}$'
    OR p_type NOT IN ('payment','mp-connect')
    OR p_action NOT IN ('payment.created','payment.updated',
                       'application.authorized','application.deauthorized')
    OR (p_type='payment' AND p_action NOT LIKE 'payment.%')
    OR (p_type='mp-connect' AND p_action NOT LIKE 'application.%')
    OR p_sha !~ '^[0-9a-f]{64}$' OR p_live IS NULL
    OR NOT EXISTS (
       SELECT 1 FROM public.mp_seller_connections_staging c
       WHERE c.tenant_id=p_tenant AND c.seller_id=p_seller
        AND c.revoked_at IS NULL
    ) THEN
    RAISE EXCEPTION 'BLOQUEADO: webhook nao autorizado';
 END IF;
 PERFORM pg_advisory_xact_lock(hashtextextended(
    'FRC-MP-STAGING-WEBHOOK|'||p_notification,0));
 SELECT * INTO old_row FROM public.mp_signed_webhook_inbox_staging
 WHERE notification_id=p_notification;
 IF FOUND THEN
   IF old_row.tenant_id<>p_tenant OR old_row.seller_id<>p_seller
       OR old_row.request_id<>p_request OR old_row.resource_id<>p_resource
       OR old_row.event_type<>p_type OR old_row.event_action<>p_action
       OR old_row.payload_sha256<>p_sha OR old_row.live_mode<>p_live THEN
      RAISE EXCEPTION 'BLOQUEADO: webhook duplicado com conteudo diferente';
   END IF;
   RETURN 'REPLAY';
 END IF;
 INSERT INTO public.mp_signed_webhook_inbox_staging(
   notification_id,tenant_id,seller_id,request_id,resource_id,
   event_type,event_action,payload_sha256,live_mode
 ) VALUES (
   p_notification,p_tenant,p_seller,p_request,p_resource,
   p_type,p_action,p_sha,p_live
 );
 RETURN 'INSERTED';
END $$;

REVOKE ALL ON FUNCTION public.mp_staging_resolve_seller(varchar),
 public.mp_staging_append_signed_webhook(
   uuid,varchar,varchar,varchar,varchar,varchar,varchar,varchar,boolean)
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role;
GRANT EXECUTE ON FUNCTION public.mp_staging_resolve_seller(varchar),
 public.mp_staging_append_signed_webhook(
   uuid,varchar,varchar,varchar,varchar,varchar,varchar,varchar,boolean)
 TO frcaixinha_mp_webhook_ingest;

COMMIT;
