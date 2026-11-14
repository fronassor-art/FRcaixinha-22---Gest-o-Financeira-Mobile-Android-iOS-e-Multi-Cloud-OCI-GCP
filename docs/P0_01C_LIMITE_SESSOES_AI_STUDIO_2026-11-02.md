# Projeto AI Studio — P0-01c: emissão provisória e limite de sessão

**Referência:** 02/11/2026 (America/Belem). Repositório AI Studio exclusivo `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`, branch `atualizacao-ai-studio-9b46a63187`, PR #2 ainda DRAFT; nenhuma operação sobre o outro projeto independente.

## Alterações versionadas (não aplicadas no celular)

1. **Migração 022** em `backend/migrations/022_auth_session_issuance_limits.sql`: a política PostgreSQL `sessions_auth_insert` passa a permitir que o papel `frcaixinha_auth_role` insira apenas a sessão provisória `PENDING_CONTEXT`, sem tenant, sem revogação e com validade de até dois minutos. O login de homologação já utiliza `PENDING_CONTEXT` por 90 segundos e promove a sessão em transação; tentativas de inserir diretamente um papel ativo são negadas por RLS.
2. **Teto de oito horas (provisório em homologação):** `sessions_absolute_8h_guard` impede que `expires_at` ultrapasse `created_at + 8 horas`, mesmo quando a conta técnica pode alterar `expires_at`. A dependência FastAPI `get_current_session` preserva o timeout de inatividade de 15 minutos, limitando renovação ao teto absoluto com `LEAST(...)`. Este teto é provisório para homologação, sujeito a decisão de segurança e adequação documental antes de produção.
3. **Regressões de CI:** PostgreSQL 16 rejeita INSERT de sessão ativa e provisória longa pela role Auth; testa que o refresh não ultrapassa oito horas, que contextos continuam isolados e que uma leitura concorrente bloqueada por lock recebe 401 após a revogação. PostgreSQL 18 confere a migração 022, a política de INSERT e a constraint.
4. Pipeline descartável e script local **futuro** passam a listar 001–022, com guardas de pré-condição. Nenhuma migration é aplicada em aparelho nesta rodada.

## Limites de segurança: não declarar resolvido

**O privilégio de UPDATE do papel Auth ainda permite alterar `active_role`, `active_tenant_id`, `expires_at` e `revoked_at` diretamente.** A restrição de INSERT é uma redução mensurável de superfície, **não uma solução integral para credenciais Auth comprometidas**: um agressor que controlar a conta técnica ainda poderá emitir sessão provisória arbitrária e promovê-la. O fechamento desse risco exige separar a emissão da verificação de senha, remover UPDATE direto sobre contextos e usar chamadas DB transacionais com verificação e autoria independente; não abrir produção antes disso.

O controle de força bruta segue em memória de processo, não é distribuído. Também faltam testes de concorrência sob carga, revogação em clusters separados, TLS/cookies, recovery, cadastro produtivo, provas de dispositivo e AT-01…50 integrais. A matriz histórica de 147 requisitos e a lista de 37 tarefas não são recalculadas automaticamente.

## Critérios de saída e restrições

- Cinco jobs GitHub Actions **no último commit**, incluindo FastAPI, PostgreSQL 16, PostgreSQL 18, frontend e APK debug.
- `main` intacta e PR #2 em rascunho. Não instalar APK debug nem declarar operação real.
- O banco exclusivo AI Studio no Termux estava em PostgreSQL 18.6, porta 5433, `frcaixinha_aistudio_dev`, sem tabelas na última leitura do operador. **Proibido executar `apply` ou `verify` no Termux sem autorização específica.** Usar apenas `check`.
- Sincronizar o clone local apenas depois de CI verde, com branch limpa e `git merge --ff-only`, sem reset, force push ou merge na main.

**Próxima ação técnica:** investigar a separação real de privilégios de emissão de sessões e bloquear mudanças arbitrárias de papel/tenant por credencial técnica Auth comprometida; seguir com isolamento entre múltiplos tenants.
