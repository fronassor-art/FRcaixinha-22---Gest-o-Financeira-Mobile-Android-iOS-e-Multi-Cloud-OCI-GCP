# FR Finance M41090 — asyncpg pool reuse/reset proof (NO-GO)

## Escopo e rastreabilidade

M41090 amplia a prova descartável M41080 para o ciclo de vida de uma conexão
asyncpg reutilizada por um pool de tamanho um. O ensaio usa o mesmo banco
PostgreSQL 18 sintético e efêmero dos workflows M41050/M41060, o login
`m40650_ci_login`, a role de aplicação `m40650_app` e identidades/dados
fictícios criados pelo fixture. Não usa sessão de pessoa real.

Requisitos relacionados: CP26-0061 / CTM-07 (identidade, papel e tenant) e
CP26-0062 / CTM-08 (RLS e credenciais). Seus 330 IDs e 2.310 etapas permanecem
inalterados. A matriz exige evidência independente e aceite aplicável; este
resultado de CI não altera `production_verified` nem fecha os requisitos.

## Prova automatizada

O runner valida os marcadores de CI, as flags OFF e o DSN fixo da instância
descartável antes de criar o pool. Com uma única conexão física, a prova:

1. estabelece contexto válido dentro de transação e confirma a leitura limitada
   ao membro sintético;
2. após commit, verifica na mesma conexão e após nova aquisição que o backend
   físico é o mesmo, `current_user` voltou ao login, os GUCs e a capability não
   persistem e `current_claims()`/RLS não expõem linhas;
3. repete o ciclo com rollback explícito e testa o estado antes e depois da
   readquisição da conexão.

Os caminhos de commit e rollback são testados no PostgreSQL 18 descartável por
M41050/M41060; os guards offline verificam os limites do runner e do workflow.
Nenhum teste substitui revisão adversarial independente ou prova de runtime.

## Limites e resultado

- API/rota de produção integrada: nenhuma.
- Schema/migrações, permissões, credenciais ou SQL de produção alterados: nenhum.
- Banco autoritativo `127.0.0.1:5433/frcaixinha_aistudio_dev`: não acessado.
- Processo FastAPI/PG: sem reload ou reinício.
- OCI/staging, credenciais reais, provedor PSP e aparelho físico: não atestados.
- M40570 (GUC falsificável), M40710/M40730 (captura/emissor SQL), M40928/M40929
  (identidade e custódia de credenciais) permanecem pendentes.
- PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF.
- PRODUCTION=BLOCKED; Issue #5 permanece NO-GO.

Status após CI: apenas prova de isolamento/reutilização em fixture sintético;
CP26-0061/0062 continuam PENDING_INDEPENDENT_EVIDENCE.

## Marcadores de checkpoint

CHECKS_DEFINED=COMMIT_RESET,ROLLBACK_RESET,POOL_REACQUIRE,SAME_BACKEND.
ORIGINAL_DATABASE=NOT_ACCESSED; MIGRATIONS=NONE.
