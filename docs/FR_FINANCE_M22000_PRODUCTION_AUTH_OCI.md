# M22000 — Contrato técnico para autenticação de produção na OCI

O backend AI Studio não deve ficar permanentemente incapaz de login de produção. Este pacote adiciona um gate estrito que exige configuração EXPLÍCITA antes de ativar a comunicação da autenticação com o banco OCI:

- ENVIRONMENT=production e FR_FINANCE_AUTH_PRODUCTION_GATE=OCI_STAGING_REVIEWED
- APP_URL HTTPS pública, nenhum Termux ou FRCAIXINHA_TEST_AUTH em produção
- AUTH_SECRET e AUTH_RATE_LIMIT_HMAC_KEY com ao menos 32 bytes, distintos
- três identidades PostgreSQL: frc_ai_app, frc_ai_auth, frc_ai_verifier
- mesmo banco de produção, DNS, porta 5432 e sslmode=verify-full
- papel de superusuário, conexões locais e bancos de desenvolvimento recusados

Nada disso foi configurado no ambiente do operador. O gate está DESATIVADO por padrão. O retorno PRODUCTION_CONFIGURED_UNVERIFIED não é prova de funcionamento do servidor ou de segurança do DB.

Antes de habilitar este gate é OBRIGATÓRIO: provisionar OCI staging; implementar verificações online de roles sem SUPERUSER/BYPASSRLS, grants, FORCE RLS e função emissora de sessão; validar certificados reais; configurar cofre/backup; simular três perfis e isolamento entre tenants; homologar autenticação e revisão de segurança independente.

Não colocar senhas/DSNs/tokens em logs, GitHub ou no chat. Nenhuma VM, API pública, operação Pix real, lançamento ou conciliação financeira foi ativada por M22000.
