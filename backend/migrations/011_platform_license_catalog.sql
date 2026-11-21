-- AI Studio: catalogo e versoes de preco SaaS para o Master.
-- NAO cadastra assinatura paga, nao cobra Pix e nao consulta caixa dos tenants.
-- O ciclo de licenca depende de provedores/aceite ainda nao integrados.
CREATE TABLE public.platform_license_plans (
  tier varchar(20) PRIMARY KEY CHECK (tier IN ('ESSENCIAL','INTERMEDIARIO','AMPLIADO')),
  display_name varchar(100) NOT NULL,
  members_limit integer CHECK (members_limit > 0),
  quotas_limit integer CHECK (quotas_limit > 0),
  status varchar(40) NOT NULL CHECK (status IN ('ACTIVE','BLOCKED_PENDING_CEILING'))
);

CREATE TABLE public.platform_license_price_versions (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  plan_tier varchar(20) NOT NULL REFERENCES public.platform_license_plans(tier),
  monthly_price numeric(12,2) NOT NULL CHECK (monthly_price > 0),
  annual_price numeric(12,2) GENERATED ALWAYS AS (monthly_price * 10) STORED,
  changed_by uuid REFERENCES public.users(id),
  reason text NOT NULL CHECK (length(trim(reason)) >= 15),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX platform_license_price_lookup
  ON public.platform_license_price_versions(plan_tier,created_at DESC,id DESC);

INSERT INTO public.platform_license_plans(tier,display_name,members_limit,quotas_limit,status)
VALUES ('ESSENCIAL','Essencial',20,40,'ACTIVE'),
       ('INTERMEDIARIO','Intermediário',50,50,'ACTIVE'),
       ('AMPLIADO','Ampliado',NULL,NULL,'BLOCKED_PENDING_CEILING');

-- Valores iniciais ja previstos no catalogo demonstrativo do AI Studio;
-- nenhum cliente e cobrado por esses registros.
INSERT INTO public.platform_license_price_versions(plan_tier,monthly_price,reason)
VALUES ('ESSENCIAL',89.90,'Catalogo inicial documentado para homologacao'),
       ('INTERMEDIARIO',109.90,'Catalogo inicial documentado para homologacao');

ALTER TABLE public.platform_license_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_license_plans FORCE ROW LEVEL SECURITY;
ALTER TABLE public.platform_license_price_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_license_price_versions FORCE ROW LEVEL SECURITY;

CREATE POLICY platform_license_plans_master_read
ON public.platform_license_plans FOR SELECT TO frcaixinha_app_role
USING (
 current_setting('app.current_role',true)='MASTER'
 AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid)
);
CREATE POLICY platform_license_prices_master_read
ON public.platform_license_price_versions FOR SELECT TO frcaixinha_app_role
USING (
 current_setting('app.current_role',true)='MASTER'
 AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid)
);
CREATE POLICY platform_license_prices_master_append
ON public.platform_license_price_versions FOR INSERT TO frcaixinha_app_role
WITH CHECK (
 current_setting('app.current_role',true)='MASTER'
 AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid)
 AND changed_by=NULLIF(current_setting('app.current_user_id',true),'')::uuid
);

GRANT SELECT ON public.platform_license_plans TO frcaixinha_app_role;
GRANT SELECT ON public.platform_license_price_versions TO frcaixinha_app_role;
GRANT INSERT(plan_tier,monthly_price,changed_by,reason)
  ON public.platform_license_price_versions TO frcaixinha_app_role;
REVOKE UPDATE,DELETE,TRUNCATE
  ON public.platform_license_plans,public.platform_license_price_versions
  FROM PUBLIC,frcaixinha_app_role;
