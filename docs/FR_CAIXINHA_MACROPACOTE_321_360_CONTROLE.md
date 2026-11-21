# FR Caixinha — Macropacote 321–360 (AI Studio Mobile)

Data: 04/11/2026. Baseline: `ee29c140f8755238de05039e4e70a6397d248082` (APK 213).
Homologação no celular do APK 213 informada pelo operador: **6/7 PASS**, 
**Anterior/Próxima PENDENTE**, `SHA runtime=NAO COMPROVADO`.
A PR #2 permanece Draft e `main` inalterada. Código e PostgreSQL desta frente não se misturam com FRcaixinha 2.2 independente.

## Escopo técnico

API adicional: `GET /api/v1/tenants/{tenant_id}/ledger/accounts/{account_id}/entries/keyset`.
Consultas limitadas, somente leitura, por chaves `(transaction_date, transaction_id, entry_id)`
e autorização repetida por sessão TENANT_ADMIN e RLS; página de 25 no aplicativo e máximo 50 na API.
O antigo extrato OFFSET permanece para compatibilidade. A UI passa a consultar a rota nova.
**Cursor não é credencial assinada, nem prova de snapshot, nem garantia de completude.**
Lançamentos retroativos podem afetar as páginas seguintes. Nenhum valor foi gravado no PostgreSQL 5433.

## Controle das 40 entregas e gates

| ID | Verificação | Estado |
|---|---|---|
| 321 | rota GET por cursor somente leitura | CÓDIGO / TESTE INCLUÍDO |
| 322 | validação do tenant no backend | CÓDIGO / TESTE INCLUÍDO |
| 323 | negativa para Master/Membro | CÓDIGO / TESTE INCLUÍDO |
| 324 | identificadores UUID válidos | CÓDIGO / TESTE INCLUÍDO |
| 325 | limite de 50 registros | CÓDIGO / TESTE INCLUÍDO |
| 326 | ordenacao estável por três chaves | CÓDIGO / TESTE INCLUÍDO |
| 327 | lookahead LIMIT +1 | CÓDIGO / TESTE INCLUÍDO |
| 328 | consulta sem OFFSET | CÓDIGO / TESTE INCLUÍDO |
| 329 | resposta sem saldos bancários | CÓDIGO / TESTE INCLUÍDO |
| 330 | nenhuma autorização de fechamento | CÓDIGO / TESTE INCLUÍDO |
| 331 | parser TS de schema exato | CÓDIGO / TESTE INCLUÍDO |
| 332 | rejeição de campos estranhos | CÓDIGO / TESTE INCLUÍDO |
| 333 | vínculo tenant/conta na resposta | CÓDIGO / TESTE INCLUÍDO |
| 334 | has_more exige página cheia | CÓDIGO / TESTE INCLUÍDO |
| 335 | centavos íntegros | CÓDIGO / TESTE INCLUÍDO |
| 336 | pilha de cursor para próxima | CÓDIGO / TESTE INCLUÍDO |
| 337 | retorno anterior e avanço novamente | CÓDIGO / TESTE INCLUÍDO |
| 338 | descarte após troca de sessão | CÓDIGO / TESTE INCLUÍDO |
| 339 | sem seeds na interface | CÓDIGO / TESTE INCLUÍDO |
| 340 | limite visual de 1000 páginas | CÓDIGO / TESTE INCLUÍDO |
| 341 | teste de 26 lançamentos sintéticos | CÓDIGO / TESTE INCLUÍDO |
| 342 | teste com zero e um lançamento | CÓDIGO / TESTE INCLUÍDO |
| 343 | conta inexistente 404 | CÓDIGO / TESTE INCLUÍDO |
| 344 | segregação dos papéis | CÓDIGO / TESTE INCLUÍDO |
| 345 | cursor inválido recusado | CÓDIGO / TESTE INCLUÍDO |
| 346 | entrada inválida recusa 422 | CÓDIGO / TESTE INCLUÍDO |
| 347 | linhas malformadas recusadas | CÓDIGO / TESTE INCLUÍDO |
| 348 | sem token HTTP 401 | CÓDIGO / TESTE INCLUÍDO |
| 349 | resposta no-store | CÓDIGO / TESTE INCLUÍDO |
| 350 | parser contra dados injetados | CÓDIGO / TESTE INCLUÍDO |
| 351 | contrato runtime M360 | CÓDIGO / TESTE INCLUÍDO |
| 352 | fingerprint fonte no import | CÓDIGO / TESTE INCLUÍDO |
| 353 | checkpoint Termux read-only | PREPARADO; TESTAR TERMUX |
| 354 | checkpoint M320 preservado | CÓDIGO / TESTE INCLUÍDO |
| 355 | zero migrations operacionais | CÓDIGO / TESTE INCLUÍDO |
| 356 | CI seis jobs no SHA final | CI NO SHA FINAL A CONFERIR |
| 357 | PR #2 Draft sem merge | PRESERVADO |
| 358 | zero escrita financeira no banco 5433 | PRESERVADO |
| 359 | teste físico paginação com 26+ registros | PENDENTE FÍSICO |
| 360 | SHA integral do processo em memória | NÃO COMPROVADO |

## Restrições contratuais preservadas

Não reclassificar as **46 pendências e 12 bloqueios** históricos do M300 nem as 147 cláusulas e AT-01–AT-50.
Persistem bloqueados: Pix real, desembolso, cobrança produtiva, fechamento, rateio, remuneração real,
migração operacional, criação de Master extra, rifa/bolão real, suporte excepcional, merge na main e upload para AI Studio.
Dados sintéticos somente em mocks/CI ou banco descartável com autorização específica; não criar contas/transações artificiais no PG 5433.
RLS, conciliação, backup off-device, recuperação RPO/RTO, auditoria imutável e LGPD continuam pendentes.

## Liberação sequencial

1. Exigir CI **6/6 PASS do SHA final**; resultado do commit anterior não substitui o atual.
2. Atualizar o Termux por `git fetch` e `git merge --ff-only` após conferir branch, histórico e estado local; sem reset/clean/push.
3. Reiniciar exclusivamente o FastAPI; PostgreSQL 5433 não pode ser reiniciado nem migrado neste pacote.
4. Rodar `bash backend/scripts/aistudio_360_checkpoint_readonly.sh SHA_COMPLETO` com a API local ativa.
5. Instalar APK assinado na versão anterior, mantendo armazenamento e package `com.frcaixinha.app.aistudio`.
6. Testar no celular acesso Admin, extrato com contas, múltiplas páginas quando houver dados suficientes,
voltar e avançar, Master/Membro negados, bloqueios financeiros e retorno do segundo plano.
7. Se não houver 26+ lançamentos no conjunto autorizado, **Anterior/Próxima continuam PENDENTES**.
8. As impressões digitais dos arquivos-fonte na importação não são a prova de SHA completo do processo.
