# FR Finance M40110 — Correlação conservadora de listener e processo

Data: 15/11/2026. Aditivo ao M40100; Caderno Mestre e contrato técnico preservados.

O retorno do Termux confirmou M40100 sincronizado no commit 9989686 e dois HTTP 404 nos checkpoints M39700/M40080. Existe uma linha de comando candidata ao FastAPI original no mesmo UID do Termux, mas o Android restringe a inspeção de sockets e o proprietário não está comprovado. O PostgreSQL FR Finance porta 5433 e o FR Caixinha 2.2 não foram consultados.

O script M40110 é somente leitura no Termux nativo: depois de confirmar duas vezes a identidade FR Finance pela saúde HTTP em loopback, analisa candidatos de ps do próprio UID. Com um único candidato, tenta lsof caso já esteja instalado (não instala ferramenta), exige listener TCP LISTEN exatamente em 127.0.0.1:8000 e correspondência do PID. Só então tenta ler o diretório do candidato por /proc/PID/cwd para exigir o worktree exato FR Finance.

Não exibe PID, comando, caminho, JSON HTTP ou credenciais. Android ou ferramenta que bloqueie a leitura resulta em diagnóstico insuficiente, não em falso sucesso. Uma correspondência completa é evidência de processo e worktree, não comprovação do bytecode carregado nem autorização para reiniciar. O relatório sempre apresenta M40110_RESTART_AUTHORIZED=FALSE. Não é um plano de intervenção automática.

O script invoca apenas utilitários curtos ps/lsof para inspeção e GET de loopback, sem sinais, reinício, SQL, migração, instalação de APK, OCI ou operações financeiras.

Comando após sincronização segura: python -B backend/scripts/frfinance_m40110_listener_correlation_readonly.py.

Indicadores imutáveis: PIX_REAL=OFF, PAGAMENTOS_REAIS=OFF, ATIVACAO_REAL=OFF, PRODUCTION=BLOCKED; DB_WRITES=NONE; MIGRATIONS=NONE; FASTAPI_RESTART=NONE.
