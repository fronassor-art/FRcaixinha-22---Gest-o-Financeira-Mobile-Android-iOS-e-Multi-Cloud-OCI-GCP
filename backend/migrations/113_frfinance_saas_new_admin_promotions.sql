-- FR Finance M39067 / SQL113: campanhas comerciais SaaS SEM cobrança/convites externos.
-- SQL112 precede este arquivo. ONLY frcaixinha_aistudio_dev PG18 native Termux.
-- Historico append-only (nova revisao DRAFT/PUBLISHED/CANCELED), sem UPDATE ou DELETE.
DO $m39067$
BEGIN
 IF current_database() <> 'frcaixinha_aistudio_dev'
 OR current_user <> 'frc_ai_owner' OR session_user <> 'frc_ai_owner'
 OR inet_server_port() <> 5433
 OR host(inet_server_addr()) <> '127.0.0.1'
 OR current_setting('data_directory') <> '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
 OR current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999
 OR NOT EXISTS (
    SELECT 1 FROM pg_catalog.pg_attribute
    WHERE attrelid=to_regclass('public.platform_license_price_versions')
      AND attname='annual_price' AND attgenerated='' AND NOT attisdropped
 )
 THEN RAISE EXCEPTION 'M39067_REQUIRES_ORIGINAL_PG18_SQL112';
 END IF;
END
$m39067$;

CREATE TABLE public.platform_saas_promotion_revisions (
 id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
 campaign_id uuid NOT NULL,
 revision integer NOT NULL CHECK (revision >= 1),
 plan_tier varchar(20) NOT NULL REFERENCES public.platform_license_plans(tier),
 billing_period varchar(10) NOT NULL CHECK (billing_period IN ('MONTHLY','ANNUAL')),
 base_price_version_id uuid NOT NULL REFERENCES public.platform_license_price_versions(id),
 promotional_price numeric(12,2) NOT NULL CHECK (promotional_price > 0 AND promotional_price <= 999999.99),
 audience varchar(24) NOT NULL CHECK (audience='NEW_ADMIN_ONLY'),
 title varchar(120) NOT NULL CHECK (length(trim(title)) BETWEEN 5 AND 120),
 benefit_description varchar(500) NOT NULL CHECK (length(trim(benefit_description)) >= 10),
 starts_at timestamptz NOT NULL,
 ends_at timestamptz NOT NULL,
 state varchar(16) NOT NULL CHECK (state IN ('DRAFT','PUBLISHED','CANCELED')),
 reason text NOT NULL CHECK (length(trim(reason)) BETWEEN 15 AND 500),
 created_by uuid NOT NULL REFERENCES public.users(id),
 created_at timestamptz NOT NULL DEFAULT now(),
 CHECK (starts_at < ends_at),
 UNIQUE(campaign_id,revision)
);

CREATE INDEX platform_saas_promotions_latest
 ON public.platform_saas_promotion_revisions(campaign_id,revision DESC);
CREATE INDEX platform_saas_promotions_period
 ON public.platform_saas_promotion_revisions(plan_tier,billing_period,starts_at,ends_at);

ALTER TABLE public.platform_saas_promotion_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.platform_saas_promotion_revisions FORCE ROW LEVEL SECURITY;

CREATE POLICY frfinance_saas_promo_master_select
 ON public.platform_saas_promotion_revisions FOR SELECT TO frcaixinha_app_role
 USING (
  current_setting('app.current_role',true)='MASTER'
  AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid)
 );

CREATE POLICY frfinance_saas_promo_master_insert
 ON public.platform_saas_promotion_revisions FOR INSERT TO frcaixinha_app_role
 WITH CHECK (
  current_setting('app.current_role',true)='MASTER'
  AND public.rls_is_master(NULLIF(current_setting('app.current_user_id',true),'')::uuid)
  AND created_by=NULLIF(current_setting('app.current_user_id',true),'')::uuid
 );

REVOKE ALL ON public.platform_saas_promotion_revisions
 FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role;
GRANT SELECT ON public.platform_saas_promotion_revisions TO frcaixinha_app_role;
GRANT INSERT(campaign_id,revision,plan_tier,billing_period,base_price_version_id,
 promotional_price,audience,title,benefit_description,starts_at,ends_at,
 state,reason,created_by) ON public.platform_saas_promotion_revisions TO frcaixinha_app_role;

-- Ponte de leitura limitada: administradores novos, autenticação do tenant validada.
-- Não entrega rascunhos/cancelamentos nem dados de outros administradores.
-- Não emite convite, cobrança, desconto automático, licença ou pagamento.
CREATE FUNCTION public.frfinance_saas_new_admin_published_promotions()
RETURNS TABLE(
 campaign_id uuid,plan_tier varchar,billing_period varchar,
 promotional_price numeric,title varchar,benefit_description varchar,
 starts_at timestamptz,ends_at timestamptz,revision integer,
 base_price_version_id uuid
)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public
AS $m39067_read$
DECLARE
 actor uuid;
 scoped_tenant uuid;
BEGIN
 IF current_setting('app.current_role',true) <> 'TENANT_ADMIN'
 OR NULLIF(current_setting('app.current_user_id',true),'') IS NULL
 OR NULLIF(current_setting('app.current_tenant_id',true),'') IS NULL
 THEN RETURN; END IF;
 BEGIN
  actor := current_setting('app.current_user_id',true)::uuid;
  scoped_tenant := current_setting('app.current_tenant_id',true)::uuid;
 EXCEPTION WHEN invalid_text_representation THEN RETURN;
 END;
 IF NOT EXISTS(
  SELECT 1 FROM public.tenants t
   WHERE t.id=scoped_tenant AND t.admin_user_id=actor AND t.status='ATIVO'
    AND public.rls_is_tenant_admin(actor,scoped_tenant)
 ) THEN RETURN; END IF;

 -- Novo administrador: sem preparações anteriores e sem licenças em seus tenants.
 IF EXISTS(SELECT 1 FROM public.saas_subscription_preparations sp
  WHERE sp.admin_user_id=actor) OR EXISTS(
   SELECT 1 FROM public.saas_license_entitlements e
    JOIN public.tenants t ON t.id=e.tenant_id WHERE t.admin_user_id=actor
 ) THEN RETURN; END IF;

 RETURN QUERY
 SELECT p.campaign_id,p.plan_tier,p.billing_period,p.promotional_price,
        p.title,p.benefit_description,p.starts_at,p.ends_at,p.revision,
        p.base_price_version_id
 FROM (
  SELECT DISTINCT ON (v.campaign_id) v.*
  FROM public.platform_saas_promotion_revisions v
  ORDER BY v.campaign_id,v.revision DESC
 ) p
 JOIN public.platform_license_plans lp ON lp.tier=p.plan_tier
 WHERE p.state='PUBLISHED' AND p.audience='NEW_ADMIN_ONLY'
   AND lp.status='ACTIVE'
   AND p.starts_at<=now() AND p.ends_at>now()
 ORDER BY p.ends_at,p.campaign_id;
END
$m39067_read$;

REVOKE ALL ON FUNCTION public.frfinance_saas_new_admin_published_promotions()
 FROM PUBLIC,frcaixinha_auth_role;
GRANT EXECUTE ON FUNCTION public.frfinance_saas_new_admin_published_promotions()
 TO frcaixinha_app_role;

COMMENT ON TABLE public.platform_saas_promotion_revisions IS
 'FR Finance SaaS marketing: append-only versions, new admins only; external dispatch, billing and activation OFF.';
