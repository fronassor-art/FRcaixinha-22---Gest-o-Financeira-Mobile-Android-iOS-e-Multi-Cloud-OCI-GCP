-- AI Studio 016: controle documental SaaS SEM cobrança e SEM ativação real.
-- Nenhuma assinatura pode ficar ACTIVE até existir conciliação e decisão posterior.
CREATE TABLE public.saas_subscription_preparations (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id uuid NOT NULL REFERENCES public.tenants(id),
  admin_user_id uuid NOT NULL REFERENCES public.users(id),
  plan_tier varchar(20) NOT NULL REFERENCES public.platform_license_plans(tier),
  price_version_id uuid NOT NULL REFERENCES public.platform_license_price_versions(id),
  billing_period varchar(10) NOT NULL CHECK (billing_period IN ('MONTHLY','ANNUAL')),
  contract_acceptance_id uuid NOT NULL REFERENCES public.contract_acceptances(id),
  status varchar(28) NOT NULL DEFAULT 'PENDING_PAYMENT'
    CHECK(status IN ('PENDING_PAYMENT','PAUSED_NO_PAYMENT','CANCELED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  canceled_at timestamptz,
  CHECK (canceled_at IS NULL OR status='CANCELED'),
  UNIQUE(tenant_id,admin_user_id,contract_acceptance_id)
);
CREATE INDEX saas_subscription_preparation_tenant
  ON public.saas_subscription_preparations(tenant_id,created_at DESC);
ALTER TABLE public.saas_subscription_preparations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saas_subscription_preparations FORCE ROW LEVEL SECURITY;
CREATE POLICY saas_subscription_master_read
  ON public.saas_subscription_preparations FOR SELECT TO frcaixinha_app_role
  USING (
    current_setting('app.current_role',true)='MASTER'
    AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid)
  );
CREATE POLICY saas_subscription_tenant_admin_read
  ON public.saas_subscription_preparations FOR SELECT TO frcaixinha_app_role
  USING (
    current_setting('app.current_role',true)='TENANT_ADMIN'
    AND tenant_id=NULLIF(current_setting('app.current_tenant_id',true),'')::uuid
    AND admin_user_id=NULLIF(current_setting('app.current_user_id',true),'')::uuid
    AND public.rls_is_tenant_admin(
      NULLIF(current_setting('app.current_user_id',true),'')::uuid,tenant_id
    )
  );
GRANT SELECT ON public.saas_subscription_preparations TO frcaixinha_app_role;
REVOKE INSERT,UPDATE,DELETE,TRUNCATE ON public.saas_subscription_preparations
  FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role;
-- Alterações pelo Master no catálogo comercial não alteram a versão da oferta já preparada.
-- IMPORTANTE: a ausência de status ACTIVE é intencional; simulação não gera fatura/receita.
