# FR Finance M39900 — Caixas do Master e do Administrador, segregação e continuidade

Data: 14/11/2026. Branch: `atualizacao-ai-studio-9b46a63187`; PR #2 em rascunho.

## Contexto recebido do Termux

M39800 sincronizado em `fedadfd`; `M39800_HEALTH=FR_FINANCE_ONLINE`,
`M39800_PROC=ANDROID_PROC_RESTRICTED`,
`M39800_STATUS=BLOCKED_NO_PROCESS_PROOF`.
A política Android impediu a identificação do dono do socket; NÃO houve
reinício de FastAPI/PostgreSQL, migração ou alteração de conta. O checkpoint
NÃO autoriza encerrar a API nem dá evidência de prontidão de PostgreSQL.

## Três domínios de recursos que não podem ser misturados

1. **PLATFORM_MASTER** — receitas próprias de licenças/assinaturas SaaS e
   despesas operacionais da plataforma FR Finance. Exclusivo do Master.
   O Master não apropria dinheiro de cotas, empréstimos ou receitas dos
   tenants. A contagem de intenções de pagamento não é receita líquida.
2. **TENANT_ADMIN_OWN** — eventual remuneração própria do administrador
   titular da caixinha e despesas de sua própria tesouraria, condicionadas
   a política contratual válida, apuração e fechamento auditado. Nunca
   é carteira de contribuições dos membros.
3. **TENANT_COLLECTIVE** — cotas e contribuições dos membros, empréstimos,
   amortizações, despesas e patrimônio da própria caixinha. Ações do
   administrador neste caixa são administrativas; não há apropriação de
   dinheiro pessoal sem o cálculo e a autorização próprios.

Master, administrador e membro continuam protegidos por autenticação de
papel, escopo de tenant e políticas PostgreSQL RLS. Somente a API, e não
a navegação no Android, pode autorizar acessos.

## Implementado M39900 neste commit

- `src/services/exclusiveCashboxEvidence.ts`: classifica evidência
  de registros e lacunas; não calcula valores monetários, receitas,
  despesas ou saldos inexistentes.
- `src/components/ExclusiveCashboxView.tsx`: organiza cinco blocos por
  caixa, com registros SaaS/ledger apenas como contagem, além de
  despesas, histórico, remuneração e conciliação claramente indisponíveis.
  O ledger da caixinha fica explicitamente **coletivo**.
- `backend/app/exclusive_cashbox_provenance.py`: classificador puro de
  sete famílias de eventos em três caixas. Retorna sempre
  `posting_authorized=False`, `withdrawal_authorized=False` e
  `reconciled_balance_cents=None`.
- Testes frontend e Python CI: papéis exclusivos, separação de origens,
  ausência de saldos inventados e proibição de tratar os registros da
  caixinha como remuneração do administrador.
- Nenhum novo endpoint, tabela, migração, escrita, Pix, saque ou pagamento
  foi ativado. O FastAPI já rodando pode continuar desatualizado.

## Trabalho restante para os caixas operacionais

- **Master:** modelo próprio de despesas, faturas/receitas SaaS efetivamente
  conciliadas, histórico de entradas/saídas, relatórios por competência e
  extrato com trilha de auditoria; validação independente dos eventos de
  pagamento antes do reconhecimento da receita.
- **Administrador:** apuração do percentual contratual de 15%/85% previsto
  no Caderno Mestre e Contrato Técnico, com verificação da política versionada
  por ciclo; remuneração a pagar, despesas próprias e extrato exigem
  comprovação independente e aprovação formal. Não alterar percentuais sem
  revisão normativa expressa.
- **Coletivo:** ledger separado e reconciliado do tenant, fechamento com
  autorização e evidências que suportem o reconhecimento de resultados e
  posterior obrigação para com administrador e membros. Proibir
  transferência implícita entre caixas.
- Antes de implementar mutações: reconciliar contrato técnico e caderno
  mestre, verificar migrações existentes, versionar novo SQL somente se
  necessário, testar em PostgreSQL descartável (CI), aprovar separadamente
  qualquer migração original, validar controle de acesso por RLS e provas
  E2E de pagamentos, estornos e consentimento.
- **Importante:** a API atual expõe percentuais 15%/85% estáticos na
  consulta de administrador, alinhados à regra normativa do produto.
  **Não foi comprovada** a leitura da política versionada de cada ciclo.
  Não usar esses campos para apuração ou liberação de remuneração sem
  resultados reconciliados e confirmação da política autoritativa.

## Checkpoint e limites

`PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`.
`MIGRACOES_LOCAIS=NONE`, `DB_WRITES=NONE`, `FASTAPI_RESTART=NONE`.
FR Finance PostgreSQL exclusivo permanece na porta 5433; FR Caixinha
2.2 permanece intocado. PR #2 permanece Draft; main não recebe merge.

Próxima execução no Termux deve ser somente `git fetch/merge --ff-only`
com revisão do HEAD, sem diagnosticar novamente `/proc` como se fosse
prova de processo. Se houver necessidade de reinício futuro, identificar
manualmente a sessão original do Uvicorn e exigir autorização específica.
