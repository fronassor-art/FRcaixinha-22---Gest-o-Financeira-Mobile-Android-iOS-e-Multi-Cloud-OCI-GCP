# FR Finance M39102 — Inventário discriminado das 129 pistas genéricas de evidência

**Estado:** documento de diagnóstico, não checklist de defeitos do aplicativo. **NENHUM dos 129 registros representa um arquivo ausente.** Todas as 129 referências são diretórios genéricos (`backend/tests/`, `src/tests/`, `backend/migrations/`) usados como placeholders quando não existe um teste ou migração individual legitimamente vinculado ao requisito.

**Confronto com HEAD da auditoria:** 714 pistas de arquivos/diretórios provenientes do checklist CP20261114: **585 arquivos exatos existentes** + **129 pistas genéricas** + **0 caminhos de arquivo individual inexistentes**. Existência de um arquivo não atesta cumprimento do requisito e não habilita produção.

## Distribuição

- 29 referências genéricas ligadas a cláusulas históricas (esquema/migrações e requisitos 16.x); elas exigem vincular o SQL/teste específico e decidir aplicabilidade.
- 100 referências genéricas correspondentes aos 50 cenários AT-01…AT-50 (um diretório de testes backend e um frontend por AT). Ainda é necessário recuperar o roteiro detalhado do AT, mapear testes efetivos por cenário e obter evidência E2E independente.

## Regra de resolução

- Para cada referência, substituir a pasta genérica por **arquivo de teste/migração preciso** somente quando houver vínculo de escopo demonstrado, cenário e resultado reprodutível. Não editar o checklist congelado silenciosamente: criar nova revisão com prova e decisão.
- Documentar contrato, aplicabilidade, risco, responsáveis e resultado; nunca marcar como produção homologada por apontar um arquivo de CI.

## Referências genéricas individualizadas

| ID checkpoint | Requisito | Fonte genérica | Natureza |
|---|---|---|---|
| `CP26-0205` | `HIST-12.1` | `backend/migrations/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0206` | `HIST-12.2` | `backend/migrations/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0207` | `HIST-12.2-B` | `backend/migrations/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0208` | `HIST-12.2-A` | `backend/migrations/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0209` | `HIST-12.3` | `backend/migrations/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0210` | `HIST-12.4` | `backend/migrations/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0211` | `HIST-12.5` | `backend/migrations/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0243` | `HIST-16.1` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0243` | `HIST-16.1` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0244` | `HIST-16.2` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0244` | `HIST-16.2` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0245` | `HIST-16.2-A` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0245` | `HIST-16.2-A` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0246` | `HIST-16.3` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0246` | `HIST-16.3` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0247` | `HIST-16.3-A` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0247` | `HIST-16.3-A` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0248` | `HIST-16.4` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0248` | `HIST-16.4` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0249` | `HIST-16.4-A` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0249` | `HIST-16.4-A` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0250` | `HIST-16.4-C` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0250` | `HIST-16.4-C` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0251` | `HIST-16.4-E` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0251` | `HIST-16.4-E` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0252` | `HIST-16.4-D` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0252` | `HIST-16.4-D` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0253` | `HIST-16.5` | `backend/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0253` | `HIST-16.5` | `src/tests/` | Cláusula histórica — teste ou migração específica não identificada |
| `CP26-0281` | `AT-01` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0281` | `AT-01` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0282` | `AT-02` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0282` | `AT-02` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0283` | `AT-03` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0283` | `AT-03` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0284` | `AT-04` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0284` | `AT-04` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0285` | `AT-05` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0285` | `AT-05` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0286` | `AT-06` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0286` | `AT-06` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0287` | `AT-07` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0287` | `AT-07` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0288` | `AT-08` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0288` | `AT-08` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0289` | `AT-09` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0289` | `AT-09` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0290` | `AT-10` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0290` | `AT-10` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0291` | `AT-11` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0291` | `AT-11` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0292` | `AT-12` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0292` | `AT-12` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0293` | `AT-13` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0293` | `AT-13` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0294` | `AT-14` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0294` | `AT-14` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0295` | `AT-15` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0295` | `AT-15` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0296` | `AT-16` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0296` | `AT-16` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0297` | `AT-17` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0297` | `AT-17` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0298` | `AT-18` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0298` | `AT-18` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0299` | `AT-19` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0299` | `AT-19` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0300` | `AT-20` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0300` | `AT-20` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0301` | `AT-21` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0301` | `AT-21` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0302` | `AT-22` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0302` | `AT-22` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0303` | `AT-23` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0303` | `AT-23` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0304` | `AT-24` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0304` | `AT-24` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0305` | `AT-25` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0305` | `AT-25` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0306` | `AT-26` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0306` | `AT-26` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0307` | `AT-27` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0307` | `AT-27` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0308` | `AT-28` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0308` | `AT-28` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0309` | `AT-29` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0309` | `AT-29` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0310` | `AT-30` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0310` | `AT-30` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0311` | `AT-31` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0311` | `AT-31` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0312` | `AT-32` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0312` | `AT-32` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0313` | `AT-33` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0313` | `AT-33` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0314` | `AT-34` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0314` | `AT-34` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0315` | `AT-35` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0315` | `AT-35` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0316` | `AT-36` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0316` | `AT-36` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0317` | `AT-37` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0317` | `AT-37` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0318` | `AT-38` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0318` | `AT-38` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0319` | `AT-39` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0319` | `AT-39` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0320` | `AT-40` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0320` | `AT-40` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0321` | `AT-41` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0321` | `AT-41` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0322` | `AT-42` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0322` | `AT-42` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0323` | `AT-43` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0323` | `AT-43` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0324` | `AT-44` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0324` | `AT-44` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0325` | `AT-45` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0325` | `AT-45` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0326` | `AT-46` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0326` | `AT-46` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0327` | `AT-47` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0327` | `AT-47` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0328` | `AT-48` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0328` | `AT-48` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0329` | `AT-49` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0329` | `AT-49` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0330` | `AT-50` | `backend/tests/` | AT — roteiro/testes E2E individualizados pendentes |
| `CP26-0330` | `AT-50` | `src/tests/` | AT — roteiro/testes E2E individualizados pendentes |

**Release:** `PRODUCTION_NOT_AUTHORIZED`; a inclusão deste relatório não executou teste financeiro, migracão local, reinício de API, operação OCI ou comunicação real.
