# AI Studio — P0-01d: transição de perfil e tenant protegida no PostgreSQL

**Referência:** 02/11/2026, fuso America/Belem. **Escopo exclusivo:** exportação do AI Studio em `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`, branch `atualizacao-ai-studio-9b46a63187`, PR #2 DRAFT. Este projeto **não** é o outro aplicativo independente de nome semelhante.

## Implementado em código na branch, condicionado à CI

- **Migração 023** `backend/migrations/023_session_context_guarded_transition.sql`: revoga `UPDATE` direto das colunas `active_role` e `active_tenant_id` ao papel técnico `frcaixinha_auth_role`.
- Introduz `public.auth_promote_pending_session(text,varchar,uuid)` com `SECURITY DEFINER`, validação do token bruto pelo hash armazenado, bloqueio de linha `FOR UPDATE`, usuário ativo, sessão provisória não revogada/não expirada, papel MASTER legítimo ou vínculo ativo de tenant. O retorno é a expiração efetivamente aplicada, respeitando 15 minutos de inatividade e limite absoluto de 8h.
- Introduz `public.auth_switch_session_context(text,varchar,uuid)`, que revalida **tanto o papel de origem quanto o destino**, incluindo tenant ativo, vínculo, usuário e sessão, na mesma transação sob lock.
- Os dois procedimentos são executáveis pelo papel técnico de autenticação, **não** pelo papel financeiro do aplicativo. `backend/app/routers/auth.py` deixa de fazer `UPDATE` direto das colunas protegidas.
- Atualiza testes sintéticos de PostgreSQL 16: credencial Auth não altera perfil/tenant diretamente; promoção ilegítima não passa; promoção e troca válidas passam; troca para caixinha não autorizada e token revogado são negados. PostgreSQL 18 confere privilégios e a presença das novas funções em migração de transação única.
- A sequência versionada passa de **001–022 para 001–023**. GitHub Actions testa migrações em bancos descartáveis; nenhuma aplicação local é autorizada.

## Segurança residual — NÃO CONSIDERAR PRODUÇÃO

A conta técnica `frcaixinha_auth_role` **ainda pode INSERT uma sessão provisória para um user_id arbitrário** e executar a função de promoção com o token que ela mesma gerou, caso seja comprometida. Isso significa que a mitigação atual protege sessões ativas contra `UPDATE` direto do contexto, mas **ainda não garante proteção contra a falsificação de sessão por comprometimento do papel técnico de Auth**.

Além disso, o papel de autenticação pode alterar outras colunas de sessões, inclusive expiração e revogação; essas capacidades precisam de redução com funções autorizadas de escopo próprio, e a emissão deve ser ligada a uma verificação de credenciais independente em fluxo transacional. Rate-limit de login permanece apenas em memória de processo. Não declarar login seguro para internet nem integração financeira operacional.

As 147 cláusulas e o backlog histórico de 37 tarefas exigem reclassificação posterior baseada em provas item a item. Não declarar resolução integral de P0-01.

## Controles operacionais

- A `main` não deve sofrer merge antes de autorização expressa. PR #2 permanece em rascunho.
- Não criar contas humanas, credenciais reais ou convites, não ativar serviços de pagamento ou operações financeiras, não instalar APK.
- **Não aplicar migrations 001–023 no Termux.** A última leitura enviada pelo operador identificou `frcaixinha_aistudio_dev`, PostgreSQL 18.6 na porta 5433, com zero tabelas. `backend/scripts/aistudio_db_local.sh check` é a única verificação local aprovada nesta rodada.
- Confirmar **cinco jobs verdes no commit final**, antes de orientar `git fetch` e `git merge --ff-only` com HEAD remoto exato e árvore local limpa.

## Próximo pacote de segurança

Reduzir o risco de `INSERT` de sessões provisórias arbitrárias com separação entre validação de credenciais e emissão; impedir alterações não vinculadas ao token em `expires_at` e `revoked_at`; testar concorrência e isolamento em três tenants e fazer auditoria explícita dos privilégios efetivos do papel do PostgreSQL.
