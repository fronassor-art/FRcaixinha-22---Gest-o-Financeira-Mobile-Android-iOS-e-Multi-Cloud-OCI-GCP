# FR Finance M39940 — Pré-validação documental dos três caixas

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`; PR #2 Draft.
**Checkpoint local recebido:** Termux M39930 sincronizado em `4c47109`,
sem migração, acesso ao PostgreSQL original, reinício do FastAPI ou
ativação financeira. **Este pacote fica inicialmente apenas no GitHub.**

## Razão do novo controle

M39920 validou a forma das partidas dobradas e M39930 testou
a estrutura imutável/RLS num PostgreSQL descartável. Ambos deixam uma
lacuna intencional: a existência de uma conta, referência ou registro de
evento **não comprova que o dinheiro foi recebido, que a despesa
ocorreu ou que uma remuneração é devida**. A lacuna passa a ser
documentada e verificada separadamente no M39940.

`backend/app/exclusive_cashbox_evidence_preflight.py` realiza uma
checagem **puramente estrutural** entre o diário candidato e um
rascunho documental. O rascunho é tratado integralmente como entrada
não confiável, sem conexão com provedor, banco, identidade real ou API.

## Origem documental compatível por evento

| Domínio | Evento | Documento exigido para prévia |
| --- | --- | --- |
| PLATFORM_MASTER | SAAS_SETTLEMENT | PROVIDER_SETTLEMENT |
| PLATFORM_MASTER | PLATFORM_OPERATING_EXPENSE | FISCAL_EXPENSE |
| TENANT_ADMIN_OWN | ADMIN_CLOSING_REMUNERATION | ANNUAL_CLOSING |
| TENANT_ADMIN_OWN | ADMIN_OWN_EXPENSE | FISCAL_EXPENSE |
| TENANT_COLLECTIVE | MEMBER_CONTRIBUTION | PROVIDER_SETTLEMENT |
| TENANT_COLLECTIVE | TENANT_LOAN_REPAYMENT | PROVIDER_SETTLEMENT |
| TENANT_COLLECTIVE | TENANT_OPERATING_EXPENSE | FISCAL_EXPENSE |

## Invariantes de pré-validação

1. Documento e diário precisam ter **mesmo tenant, escopo,
   tipo de evento, referência e fingerprint**; o preflight contábil
   M39920 é **recalculado** para rejeitar diários fabricados,
   desbalanceados ou marcados como pagos.
2. Valor documental proposto em centavos inteiros positivos deve
   coincidir com o total a débito; nunca se aceita float, booleano,
   valor ausente, zero, negativo ou excesso.
3. Hash documental SHA-256 é apenas um formato de referência.
   O teste **não autentica a origem ou existência dos bytes**.
4. Para recebimentos são exigidos formato do identificador do
   pagamento e recebedor do provedor e horário com timezone;
   nenhuma dessas informações constitui consulta autenticada,
   confirmação de liquidação ou conciliação.
5. Para despesas é exigida referência fiscal com formato válido,
   sem herdar campos de pagamento/fechamento; ainda não há
   validação de NF-e ou aprovação de despesa.
6. Para remuneração do administrador, só cabe o domínio
   `TENANT_ADMIN_OWN`, com ciclo e política apontados por UUID,
   ano declarado e comparação numérica **ilustrativa** do total
   informado com 15% para administrador e 85% para membros, com
   arredondamento exato em centavos. São conferidos dois valores:
   remuneração proposta e pool proposto aos membros, exigindo
   soma igual ao lucro informado. **Não lê a política, não calcula
   resultado real, não reconhece obrigação, não libera retirada.**
7. IDs propostos de preparador e revisor devem ser distintos,
   mas **não demonstram identidade, vínculo, consentimento,
   revisão independente executada ou dupla autorização**.
8. Os retornos **sempre** permanecem em
   `DOCUMENTARY_CANDIDATE_NOT_AUTHENTICATED`,
   `document_authenticated=false`, `amount_reconciled=false`,
   `actor_authorized=false`, `independent_review_verified=false`,
   `original_db_posted=false`, `payout_authorized=false`.
   Pendências de autenticidade, titularidade, dupla revisão,
   idempotência persistida, competência/contabilidade e liberação
   de pagamento permanecem explícitas.

## Próxima evolução necessária

Construir, **somente em PostgreSQL descartável/staging homologado**,
um catálogo append-only de evidências e vínculos com lançamentos
candidatos, versão de política e ciclo, impossibilidade de replay,
FK composta por domínio/tenant, RLS controlado pela sessão autenticada,
estorno auditado, reconciliação independente do Mercado Pago e provas de
despesa/fechamento. A posterior aplicação no PostgreSQL FR Finance
original porta 5433 depende de aprovação separada após backup,
auditoria, CI e verificação jurídica.

Não disponibilizar interface de saldo, comissão a receber, saque,
receita liquidada ou movimentação real com base neste pacote.
Não acessar o PostgreSQL do FR Caixinha 2.2.

## Artefatos e checkpoints

- Biblioteca: `backend/app/exclusive_cashbox_evidence_preflight.py`.
- Testes: `backend/tests/test_m39940_cashbox_evidence_preflight_ci.py`.
- Workflow: `.github/workflows/frfinance-m39940-evidence-preflight-ci.yml`.
- Base documental selada M39100: **não alterar hashes nem contagens**.
- `M39940_MIGRATIONS=NONE`; `M39940_TERMUX_ACCESS=NONE`;
  `M39940_FASTAPI_RESTART=NONE`; `PIX_REAL=OFF`;
  `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`;
  `PRODUCTION=BLOCKED`.
