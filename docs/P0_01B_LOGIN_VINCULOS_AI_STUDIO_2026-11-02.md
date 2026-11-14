# Projeto AI Studio — P0-01b: autenticação por sessão e isolamento de vínculos

**Data:** 02/11/2026 (America/Belem). **Repositório exclusivo:** `fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP`. Branch `atualizacao-ai-studio-9b46a63187`; PR #2 em rascunho, `main` preservada.

## Objetivo e resultado em código

Eliminar o caminho de consulta de vínculos por UUID arbitrário no serviço de autenticação de **homologação** do AI Studio, mantendo um único login com múltiplos papéis e tenants.

1. **Migração 021:** elimina a assinatura `auth_active_memberships(uuid)` criada na 006, substituindo-a por `auth_active_memberships(text)`, com validação de token bruto por SHA-256 via `pgcrypto`; tokens expirados, revogados, usuários suspensos e sessões com contexto inválido não retornam vínculos. Permissão `EXECUTE` apenas ao papel `frcaixinha_auth_role`.
2. **Login em duas fases, numa transação:** após validar a senha com Argon2id/bcrypt, insere sessão temporária `PENDING_CONTEXT` com TTL de 90 segundos; consulta os vínculos usando somente o token recém-gerado; promove a sessão para o papel autorizado (MASTER ou vínculo ativo), ou reverte toda a transação se a identidade não tiver papel permitido. Nenhum token provisório sai para o cliente. Não cria sessão de conta sem vínculo.
3. **Proteção do token provisório:** o papel `PENDING_CONTEXT` não é aceito por `get_current_session`, rotas Master, administrador, membro ou pela função de nomes de contextos da migração 020.
4. **Sessão e troca de contexto:** `get_current_session` e `switch_context` passam o token bruto validado no backend, não UUID de usuário, ao novo lookup. Preservam revalidação de papel, tenant ativo, expiração, revogação e transação.
5. **Readiness e guardas:** `/api/health/ready`, script de migração futura AI Studio, controle de funções e PostgreSQL 16/18 CI passam a conferir a nova assinatura. Sequência versionada: **001–021**.
6. **Testes negativos:** consulta por UUID/valor aleatório e hash armazenado não retorna vínculos; sessão ativa retorna somente vínculos próprios; sessão temporária não autoriza API; sessão temporária expirada deixa de fornecer vínculos; testes anteriores de login real sintético, usuário sem vínculo, switch-context, logout e RLS são regressões obrigatórias.

## Limites desta mitigação

- A regra reduz a superfície de enumeração por uma chamada SQL arbitrária por UUID, mas **não** substitui a proteção e segregação das credenciais do serviço Auth. Um atacante que controle a credencial técnica de autenticação com permissão para criar sessões pode forjar uma sessão válida. Remediar esse risco requer serviço emissor de sessão com privilégios ainda mais restritos, hardening independente e revisão operacional; não declarar resistência a comprometimento integral do serviço.
- `auth_active_membership_contexts(text)` permanece a função de nomes da migração 020; `auth_active_memberships(text)` é a função de papéis da migração 021.
- Proteção de força bruta compartilhada, prova de e-mail, recuperação de senha, infraestrutura TLS/produção, financeiro real, homologação Android física e testes AT-01–AT-50 completos **continuam pendentes**.
- A matriz histórica de 147 cláusulas e o backlog de 37 tarefas não são automaticamente reclassificados por este pacote.
- Nenhuma decisão financeira, percentual, calendário ou política de outro projeto é importada.

## Evidências do GitHub Actions

Executar e confirmar os cinco jobs **no último commit da PR**, nunca inferir sucesso apenas pela criação dos arquivos:
- `API sem banco configurado`: importação FastAPI e testes de segurança.
- `Migrações e testes de RLS em PostgreSQL descartável`: PG16 e testes de login/contexto, com dados sintéticos.
- `PostgreSQL 18 preflight`: transação única 001–021 e privilégios.
- `Frontend e regras locais`: TypeScript/React e regras de navegação.
- `Compilar APK debug`: compilação, sem instalação física.

O commit intermediário `d770f268` teve **FAIL** na importação Python por erro de parêntese em `auth.py`. A correção específica foi publicada em `db9425aed54120e0ca6841f442d1b75e0e521b99`. O relatório final deverá considerar a CI deste último commit ou de commit posterior que o contenha.

## Restrições de execução

- **PROIBIDO aplicar as migrações 001–021 no banco local do Termux nesta rodada.** Banco AI Studio: `frcaixinha_aistudio_dev`, PostgreSQL 18.6, porta 5433, zero tabelas no último diagnóstico do operador. A ferramenta `aistudio_db_local.sh check` é somente leitura.
- Sem bootstrap Master humano, novas contas reais, convites, pagamentos, MP/SMTP, Pix, empréstimos, bolões/rifas reais, APK instalado ou merge na `main`.
- Próxima sincronização GitHub→Termux só depois de validar a CI do commit final e comparar hashes exatos; usar `git fetch` e `git merge --ff-only` com árvore local limpa.

## Sequência seguinte do P0

Auditar a cadeia de `INSERT/UPDATE` de sessões pelo papel Auth e reduzir privilégios de emissão; cobrir concorrência de login/logout/suspensão e revisar expiração absoluta, inatividade e auditoria. Em paralelo, mapear endpoints de MASTER/ADMIN/MEMBER com operações de leitura e escrita negadas em três tenants.
