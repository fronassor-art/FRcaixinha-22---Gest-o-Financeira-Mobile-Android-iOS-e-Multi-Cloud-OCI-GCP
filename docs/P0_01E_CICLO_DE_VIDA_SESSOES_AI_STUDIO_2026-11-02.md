# Projeto AI Studio — P0-01e: ciclo de vida de sessões por token

**Data de elaboração:** 02/11/2026 — America/Belem. Repositório exclusivo do AI Studio: `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`, branch `atualizacao-ai-studio-9b46a63187`, PR #2 DRAFT. Não utilizar dados ou regras do outro projeto independente.

## Alterações preparadas (nenhuma aplicada no aparelho)

A migração **024**, `backend/migrations/024_token_bound_session_lifecycle.sql`, revoga a permissão SQL direta de `UPDATE` das colunas `expires_at` e `revoked_at` para `frcaixinha_auth_role`.

As quatro funções `SECURITY DEFINER` abaixo são concedidas apenas ao papel de autenticação, revogando `EXECUTE` de `PUBLIC` e mantendo o papel financeiro sem acesso:

- `auth_refresh_session(text)`: renova somente a própria sessão ainda válida, com token bruto, usuário `ACTIVE`, contexto vigente e limites de inatividade (15 minutos) e absolutos (8 horas). Usa `FOR UPDATE`, evitando reativação após revogação concorrente.
- `auth_revoke_session(text)`: revoga apenas a sessão correspondente ao token bruto recebido; não aceita UUID ou hash armazenado como identificador.
- `auth_revoke_all_sessions(text)`: identifica o próprio usuário por sessão não revogada e não expirada e revoga as sessões desse usuário em transação, sem aceitar user_id informado pelo cliente.
- `auth_revoke_owned_session(text,uuid)`: revoga somente a sessão-alvo se pertencer à identidade autenticada; código 0 não revela existência de sessões de terceiros, código 1 revoga outra sessão própria, código 2 revoga a sessão atual.

O FastAPI passa a usar essas funções nas rotas `/auth/logout`, `/auth/logout-all`, `/auth/sessions/{session_id}/revoke` e na dependência `get_current_session`. Sem alteração de interface de autenticação do frontend. A sequência versionada e os dois pipelines PostgreSQL passam a contemplar **001–024**, apenas em bancos descartáveis de CI.

## Testes de segurança e escopo

- PostgreSQL 16: negar SQL direto de alteração de expiração e revogação pela conta técnica; testar renovação de token válido, recusa de token aleatório, impossibilidade de revogar sessão de outro usuário e preservação dos testes anteriores de login, logout global, logout específico e contexto multiempresa.
- PostgreSQL 18: conferir os privilégios por coluna e a capacidade exclusiva do papel Auth de executar funções; validar em transação única as migrações 001–024.
- Manter os cinco jobs do GitHub Actions obrigatórios (frontend, FastAPI, PostgreSQL 16, PostgreSQL 18 e APK debug) para considerar o commit sincronizável.

## Riscos e bloqueios mantidos

**Não está resolvida a falsificação de sessões caso a credencial técnica Auth seja comprometida.** O papel técnico ainda pode inserir uma sessão `PENDING_CONTEXT` para identidade arbitrária e invocar uma promoção de contexto. A próxima medida de arquitetura deve retirar esse poder, separando comprovação de senha de emissão de sessão com credenciais e fronteiras de confiança independentes. A simples criação de uma função `SECURITY DEFINER` não substitui prova independente de senha.

Persistem outros limites: leitura direta ampla de `public.sessions` pelo papel Auth, rate limiting somente por processo, falta de TLS/cookies produtivos, recuperação de senha, implantação real, revisão jurídica e testes de todos os endpoints e dos requisitos contratuais individualmente. A migração e os testes não constituem homologação produtiva.

## Restrições operacionais e sincronização

- Proibido aplicar migrações em `frcaixinha_aistudio_dev` no Termux sem autorização específica; último diagnóstico do operador: PostgreSQL 18.6, porta 5433, zero tabelas, papéis técnicos sem privilégios de superusuário e `frc_ai_owner` superuser apenas administrativo.
- Proibido merge na `main`, criação de usuários reais, ativação de Pix/MP/pagamentos, instalação de APK ou publicação em produção.
- Após verificar os cinco jobs verdes no **último commit**, sincronizar somente GitHub→Termux, com HEAD local e remoto exatos, árvore limpa, `git merge --ff-only`, seguido exclusivamente de `bash backend/scripts/aistudio_db_local.sh check`.
- Não atualizar automaticamente a classificação histórica das 147 cláusulas ou das 37 tarefas; verificar cada controle com evidência específica.
