# FR Finance M32900–M33300 — recuperação segura de reservas antigas

Projeto AI Studio exclusivo, mesma branch e PR #2. Base homologada M32800:
`8fe6cd1f01f32d47b16dbb1a394108035c64f7d7`.

## Lacuna corrigida

As reservas CI (`HOLD`) tinham bloqueio de concorrência e claim, mas não uma
rotina controlada de compensação após expiração. Isso pode imobilizar vagas sem
matrícula efetiva. O pacote constrói a recuperação sintética, SEM DML em membros,
cotas reais, pagamentos, entitlements, saldo, livro-razão ou Pix.

- **M32900:** recusa reivindicar reservas com 60 minutos ou mais de idade.
- **M33000:** `saas_capacity_expire_ci` valida administrador, tenant, idade e
  ausência de claim, e usa o mesmo lock `FOR UPDATE` por tenant da reserva.
- **M33100:** compensação transacional por evento `RELEASE` já existente,
  idempotente por `request_id`, sem liberações duplas.
- **M33200:** evidência de compensação com RLS forçado e trilha imutável.
- **M33300:** CI PostgreSQL descartável testa corrida, retry, hold reivindicado,
  tenant incorreto, expiração prematura e ausência de operações reais.

O endpoint de liberação/ativação produtiva continua inexistente nesse fluxo.
O prazo de 60 minutos é **uma hipótese de engenharia para CI**, não política
comercial aprovada nem regra implantada na base dos usuários. Nenhuma reserva
local do Termux é alterada. Resgatar capacidade sintética não cria direito a
licença ou pagamento.

**NUNCA aplicar** `backend/staging_migrations/062_saas_capacity_claim_staging_only.sql`
ou `063_saas_capacity_expiry_staging_only.sql` na porta 5433, OCI ou produção.
As duas versões são somente para o banco efêmero `frcaixinha_staging` da CI.

Próximas provas reais ainda pendentes: admissão atômica de usuários/cotas
definitivos, reconciliação autenticada MP, autenticacão Master/MFA, contratos,
migração de staging/OCI e gates de liberação (20 técnicos / 7 externos).
