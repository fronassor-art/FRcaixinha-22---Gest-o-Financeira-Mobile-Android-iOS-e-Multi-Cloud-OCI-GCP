# FR Caixinha — Macropacote 320 | Diretório de contas sem saldos, controles e homologação

**Data da preparação:** 04/11/2026. **Frente técnica:** AI Studio Mobile. **Produto:** FR Caixinha, com **Documento Mestre e Contrato Técnico Mestre compartilhados** com a frente original, mas sem qualquer compartilhamento de código, banco, segredos, backups ou deploy. Esta etapa não edita o projeto no Google AI Studio.

## 1. Baseline de autorização

- Base inicial: commit `e33bae79fa1b4b48eb9cd10c3ea4873be0c1a636`, Macropacote 300.
- CI #211: **6/6 PASS**. Termux M300: sincronização e FastAPI runtime **PASS informados pelo operador**, PostgreSQL AI Studio exclusivo `127.0.0.1:5433`.
- APK 211: **4/7 PASS, 3 pendentes, 0 FAIL** informados pelo operador. PASS: perfil Administrador, prévia contábil, Master/Membro sem acesso administrativo, fechamento e operações financeiras bloqueados. PENDENTE: botão/extrato por conta e navegação entre páginas, porque a prévia apresentou **zero transações**.
- A captura com `NO_TRANSACTIONS` **não prova ausência de contas**, somente ausência de transações na amostra de prévia autorizada; por isso não gerar lançamentos falsos no PostgreSQL para criar telas.
- A PR #2 permanece **Draft**, `main` não recebe merge. Revisão, Termux e Android após aprovação da CI.
- A matriz [147 cláusulas](MATRIZ_147_PENDENCIAS_AI_STUDIO_2026-11-01.md) permanece histórica, sem reclassificação inferida. O [backlog M300](FR_CAIXINHA_MACROPACOTE_300_CHECKLIST_CONSOLIDADO.md) preserva 46 pendências e 12 bloqueios; este pacote não os elimina.

## 2. Entregas de código agrupadas — verificar por evidência

| Grupo | Código e teste | Objetivo | Situação antes da CI |
|---|---|---|---|
| 320-A | `backend/app/routers/ledger.py`, `backend/app/models.py` | Novo GET de diretório `/api/v1/tenants/{tenant_id}/ledger/accounts/directory`, somente código/nome/tipo e ID, sem valor de saldo | PREPARADO |
| 320-B | Limite 500 + `LIMIT 501`, `WHERE tenant_id=$1`, ordenação por código e ID | Recusar diretórios grandes em vez de truncar silenciosamente, acesso do admin ao tenant próprio | PREPARADO |
| 320-C | Validador backend fail-closed | Recusar identidades trocadas, contas duplicadas e dados inválidos, sem gravação | PREPARADO |
| 320-D | `src/services/ledgerAccountDirectoryBoundary.ts` | Parser rigoroso com esquema exato, tenant vinculante, sem valores financeiros, rejeita campos extras | PREPARADO |
| 320-E | `financialApiService.ts` | Cliente GET autenticado com guarda de TENANT_ADMIN | PREPARADO |
| 320-F | `src/services/ledgerVisibilityPolicy.ts` | Separar `BALANCED`, `NO_TRANSACTIONS` e `REVIEW_REQUIRED` sem afirmar fechamento | PREPARADO |
| 320-G | `src/components/LedgerView.tsx` | Em `NO_TRANSACTIONS`, exibir apenas contas existentes sem saldo. Se zero contas, explicar ausência de diretório | PREPARADO |
| 320-H | `src/components/LedgerAccountEntries.tsx` | Aceitar metadata mínima; extrato vazio permite testar tela e paginação quando houver conta | PREPARADO |
| 320-I | `src/components/Navbar.tsx` | Cabeçalho do aplicativo `FR Caixinha` (antes `FRcaixinha`) | PREPARADO |
| 320-J | `backend/app/main.py` | Endpoint de contrato carregado `/api/health/features/m320` sem PII ou credenciais; conserva versão M300 | PREPARADO |
| 320-K | `backend/scripts/aistudio_320_checkpoint_readonly.sh` | Verifica Git/PG/ready via M300, contrato M320 e GET não autorizado HTTP 401; sem tocar DB | PREPARADO |
| 320-L | 3 conjuntos Pytest | Validar diretório 0, 1, 501 contas, SQL/role, HTTP e runtime sintéticos | PREPARADO |
| 320-M | 2 conjuntos TS | Campos proibidos, estado vazio, sessão obsoleta, transições de visibilidade | PREPARADO |
| 320-N | GitHub CI | Verificação obrigatória de frontend, API, PG18, RLS descartável, build Android e snapshot-fonte | PREPARADO |

**Importante:** somente CI 6/6 PASS no SHA final permite liberar a sincronização. Somente aparelho e Termux comprovam homologação física, não testes mockados.

## 3. Contrato de API — diretorio vazio

`GET /api/v1/tenants/{tenant_id}/ledger/accounts/directory` requer sessão real de `TENANT_ADMIN` daquele tenant. `MASTER`, `TENANT_MEMBER` ou outro tenant: HTTP 403. Sem token: HTTP 401. `RLS` no banco também permanece obrigatório.

A resposta tem `source=POSTGRESQL_RLS`, `scope=TENANT_ADMIN_READ_ONLY`, `tenant_id`, `accounts` (id, account_code, account_name, account_type), `balance_values_hidden=true`, `complete_ledger_verified=false`, `bank_reconciled=false`, `financial_closing_authorized=false`. Não há `balance_cents`, `balance_brl`, referência bancária, CPF, token ou informação de recebedor.

Se `NO_TRANSACTIONS` e `accounts=[]`, a tela não mostra botão fictício. Se há conta, permite abrir extrato da conta mesmo sem lançamentos; isso não transforma a prévia em razão completo nem prova valores.

Se a prévia está `REVIEW_REQUIRED`, não buscar diretório nem detalhes. Se `BALANCED`, segue o fluxo anterior com limite geral 500 contas/transações; esse gate não deve ser removido por conveniência. Não há novas tabelas, migrations, dados artificiais, contas ou lançamento.

## 4. Matriz de testes exigidos

- Testar GET no tenant certo e ausência de campos financeiros na resposta.
- Testar dados sintéticos de **zero contas**, **uma conta**, duplicidade, mais de 500 e identidades de outro tenant.
- Testar Master, Membro e Admin de outra caixinha = 403, antes de qualquer leitura (mocks) e com RLS efetivo nos testes existentes.
- Testar token ausente = 401 e `Cache-Control: no-store`.
- Testar `NO_TRANSACTIONS` dirige para diretório sem saldo, `BALANCED` para detalhamento limitado, `REVIEW_REQUIRED` para bloqueio.
- Testar parser frontend contra saldo injetado, `tenant_id` indevido, campos adicionais, UUID inválido, nomes malformados e duplicados.
- Testar que mudança de sessão descarta respostas antigas (guarda existente do AuthService).
- Compilar/assinar APK preservando identificador `com.frcaixinha.app.aistudio` e SHA do certificado; instalar **sem remover** versão anterior.
- Homologar no Android 212+ quando disponível: primeiro Admin, depois menu Livro-Razão, contas (se existentes), extrato vazio, sessão Master/Membro, bloqueio financeiro, restauração do app e navegação.
- Com `accounts=[]` no banco, **paginação visual permanece pendente**. Para exercitá-la sem risco, usar somente dados sintéticos em banco descartável e/ou ambiente dedicado de homologação sob aprovação — jamais inserir registros no cluster operacional 5433 apenas para mudar telas.

## 5. Restrições e próximas frentes (não encerradas)

Mantêm-se **PENDENTES**: 147 cláusulas/AT-01–AT-50 por comprovar, backup cifrado e chave `age` fora do celular, RPO/RTO, restore completo, RLS local autenticado dos três papéis técnicos, paginação global por cursor/snapshot, reconciliação de saldos e datas, auditoria imutável/provas, Pix/Mercado Pago (sandbox), onboarding/convites/licenças SaaS, contratos jurídicos, consentimento anual e autoempréstimo, Price e crédito interno/externo, LGPD e OCI/GCP operacional.

Mantêm-se **BLOQUEADAS**: Pix/cobranças/desembolsos reais, fechamento e rateio, alteração de Master, suporte excepcional sem consentimento, rifas/bolões reais, migração no banco operacional, merge na main e envio para AI Studio sem solicitação.

## 6. Ordem operacional após CI

1. Conferir PR #2 Draft e CI 6/6 PASS.
2. Termux: fast-forward guardado no SHA informado e worktree limpa; não usar `git reset --hard`, `git clean` ou `git push`.
3. Por alteração Python, **Ctrl+C apenas no FastAPI** e reinício por `bash backend/scripts/run_termux_fastapi.sh`. Não reiniciar PostgreSQL 5433.
4. Segunda sessão: `bash backend/scripts/aistudio_320_checkpoint_readonly.sh SHA_COMPLETO`; exigir contrato e acesso sem token negado.
5. Instalar APK gerado sobre o anterior, testar papéis e contas sem transações. Marcar PASS somente testes realmente observados no celular. Preservar as pendências se faltar dado no ambiente.
