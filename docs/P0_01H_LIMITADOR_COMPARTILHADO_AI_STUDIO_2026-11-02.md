# AI Studio P0-01h — etapa 1/2: limitador compartilhado

PR #2 Draft, repositório exclusivo AI Studio, 02/11/2026. Baseline a37e338.

1. SQL 027: tabela com HMAC do identificador, nenhum email bruto, FORCE RLS.
2. Funções SECURITY DEFINER check/failure/success exclusivamente para Auth.
3. Quinta falha bloqueia 60 segundos; duas conexões não conseguem perder incrementos concorrentes.
4. HMAC da API requer segredo externo com pelo menos 32 bytes; sem fallback inseguro.
5. CI PostgreSQL 16/18: isolamento real, bloqueio, concorrência e teste do helper HMAC.
6. Termux: apenas inventário das 27 migrações, nenhum apply.

**A integração no endpoint FastAPI /login fica para etapa 2/2 após a validação SQL.** Até lá, o limite compartilhado NÃO está ativo no login. Nenhuma credencial/usuário local, nem banco real, foi criado.

Pendências: integração API, limpeza dos registros obsoletos, rotação do segredo HMAC, limitação por IP, TLS, recuperação de senha, provas de provisionamento do verificador. Produção e Pix real continuam bloqueados.
