# FR Finance M40140 — preflight seguro de recuperação do FastAPI original

Data: 15/11/2026. Decorrente do M40130. Não autoriza inicialização, reinício, migração, produção nem pagamentos reais.

## Evidências
- M40130 sincronizado no Termux: `1560cb5`.
- `TCP_CONNECTION_REFUSED` nas duas amostras de `127.0.0.1:8000`; GET saúde sem resposta.
- Isso significa que a porta recusou conexão nesses instantes. Não prova que nenhum FastAPI exista em outra porta, no Debian, ou em outra sessão.
- Processo dono do antigo serviço e identidade do PostgreSQL ativo seguem não comprovados; não alterar credenciais ou qualquer cluster.

## Descoberta importante no código

A instalação contém DOIS controladores de origem distinta:

1. `backend/scripts/run_termux_fastapi.sh`: inicializador M38801 previsto para o checkout **`$HOME/fr-finance`**. Refere-se ao PGDATA original de FR Finance `frcaixinha_aistudio_pg18`, porta **5433**, chama os guardas de projeto e do DSN e propõe o uvicorn em **127.0.0.1:8000**.
2. `backend/scripts/aistudio_termux_api_control.py`: controlador histórico aponta para `~/frcaixinha-aistudio-mobile`, um worktree diferente, por isso **não deve ser usado** como comando de start/stop/restart do checkout atual sem revalidação técnica.

O inicializador M38801 é código **capaz de iniciar processo**: não executá-lo com base apenas no TCP recusado. Ele precisa de autorização operacional distinta e de verificação do PG18 original real; `M40140` não contém nem executa tal comando.

## Preflight M40140

O script somente-leitura:

- exige Termux nativo na pasta atual do FR Finance;
- verifica contrato estático do inicializador sem executá-lo;
- verifica o manifesto M38794 e identificadores de PGDATA/PG_VERSION do FR Finance, **sem conectar ao PostgreSQL**;
- examina apenas **metadados** de api.env privado: presença, arquivo regular, proprietário e restrição de permissões. **Não lê seu conteúdo** e não apresenta DSN, usuário ou senha;
- detecta disponibilidade dos nomes pg_ctl/pg_isready **sem executá-los**;
- testa uma única conexão TCP curta e fechada para 127.0.0.1:8000, sem comando de processo.

Não inspeciona PGDATA do FR Caixinha 2.2 além das separações estáticas já verificadas por M38794. Não acessa rede externa, PG porta 5433/5432, HTTP de prontidão, diretórios /proc de processos ou arquivos de credenciais.

**Saída obrigatória:** `M40140_LAUNCH_AUTHORIZED=FALSE`, `M40140_RESTART_AUTHORIZED=FALSE` e status BLOCKED mesmo quando toda configuração estática parecer consistente. Uma verificação estática não comprova um servidor ativo.

Se a API for reiniciada ou inicializada futuramente, isso requer primeiro comprovar os bancos e o processo/serviço corretos, assim como autorização expressa e específica. Manter produção e dinheiro real bloqueados.

## Execução

Somente no Termux nativo, após sincronização de SHA aprovado:

`python -B backend/scripts/frfinance_m40140_original_launcher_preflight_readonly.py`

Não executar `run_termux_fastapi.sh`, `aistudio_termux_api_control.py`, `pg_ctl`, `kill`, `pkill` ou comandos de migração com base neste teste.

Controles: DB_WRITES=NONE, MIGRATIONS=NONE, API_START_STOP=NONE, FASTAPI_RESTART=NONE, PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF, ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED.
