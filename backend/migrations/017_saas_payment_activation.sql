-- AI Studio 017: motor de cobrança SaaS separado dos fundos das caixinhas.
-- A API comum pode CONSULTAR conforme RLS. Nenhum papel app/auth pode pagar,
-- ativar ou registrar conciliacao. Operacoes reais dependem de autorizacao
-- juridica, provedor, segredo e servico segregado revisado.
CREATE TABLE public.saas_payment_intents (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  preparation_id uuid NOT NULL REFERENCES public.saas_subscription_preparations(id),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  admin_user_id uuid NOT NULL REFERENCES public.users(id),
  price_version_id uuid NOT NULL REFERENCES public.platform_license_price_versions(id),
  expected_amount_cents bigint NOT NULL CHECK(expected_amount_cents > 0),
  currency char(3) NOT NULL DEFAULT 'BRL' CHECK(currency='BRL'),
  external_reference varchar(100) NOT NULL UNIQUE,
  idempotency_key varchar(64) NOT NULL UNIQUE,
  provider varchar(20) NOT NULL DEFAULT 'MERCADO_PAGO' CHECK(provider='MERCADO_PAGO'),
  provider_payment_id varchar(40) UNIQUE CHECK(provider_payment_id ~ '^[0-9]{1,40}$'),
  platform_collector_id varchar(40) NOT NULL CHECK(platform_collector_id ~ '^[0-9]{1,40}$'),
  live_mode boolean NOT NULL,
  status varchar(24) NOT NULL DEFAULT 'PENDING'
    CHECK(status IN ('PENDING','APPROVED','REJECTED','CANCELED','REFUNDED')),
  paid_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  reconciled_at timestamptz,
  UNIQUE(preparation_id,id)
);
CREATE UNIQUE INDEX saas_one_open_payment_per_preparation
  ON public.saas_payment_intents(preparation_id)
  WHERE status IN ('PENDING','APPROVED');
CREATE INDEX saas_payment_tenant_history ON public.saas_payment_intents(tenant_id,created_at DESC);
CREATE TABLE public.saas_license_entitlements (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  preparation_id uuid NOT NULL UNIQUE REFERENCES public.saas_subscription_preparations(id),
  payment_intent_id uuid NOT NULL UNIQUE REFERENCES public.saas_payment_intents(id),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  plan_tier varchar(20) NOT NULL REFERENCES public.platform_license_plans(tier),
  status varchar(20) NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','SUSPENDED','EXPIRED','REVOKED')),
  valid_from timestamptz NOT NULL,
  valid_until timestamptz NOT NULL CHECK(valid_until > valid_from),
  activated_at timestamptz NOT NULL DEFAULT now(),
  suspended_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX saas_entitlement_tenant ON public.saas_license_entitlements(tenant_id,valid_until DESC);
CREATE TABLE public.saas_provider_webhook_receipts (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  provider varchar(20) NOT NULL DEFAULT 'MERCADO_PAGO' CHECK(provider='MERCADO_PAGO'),
  provider_payment_id varchar(40) NOT NULL,
  provider_request_id varchar(128) NOT NULL,
  signature_timestamp bigint NOT NULL,
  payload_digest char(64) NOT NULL CHECK(payload_digest ~ '^[0-9a-f]{64}$'),
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  verified boolean NOT NULL DEFAULT false,
  UNIQUE(provider,provider_request_id)
);
-- Estas tabelas nunca sao o ledger interno de contribuicoes.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['saas_payment_intents','saas_license_entitlements','saas_provider_webhook_receipts']
  LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY',t);
    EXECUTE format('ALTER TABLE public.%I FORCE ROW LEVEL SECURITY',t);
  END LOOP;
END $$;
CREATE POLICY saas_payment_master_read
ON public.saas_payment_intents FOR SELECT TO frcaixinha_app_role
USING(current_setting('app.current_role',true)='MASTER'
 AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid));
CREATE POLICY saas_payment_admin_read
ON public.saas_payment_intents FOR SELECT TO frcaixinha_app_role
USING(current_setting('app.current_role',true)='TENANT_ADMIN'
 AND tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
 AND admin_user_id=NULLIF(current_setting('app.current_user_id',true),'')::uuid
 AND public.rls_is_tenant_admin(
 NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id));
CREATE POLICY saas_entitlement_master_read
ON public.saas_license_entitlements FOR SELECT TO frcaixinha_app_role
USING(current_setting('app.current_role',true)='MASTER'
 AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid));
CREATE POLICY saas_entitlement_admin_read
ON public.saas_license_entitlements FOR SELECT TO frcaixinha_app_role
USING(current_setting('app.current_role',true)='TENANT_ADMIN'
 AND tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
 AND public.rls_is_tenant_admin(
 NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id));
GRANT SELECT ON public.saas_payment_intents,public.saas_license_entitlements
 TO frcaixinha_app_role;
REVOKE ALL ON public.saas_provider_webhook_receipts FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE
 ON public.saas_payment_intents,public.saas_license_entitlements,public.saas_provider_webhook_receipts
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role;
