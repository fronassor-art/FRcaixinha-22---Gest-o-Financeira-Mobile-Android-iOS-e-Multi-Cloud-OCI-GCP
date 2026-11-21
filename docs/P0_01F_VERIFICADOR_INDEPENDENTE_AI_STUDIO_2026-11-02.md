# Projeto AI Studio — P0-01f: verificação independente antes da emissão de sessão

**Data:** 02/11/2026 (America/Belem). **Repositório exclusivo AI Studio:** `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`. Branch `atualizacao-ai-studio-9b46a63187`, PR #2 DRAFT. Nenhum vínculo técnico, jurídico ou de dados com o outro projeto independente de nome parecido.

## Mudança técnica em homologação

A migração **025**, `backend/migrations/025_verifier_bound_session_issuance.sql`, cria `frcaixinha_verifier_role` (NOLOGIN/NOSUPERUSER/NOBYPASSRLS) e uma tabela de comprovações `auth_login_proofs`, com apenas hashes SHA-256, validade curta, consumo único e RLS forçado.

**Contas separadas:**
- **Verificador:** pode consultar colunas mínimas de `users` e `credentials.password_hash` e inserir comprovação curta em `auth_login_proofs`. Não pode inserir nem consultar tokens de sessões e não pode executar a função de emissão.
- **Autenticação/sessões:** mantém leitura mínima da identidade e execução de funções de sessões, **não lê** `credentials.password_hash`, **não insere** diretamente em `sessions`, nem lê a tabela de comprovações. Somente `auth_issue_pending_session(uuid,text,text)` (SECURITY DEFINER, com verificação de proof bruto por digest, identidade ACTIVE, expiração e lock) pode emitir a sessão provisória ao consumir a prova.
- **Aplicação financeira:** permanece sem leitura de hashes, provas e sessões.

A API FastAPI de **homologação apenas** exige `AUTH_DATABASE_URL` e `AUTH_VERIFIER_DATABASE_URL`, com nomes de usuários PostgreSQL distintos e mesmo alvo (host/porta/database). O password hash é verificado em Python Argon2id/bcrypt antes da criação de uma prova de 60 segundos; a conta Auth só recebe o valor bruto dessa prova em memória após verificação bem-sucedida. Em seguida, em sua própria transação, emite o token `PENDING_CONTEXT`, consulta vínculos e promove o contexto; se o vínculo não for válido, a sessão não é persistida.

### Ameaças mitigadas e não mitigadas

**Mitigado sob hipótese de uma única credencial técnica vazada:** quem controlar somente o usuário SQL Auth não poderá ler hashes de senha ou criar sessão sem prova de uso único do verificador. Quem controlar somente o verificador não poderá emitir a sessão pela função de emissão nem acessar a tabela de sessões. A conclusão depende de comprovação em CI das concessões efetivas e da segregação de credenciais.

**Não mitigado:** comprometimento completo do backend, das duas credenciais SQL ou do mecanismo Python de verificação; backend malicioso ainda pode gerar provas para qualquer identidade. A comprovação de senha é realizada pela camada FastAPI, não por um processo independente de confiança. O sistema não oferece garantia contra um servidor de aplicação comprometido. Rate limit de login permanece por processo e há riscos de observabilidade/logging, recuperação de senha, e-mail e transporte/TLS ainda a resolver. **Proibido declarar aptidão produtiva.**

## Provas mínimas exigidas em CI

1. PostgreSQL 16: duas conexões independentes (credenciais sintéticas, nomes PostgreSQL diferentes), ausência de leitura de hashes pela conta Auth, ausência de acesso de sessão da conta verificadora e bloqueio de INSERT direto em sessão pela Auth.
2. Prova válida pode ser consumida uma única vez. Reuso, prova aleatória, prova expirada e token/usuário incompatíveis são negados; vínculo de tenant inválido não é promovido.
3. Login FastAPI com senha sintética, login sem vínculo, troca de contexto, inventário de sessões, logout, revogação e concorrência preservados.
4. PostgreSQL 18: a sequência versionada **001–025** completa em uma transação, permissões e RLS da prova aprovados.
5. Frontend, API sem banco e compilação do APK debug continuam gates obrigatórios.

Apenas cinco jobs **SUCCESS** no HEAD final da branch permitem sincronizar o clone local do Termux.

## Restrições

- O banco **AI Studio** do aparelho continua **sem migrações autorizadas**: `frcaixinha_aistudio_dev`, PostgreSQL 18.6, porta 5433, **zero tabelas**, última leitura do operador no commit `3ee570d`. Nem a migração 025 nem as anteriores devem ser aplicadas sem autorização expressa.
- Sem novos usuários reais, sem credenciais adicionais locais, sem bootstrap Master real, sem Pix/cobrança, sem instalar APK e sem merge na `main`.
- O script `aistudio_db_local.sh` lista a migração 025 somente para uso futuro, após planejamento e aprovação de provisionamento do verificador no banco isolado.
- A matriz histórica de 147 cláusulas e o backlog de 37 tarefas só devem mudar após auditoria requisito a requisito.

**Próximo P0:** auditar isolamento efetivo de papéis por instância, separar segredos/credential rotation e verificar race conditions de consumo de prova e a validade de credenciais após mudança de senha.
