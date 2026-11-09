# FR Finance M30400-M30800 — autorização anual para autoempréstimo

Implementada uma trilha de consentimentos anuais **em banco PostgreSQL
descartável na CI**, para as cláusulas 2.5, 2.6 e 8.8.

- Banco de testes: `frcaixinha_staging` porta 5432 somente GitHub Actions.
- Tabela append-only `annual_self_loan_events_staging` com tenant, ano,
  vínculo, autor, versão SHA de termos, decisão, evidência e request-id.
- Função com trava `FOR UPDATE`, idempotência, rejeição de divergência
  e validação de vínculo, ator, administrador e tenant.
- Releitura que considera membros ativos, a assinatura mais recente e
  revogações; exige pelo menos um outro membro. Mesmo unanimidade
  sintética devolve `real_authorized=false`, `payout_authorized=false`.
- CI verifica PostgreSQL real descartável, replay, revogação, colisão,
  leitura crua proibida e imutabilidade.

**NÃO aplicar** os arquivos 057/058 do catálogo ao PostgreSQL local 5433
nem à OCI. Eles são exclusivos de CI, sem disponibilizar rotas públicas.
Identidade do signatário não foi atestada por provedor e assinatura
jurídica não foi homologada; o fechamento das cláusulas permanece bloqueado.

Para migrar o produto real, serão necessários: versão canônica aprovada,
contrato revisado, plano de roles com least privilege, função transacional
definitiva em migração local própria, assinatura por usuário autenticado,
revalidação em aprovação/reserva/desembolso e testes adversariais de
concorrência. Não liberar dinheiro real só com resultado de CI.

Termux: somente `cd "$HOME/fr-finance"`, git fast-forward e
`python backend/scripts/aistudio_migration_inventory.py repo-check`.
Nenhum SQL aplicado ao 5433.
