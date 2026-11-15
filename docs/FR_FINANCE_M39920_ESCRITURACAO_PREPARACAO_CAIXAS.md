# FR Finance M39920 — Escrituração preparatória dos três caixas

**Data:** 15/11/2026. **Branch:** `atualizacao-ai-studio-9b46a63187`; PR #2 permanece em rascunho.

## Resultado desta etapa

Há agora um **núcleo de pré-validação de candidatos a lançamentos contábeis**, estritamente puro (sem rede, banco, provedor, usuário ou pagamento):

- `backend/app/exclusive_cashbox_journal_preflight.py` valida o domínio do evento, o escopo `PLATFORM_MASTER`, `TENANT_ADMIN_OWN` ou `TENANT_COLLECTIVE`, a chave do tenant, a conta contábil pertencente ao domínio, os dois lados de lançamento (DR/CR), centavos inteiros positivos e conservação exata DR=CR.
- Não é possível aceitar contas `PM_` no diário de uma caixinha, contas `TA_` no Master ou misturar linhas entre tenants, mesmo que o total fique numericamente equilibrado.
- Um `fingerprint` SHA-256 determinístico identifica o **mesmo candidato** com linhas reordenadas. **Não prova** idempotência persistida, autenticidade de evidência ou reconciliação: tais obrigações dependem de controles de banco e do provedor.
- A resposta é sempre `STRUCTURAL_PREVIEW_NO_POSTING`, com `evidence_attested=false`, `policy_attested=false`, `provider_reconciled=false`, `journal_posted=false`, `payment_enabled=false` e `withdrawal_enabled=false`.
- `backend/tests/test_m39920_exclusive_cashbox_journal_preflight_ci.py` prova sete famílias de eventos, recusa de valores zero/negativos/booleanos/fração, paridade contábil, referência inválida, duplicações, mistura de conta e tenant e ausência de funções de I/O.

## Modelo SQL somente descartável, não migração

`backend/tests/sql/m39920_three_cashbox_journal_disposable_ci.sql` cria **tabelas TEMP** somente dentro de uma transação de CI em `frcaixinha_ci` com sessão PostgreSQL 18 / 5432 / usuário `postgres` e prova adicional por `frfinance.m39920_ci=DISPOSABLE_ONLY` + argumento `CI_M39920_DISPOSABLE`.

Verificações: chave de tesouraria por domínio, eventos admitidos por escopo, prefixo de conta, valor positivo, lançamento de contrapartida, bloqueio de `posting_authorized=true`, `provider_reconciled=true`, saldo positivo e replay de mesma referência. Os cenários rejeitados usam transações aninhadas de teste. Todos os dados sintéticos são descartados por `ROLLBACK`.

**Não criar migração 114 nem aplicar SQL no Termux nesta etapa.** O esquema é uma hipótese de implementação isolada. Não existe ainda trigger diferida de balanceamento, imutabilidade, RLS com papéis reais, trilha de autorização ou política de competência prontas para produção. Esses requisitos são bloqueadores de qualquer persistência no banco original.

Workflow: `.github/workflows/frfinance-m39920-cashbox-journal-disposable-ci.yml`.
Jobs: biblioteca pura Python e PostgreSQL 18 descartável. Nenhum serviço local é acessado.

## Compromissos contratuais e financeiros

- **Master**: apenas receitas/despesas da própria plataforma. Uma intenção SaaS `APPROVED` não se transforma em receita paga sem comprovação do provedor; a plataforma não é banco dos membros.
- **Admin titular**: o domínio de remuneração própria não equivale ao caixa coletivo e não pode reconhecer 15% automaticamente sem lucro líquido elegível, política versionada, fechamento anual auditado e conciliação.
- **Coletivo**: cada tenant mantém sua propriedade contábil independente. Cotas e principal não são lucro; os 85% dos membros elegíveis dependem de Capital-Dias e apuração.
- Nenhum lançamento cruzado entre domínios; qualquer obrigação de distribuição futura requer registro apropriado e autorização independente.
- O fingerprint de candidato não é chave idempotente persistida e não é autenticação de operação.

## Próximo pacote antes de migrações reais

A arquitetura futura deverá estabelecer: (1) contas por titularidade e competência, (2) esquema persistente versionado com FK de tenant e dupla entrada diferida, (3) políticas RLS e papéis sem bypass, (4) trilha de eventos append-only e estorno, (5) evidência de provedor com consulta server-side e idempotência transacional, (6) prévia de remuneração com versão de política/fechamento, (7) autorização independente para qualquer payout, (8) testes de regressão e restauração no banco **descartável**. O proprietário deverá autorizar separadamente a aplicação de nova migração no banco original após backup e auditoria.

## Checkpoint operacional

M39800 permanece `ANDROID_PROC_RESTRICTED` / `BLOCKED_NO_PROCESS_PROOF`.
Não enviar sinais ao FastAPI, não usar `pkill`, não reiniciar PostgreSQL.
FR Finance original porta 5433, FR Caixinha 2.2 separado e intocado.
`PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`,
`MIGRACOES_LOCAIS=NONE`, `DATABASE_WRITES_ORIGINAL=NONE`,
`APP_FINANCIAL_POSTING=OFF`, `PRODUCTION=BLOCKED`.

A CI com dados TEMP **não representa** comprovação de saldo financeiro ou disponibilização da função no APK.
