# FR Finance M40180 — Retomada controlada do FastAPI original após o restart Android

## Evidência operacional
- Usuário executou `pg_ctl start` para o cluster original PG18 do FR Finance na porta 5433.
- `pg_ctl status` confirmou PostgreSQL em execução; `pg_isready` confirmou que aceita conexões.
- A consulta autenticada, somente leitura, com `frc_ai_owner` retornou `FR_FINANCE_PG18=PASS`, validando nome do banco, porta 5433, diretório de dados e PostgreSQL 18.
- FR Caixinha 2.2 não foi acessado. Não houve migração de esquema.
- FastAPI na porta 8000 permaneceu sem resposta durante os diagnósticos anteriores. Não afirmar que continua parado sem nova consulta.

## Mudanças M40180 no inicializador EXISTENTE
Arquivo: `backend/scripts/run_termux_fastapi.sh`.

1. Mantém a verificação do checkout nativo `~/fr-finance`, isolamento M38794, `pg_ctl status` do PGDATA original e `pg_isready` em 5433.
2. Só tenta iniciar FastAPI em 127.0.0.1:8000 quando a porta retorna `ECONNREFUSED`. Qualquer porta ocupada, timeout ou erro inesperado bloqueia o start e não encerra outro processo.
3. Após carregar o arquivo privado `api.env` (sem imprimi-lo), o helper M40180 rejeita valores de ativação para os controles `PIX_REAL`, `PAGAMENTOS_REAIS`, `ATIVACAO_REAL`, trabalhador de e-mail e endpoints de CI. Ele não imprime valores privados.
4. Exporta explicitamente flags reais e trabalhador de e-mail desligados, `ENVIRONMENT=homologation`, e valida DSNs fixos com o `validate_aistudio_database.py` existente.
5. O `exec python -m uvicorn` existente permanece em primeiro plano; **nenhum daemon, supervisor, segundo servidor ou processo auxiliar é criado**. A sessão que executa ficará ocupada até o FastAPI terminar. Não executar no Debian.

### Limitações
- Testes de CI são estáticos e sintéticos; o GitHub não acessa o Termux, a API do celular, o banco ou o arquivo privado.
- Ao iniciar um servidor com endpoints de aplicativo, chamadas posteriores podem criar sessões ou alterações no banco; não declarar `DATABASE_WRITES=NONE` para a aplicação operacional.
- O helper valida o conjunto conhecido de flags. Não substitui auditoria de integrações reais, redes, provedores ou do arquivo privado. O serviço de homologação ainda não pode ser promovido a produção.
- `pg_isready` sozinho não verifica identidade, mas uma consulta autenticada anterior já confirmou o cluster.
- Não executar `M40170` com o PG online, porque esse script é um preflight de cluster parado.

## Execução manual
Após sincronizar commit M40180 e conferir que o PG continua pronto:

`bash backend/scripts/run_termux_fastapi.sh`

Somente o operador pode executar o comando de início; a publicação do código não inicia nem reinicia o servidor. Se a porta 8000 já estiver ocupada, o comando bloqueia sem interromper o processo.

Em outro terminal Termux ou sessão independente, consultar exclusivamente `http://127.0.0.1:8000/api/health`. Confirmar `app=FR Finance`, `status=ONLINE`, mas não confundir health com identidade de processo, versão carregada ou autenticação financeira. O servidor fica em localhost, pagamentos reais OFF e produção bloqueada.
