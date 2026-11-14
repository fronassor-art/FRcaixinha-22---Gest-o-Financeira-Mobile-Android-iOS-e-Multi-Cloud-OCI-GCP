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


## Etapa 2/2 — integração FastAPI

- \`/auth/login\` consulta o limitador SQL antes da verificação da senha.
- Falhas 401 contabilizam após rollback; sucesso limpa a contagem dentro da transação de emissão autorizada.
- Limite em memória continua como defesa adicional, mas não como única barreira.
- \`/api/health/ready\` valida o HMAC e permissões efetivas; não declara prontidão produtiva.
- \`/auth/status\` exige chave HMAC configurada para sinalizar modo de teste.
- Teste E2E de CI para 5 tentativas inválidas, bloqueio, limpeza de cooldown sintética, emissão de sessão e logout.
- A chave no CI é exclusivamente sintética, não é credencial real. Segredos de homologação devem ser mantidos em cofre.

Nenhum banco ou usuário local foi alterado. O uso produtivo continua proibido.
