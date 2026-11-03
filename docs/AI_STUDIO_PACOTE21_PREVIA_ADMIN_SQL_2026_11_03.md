# Pacote 21 — consulta consolidada de homologação, somente leitura

Commit base: 746eafff51b3a03a2cceba8f73641f2153d66b4e.
API `GET /api/v1/tenants/{tenant_id}/contributions/annual-preview/admin?year=2027`
é exclusiva do TENANT_ADMIN, protegida por sessão, tenant e RLS.
Retorna o mesmo contrato fechado de prévia cadastral que o demonstrativo
do membro: quantidades, montantes devidos, pagos registrados e saldo.
`profit_amount` sempre null. Sem apuração, liquidação, receita, Pix,
webhook, saldo disponível, mudança de policy, trigger ou migration.
Teste PostgreSQL descartável com dois tenants e múltiplos memberships:
confirma agregação, recusa Master/Membro/tenant cruzado e zero ledger
e fechamento. Apresentação Android na próxima etapa, checkpoint 190.
PR #2 permanece Draft; integração Mercado Pago conforme documentos mestres.
