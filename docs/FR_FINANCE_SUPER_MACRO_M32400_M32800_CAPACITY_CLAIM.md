# FR Finance M32400–M32800 — capacidade e claim transacional CI

Checkpoint M32300: ea646e13f91bd3d4ade84bd1e2a1471b9d8b7162.
Projeto: AI Studio; mesma branch e PR #2. Engenharia sintética, sem ativação.

M32400: claim de reserva existente sob o mesmo lock de tenant que HOLD/RELEASE.
M32500: recontagem de vagas, vínculo administrador e licença sintética vigente.
M32600: request_id único, hold_event_id único, replay idêntico e rejeição de corrida.
M32700: trigger impede a liberação de reserva com claim já persistida.
M32800: PostgreSQL descartável prova concorrência e trilha imutável, sem DML
em membros, cotas, ledger, pagamento ou entitlements.

A quantidade reivindicada permanece contabilizada no HOLD até encerramento
de todo o ensaio; não é somada duas vezes. Uma claim CI não cria membro/cota.
O registro de pagamento original é fixture artificial e NÃO atesta Mercado
Pago. O resultado CLAIMED_CI_NO_REAL_CREATION não autoriza qualquer criação
de usuário, pagamento, Pix, permissão ou prorrogação de licença.

NUNCA aplicar backend/staging_migrations/062_saas_capacity_claim_staging_only.sql
no PostgreSQL Termux 5433 nem OCI. Não há migração local autorizada.

Pendente de produção: transação definitiva que une admissão real à contagem,
reconciliação autenticada do provedor, autorizações Master, aceite contratual,
infraestrutura OCI, validação em aparelhos e gates de liberação externos.

Correção técnica: restaurar modo executável 100755 do script
backend/scripts/aistudio_staging_chain_ci.sh (anteriormente 100644).
