-- FR Finance M39066 / SQL112: preco mensal/anual SaaS independentes pelo Master.
-- EXECUTAR SOMENTE no PG18 ORIGINAL 127.0.0.1:5433/frcaixinha_aistudio_dev
-- por instalador revisado com backup e aprovacao expressa. NUNCA no FR 2.2.
-- Uma unica transacao de DDL, sem DELETE/UPDATE de historico, sem cobranca.
-- A coluna annual_price nasceu GENERATED ALWAYS AS monthly_price * 10 na 011.
-- DROP EXPRESSION mantem o valor ja armazenado para CADA versao historica.
DO $fr_m39066$
DECLARE generated_flag char;
BEGIN
  IF current_database() <> 'frcaixinha_aistudio_dev'
     OR current_user <> 'frc_ai_owner'
     OR session_user <> 'frc_ai_owner'
     OR inet_server_port() <> 5433
     OR host(inet_server_addr()) <> '127.0.0.1'
     OR current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999
     OR current_setting('data_directory') <> '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
  THEN
    RAISE EXCEPTION 'M39066_WRONG_ORIGINAL_POSTGRESQL_IDENTITY';
  END IF;

  SELECT a.attgenerated INTO generated_flag
  FROM pg_catalog.pg_attribute a
  WHERE a.attrelid = to_regclass('public.platform_license_price_versions')
    AND a.attname = 'annual_price'
    AND NOT a.attisdropped;

  IF generated_flag IS DISTINCT FROM 's'
     OR to_regclass('public.platform_license_plans') IS NULL
  THEN
    RAISE EXCEPTION 'M39066_LEGACY_GENERATED_ANNUAL_COLUMN_REQUIRED_STOP';
  END IF;
  IF EXISTS (
    SELECT 1 FROM public.platform_license_price_versions
    WHERE annual_price IS NULL OR annual_price <= 0
  ) THEN
    RAISE EXCEPTION 'M39066_INVALID_EXISTING_PRICE_VERSION';
  END IF;
END
$fr_m39066$;

-- Preserva os anos historicos antes calculados e DESFAZ a formula obrigatoria.
ALTER TABLE public.platform_license_price_versions
  ALTER COLUMN annual_price DROP EXPRESSION;

ALTER TABLE public.platform_license_price_versions
  ALTER COLUMN annual_price SET NOT NULL;

ALTER TABLE public.platform_license_price_versions
  ADD CONSTRAINT platform_license_annual_price_positive
  CHECK (annual_price > 0 AND annual_price <= 999999.99);

-- O papel de aplicacao nao recebe UPDATE/DELETE; apenas novas versoes imutaveis
-- com mensalidade E anuidade informadas pelo Master e verificadas por RLS.
GRANT INSERT (annual_price)
  ON public.platform_license_price_versions TO frcaixinha_app_role;

REVOKE UPDATE, DELETE, TRUNCATE
  ON public.platform_license_price_versions
  FROM PUBLIC, frcaixinha_app_role, frcaixinha_auth_role;

COMMENT ON COLUMN public.platform_license_price_versions.annual_price IS
  'Preco anual independente em BRL, definido pelo Master; versoes anteriores preservadas. Nunca recalcular retroativamente.';

-- Mantem em vigor RLS/FORCE RLS, indice de versoes, FK e relacoes
-- saas_subscription_preparations.price_version_id ja existentes.
-- Nao ativa plano AMPLIADO nem altera cobrancas, licencas ou membros.
