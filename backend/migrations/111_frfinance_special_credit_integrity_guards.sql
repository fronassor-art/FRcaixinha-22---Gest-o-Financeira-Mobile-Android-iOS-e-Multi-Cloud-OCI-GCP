-- FR Finance AI Studio M39020 / SQL 111
-- ADITIVO DE SEGURANÇA À MIGRAÇÃO 110. CANDIDATO; NÃO EXECUTAR NO TERMUX.
-- NENHUM ENVIO EXTERNO OU MOVIMENTAÇÃO FINANCEIRA.
-- M39020: SQL110+111 MUST run together with psql --single-transaction.
-- Standalone -f without explicit session gate is intentionally forbidden.
DO $
DECLARE mode text := current_setting('frfinance.m39020_migration_mode',true);
BEGIN
 IF mode='CI_DISPOSABLE' THEN
   IF current_database()<>'frfinance_ci_credit' OR inet_server_port()<>5432
      OR session_user<>'postgres' THEN
     RAISE EXCEPTION 'M39020 CI must use disposable database';
   END IF;
 ELSIF mode='LOCAL_AUTHORIZED' THEN
   IF current_database()<>'frcaixinha_aistudio_dev'
      OR inet_server_port()<>5433 OR session_user<>'frc_ai_owner' THEN
     RAISE EXCEPTION 'M39020 local identity mismatch';
   END IF;
 ELSE
   RAISE EXCEPTION 'M39020 migration requires explicit atomic session gate';
 END IF;
END $;


DO $$
BEGIN
 IF to_regclass('public.special_credit_grants') IS NULL
    OR to_regclass('public.special_credit_campaigns') IS NULL
    OR to_regclass('public.special_credit_recipients') IS NULL
    OR to_regclass('public.special_credit_outbox') IS NULL THEN
   RAISE EXCEPTION 'M39020 exige SQL 110 íntegro; instalação parcial proibida';
 END IF;
END $$;

CREATE FUNCTION public.sc_m39020_guard_grant_update()
RETURNS trigger LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
 IF (to_jsonb(NEW)-'status'-'updated_at') IS DISTINCT FROM
    (to_jsonb(OLD)-'status'-'updated_at') THEN
   RAISE EXCEPTION 'M39020: concessão financeira imutável após criação';
 END IF;
 IF OLD.status<>'ACTIVE' OR NEW.status NOT IN ('REVOKED','EXPIRED') THEN
   RAISE EXCEPTION 'M39020: concessão revogada/expirada não pode ser reativada';
 END IF;
 IF NEW.updated_at < OLD.updated_at THEN
   RAISE EXCEPTION 'M39020: timestamp retroativo';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER sc_m39020_grant_transition
 BEFORE UPDATE ON public.special_credit_grants
 FOR EACH ROW EXECUTE FUNCTION public.sc_m39020_guard_grant_update();

CREATE FUNCTION public.sc_m39020_guard_campaign_update()
RETURNS trigger LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
 IF (to_jsonb(NEW)-'status'-'published_at') IS DISTINCT FROM
    (to_jsonb(OLD)-'status'-'published_at') THEN
   RAISE EXCEPTION 'M39020: conteúdo/destinatários da campanha imutáveis';
 END IF;
 IF NOT (
    (OLD.status='DRAFT' AND NEW.status IN ('PUBLISHED','CANCELLED'))
    OR (OLD.status='PUBLISHED' AND NEW.status='CANCELLED')
 ) THEN
   RAISE EXCEPTION 'M39020: transição de campanha não autorizada';
 END IF;
 IF NEW.status='PUBLISHED' THEN
   IF NEW.published_at IS NULL OR NEW.expires_at<=now() OR
      NOT EXISTS (SELECT 1 FROM public.special_credit_recipients r
        WHERE r.campaign_id=NEW.id AND r.tenant_id=NEW.tenant_id) OR
      EXISTS (
       SELECT 1 FROM public.special_credit_recipients r
       LEFT JOIN public.special_credit_grants g
        ON g.id=r.grant_id AND g.tenant_id=r.tenant_id
       LEFT JOIN public.memberships m
        ON m.id=r.member_id AND m.tenant_id=r.tenant_id
       WHERE r.campaign_id=NEW.id AND r.tenant_id=NEW.tenant_id
         AND (g.id IS NULL OR g.status<>'ACTIVE' OR g.expires_at<=now()
              OR g.expires_at<NEW.expires_at OR m.id IS NULL
              OR m.status<>'ATIVA' OR m.role<>'TENANT_MEMBER'
              OR m.user_id<>r.user_id)
      ) THEN
     RAISE EXCEPTION 'M39020: publicação depende de autorizações ativas';
   END IF;
 ELSE
   IF NEW.published_at IS DISTINCT FROM OLD.published_at THEN
     RAISE EXCEPTION 'M39020: cancelamento não pode reescrever data de publicação';
   END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER sc_m39020_campaign_transition
 BEFORE UPDATE ON public.special_credit_campaigns
 FOR EACH ROW EXECUTE FUNCTION public.sc_m39020_guard_campaign_update();

CREATE FUNCTION public.sc_m39020_recipient_consistency()
RETURNS trigger LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
 IF NOT EXISTS (
  SELECT 1 FROM public.special_credit_campaigns c
   JOIN public.special_credit_grants g
    ON g.cycle_id=c.cycle_id AND g.tenant_id=c.tenant_id
   JOIN public.memberships m
    ON m.id=g.member_id AND m.tenant_id=g.tenant_id
  WHERE c.id=NEW.campaign_id AND c.tenant_id=NEW.tenant_id
    AND c.status='DRAFT' AND c.expires_at>now()
    AND g.id=NEW.grant_id AND g.member_id=NEW.member_id
    AND g.status='ACTIVE' AND g.expires_at>=c.expires_at
    AND m.user_id=NEW.user_id AND m.role='TENANT_MEMBER'
    AND m.status='ATIVA'
 ) THEN
  RAISE EXCEPTION 'M39020: destinatário fora da caixinha, ciclo ou autorização';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER sc_m39020_recipient_insert
 BEFORE INSERT ON public.special_credit_recipients
 FOR EACH ROW EXECUTE FUNCTION public.sc_m39020_recipient_consistency();

CREATE FUNCTION public.sc_m39020_guard_reply()
RETURNS trigger LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
 IF (to_jsonb(NEW)-'response_status'-'responded_at') IS DISTINCT FROM
    (to_jsonb(OLD)-'response_status'-'responded_at') THEN
   RAISE EXCEPTION 'M39020: destinatário e tenant são imutáveis';
 END IF;
 IF OLD.response_status <> 'PENDING' OR
    NEW.response_status NOT IN ('INTERESTED','DECLINED') OR
    NEW.responded_at IS NULL OR
    NOT EXISTS (
      SELECT 1 FROM public.special_credit_campaigns c
       JOIN public.special_credit_grants g ON g.id=OLD.grant_id
       WHERE c.id=OLD.campaign_id AND c.tenant_id=OLD.tenant_id
        AND c.status='PUBLISHED' AND c.expires_at>now()
        AND g.tenant_id=OLD.tenant_id AND g.status='ACTIVE'
        AND g.expires_at>now()
    ) THEN
  RAISE EXCEPTION 'M39020: resposta duplicada, expirada ou inválida';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER sc_m39020_reply_transition
 BEFORE UPDATE ON public.special_credit_recipients
 FOR EACH ROW EXECUTE FUNCTION public.sc_m39020_guard_reply();

CREATE FUNCTION public.sc_m39020_outbox_consistency()
RETURNS trigger LANGUAGE plpgsql SET search_path=public,pg_temp AS $$
BEGIN
 IF NEW.state <> 'BLOCKED_EXTERNAL' OR NOT EXISTS (
  SELECT 1 FROM public.special_credit_recipients r
   JOIN public.special_credit_campaigns c
    ON c.id=r.campaign_id AND c.tenant_id=r.tenant_id
   JOIN public.special_credit_preferences p
    ON p.user_id=r.user_id AND p.tenant_id=r.tenant_id
  WHERE r.id=NEW.recipient_id AND r.tenant_id=NEW.tenant_id
    AND r.campaign_id=NEW.campaign_id AND c.status='PUBLISHED'
    AND c.expires_at>now() AND p.channel=NEW.channel
    AND p.opted_in=true
 ) THEN
  RAISE EXCEPTION 'M39020: fila externa bloqueada ou sem preferência válida';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER sc_m39020_outbox_insert
 BEFORE INSERT ON public.special_credit_outbox
 FOR EACH ROW EXECUTE FUNCTION public.sc_m39020_outbox_consistency();

-- Banco impede ressurreição/duplicação de concessão, mutação tardia
-- de campanhas, injeção de destinatários e enfileiramento sem opt-in.
-- O worker de delivery NÃO faz parte desta migração.
