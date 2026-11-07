-- AI Studio 022 — limite de emissao e validade de sessoes de homologacao.
-- Apenas versionamento / testes descartaveis CI: nao aplicar no Termux.
-- Nao libera login em producao e nao cria contas, tenants nem movimentos reais.
--
-- O papel de autenticacao nao pode INSERT diretamente uma sessao ativa: o
-- caminho autorizado e PENDING_CONTEXT (90 s) -> promocao na mesma transacao
-- apos verificacao da senha e selecao de papel permitida pelo servidor.
--
-- RISCO RESIDUAL: o papel Auth ainda pode fazer UPDATE de active_role/tenant
-- e criar tokens PENDING para IDs arbitrarios se suas credenciais vazarem.
-- A separacao independente do emissor requer projeto e testes especificos.
-- Esta politica nao e uma prova de resistencia a comprometimento do Auth.

ALTER TABLE public.sessions
  ADD CONSTRAINT sessions_absolute_8h_guard
  CHECK (expires_at <= created_at + INTERVAL '8 hours');

DROP POLICY sessions_auth_insert ON public.sessions;
CREATE POLICY sessions_auth_insert ON public.sessions
  FOR INSERT TO frcaixinha_auth_role
  WITH CHECK (
    active_role = 'PENDING_CONTEXT'
    AND active_tenant_id IS NULL
    AND revoked_at IS NULL
    AND expires_at <= created_at + INTERVAL '2 minutes'
  );

DO $guard$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.sessions'::regclass
      AND conname='sessions_absolute_8h_guard'
  )
     OR NOT EXISTS (
       SELECT 1 FROM pg_policies
       WHERE schemaname='public'
         AND tablename='sessions'
         AND policyname='sessions_auth_insert'
         AND cmd='INSERT'
         AND with_check LIKE '%PENDING_CONTEXT%'
     )
     OR has_table_privilege('frcaixinha_app_role','public.sessions','INSERT')
     OR has_table_privilege('frcaixinha_app_role','public.sessions','UPDATE')
  THEN
    RAISE EXCEPTION 'BLOQUEADO: limite de sessao ou politica do Auth ausente';
  END IF;
END $guard$;
