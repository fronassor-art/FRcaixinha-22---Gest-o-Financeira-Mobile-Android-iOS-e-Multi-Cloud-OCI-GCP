# FR Finance M40240 — diagnóstico real de catálogo RLS, somente leitura

## Contexto

No Termux original, M40230 foi sincronizado no commit `28b16e9` e devolveu `PASS_SOURCE_BOUNDARIES_ONLY_NOT_RUNTIME_RLS`. A CI M40230 aprovou 135 testes de RLS e RBAC sintéticos. M40220 já havia confirmado 12 HTTP 401 anônimos. Nenhuma dessas provas atesta a instalação efetiva de políticas RLS no PostgreSQL original.

## Objetivo do M40240

Conectar *somente* ao cluster FR Finance PostgreSQL 18, `127.0.0.1:5433`, database `frcaixinha_aistudio_dev`, role `frc_ai_owner`, sem ler nenhuma linha de usuário/membro/sessão, sem escrever dados e sem reiniciar serviços.

O comando utiliza `env -i` (não herda PGPASSWORD nem URLs), senha digitada interativamente e escondida pelo psql `-W`; cliente `-X` sem configuração pessoal; `PGOPTIONS` impõe modo padrão read-only. A transação SQL inicia com `BEGIN READ ONLY` e termina em `ROLLBACK`. `ON_ERROR_STOP` e guardas SQL por divisão-zero interrompem no primeiro invariante falso.

Os quatro guardas de catálogo verificam:
1. Servidor PG18, diretório PGDATA original, endereço/porta, role/DB e modo read-only.
2. Três papéis técnicos `frc_ai_app`, `frc_ai_auth`, `frc_ai_verifier` existem, LOGIN, não superuser e não BYPASSRLS.
3. Seis tabelas de Crédito Especial/Extraordinário existentes com `relrowsecurity` e `relforcerowsecurity`.
4. Dezesseis políticas RLS nomeadas da migração 110 estão presentes nas tabelas corretas.

**Limite crucial:** a consulta com `frc_ai_owner` verifica o catálogo, não demonstra a eficácia das políticas para as sessões de usuário `frc_ai_app`. O proprietário pode ter privilégios especiais e os predicados não são executados neste preflight. Nenhuma aprovação de crédito, RLS real entre tenants, entrega externa ou produção pode ser inferida. M40240 não lê CPF, saldos, senhas, tokens, linhas de negócio ou `api.env`.

## Operação

Executar no **Termux nativo**, e não no Debian, após sincronizar a branch AI Studio:

`bash backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sh`

Se surgir `M40240_STATUS=BLOCKED_LIVE_RLS_CATALOG_OR_CONNECTION`, não aplicar migrações, não alterar roles, não rodar `pg_resetwal` e não reiniciar PostgreSQL para forçar PASS. Inspecionar somente a categoria de falha sem compartilhar senha.

## Metadados de homologação

Nenhum novo SQL de migração. Nenhuma alteração em `backend/app/main.py` ou routers. A CI audita apenas forma de SQL, sintaxe shell e regressões sintéticas: não acessa o celular.

`PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.


## Adendo M40310 após a aprovação real do M40240

O operador confirmou em 17/11/2026 o M40240 PASS no cluster original: identidade PostgreSQL 18/5433, três papéis técnicos, seis tabelas com FORCE RLS, dezesseis políticas e ROLLBACK READ ONLY.

O M40310 amplia o **mesmo SQL e o mesmo launcher** M40240, sem scripts de migração nem ambiente adicional. Confere os comandos, papéis destino e contexto de sessão das 16 políticas (inclusive ausência de política inesperada), os cinco triggers SQL111 habilitados e os privilégios mínimos de frc_ai_app. Se falhar, diagnosticar a divergência; nunca corrigir automaticamente ou reexecutar migrações.

Esse resultado continua **somente de catálogo**, não é teste de RLS efetivo com usuários autenticados ou leitura de dados pessoais. Mesmo um PASS não autoriza produção, canais reais, PIX ou criação da VM OCI. A rotina solicita a senha preexistente de frc_ai_owner, sem armazená-la.
