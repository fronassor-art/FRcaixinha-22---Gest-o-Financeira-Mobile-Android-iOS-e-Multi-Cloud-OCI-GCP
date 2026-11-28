# FR Finance — M40090: Diagnóstico não invasivo do FastAPI antigo

Data: 15/11/2026. Atualiza o aditivo M40080 sem alterar M39100, o contrato técnico ou as políticas seladas.

## Evidência local recebida

- O usuário confirmou a sincronização `FAST_FORWARD` de `69cad69` para `b5de397` no Termux nativo.
- M40080 obteve `M40080_HEALTH=FR_FINANCE_ONLINE`.
- M40080 obteve `M40080_PROCESS_ORIGIN=NOT_ATTESTED_ANDROID_OR_UNKNOWN`.
- M40080 obteve `M40080_LOADED_SNAPSHOT=M40080_NOT_LOADED_OR_ROUTE_ABSENT`.
- Sem migrações, sem escritas nos bancos, sem reinício e sem ativação financeira.

**Diagnóstico:** o checkout contém o código M40080, mas a rota ainda não foi observada na API antiga. Um listener FR Finance antigo é hipótese plausível, não identidade comprovada do PID. Essa evidência não comprova defeito do PostgreSQL ou senha errada.

## O que o M40090 acrescenta

`backend/scripts/frfinance_m40090_old_fastapi_diagnosis.py` faz somente três rotas HTTP GET fixas em `127.0.0.1:8000`, com confirmação dupla de identidade FR Finance, antes/depois dos checkpoints: `/api/health`, `/api/health/checkpoint` e `/api/health/features/m40080`. Não lê outros endpoints nem segue redirecionamentos de host.

A conferência do proprietário utiliza a classificação somente leitura do M39800 e, quando permitido, observa a **modalidade de bind** da porta 8000 nas tabelas `/proc/net/tcp` e `/proc/net/tcp6`. Não imprime endereços locais, PIDs, inodes, linha de comando, nomes, ambiente, porta de banco, credenciais nem valores de JSON. Falta de acesso a `/proc` no Android gera falha fechada; não se presume proprietário ou segurança da ligação.

Se a rota M40080 retornar 404, o estado é `BLOCKED_M40080_ROUTE_MISSING_IN_RUNNING_API`; isso não representa erro de autenticação ou do PostgreSQL. Caso exista vínculo não loopback, a aplicação continua bloqueada para revisão. Mesmo o estado `PASS_RUNTIME_COMPATIBILITY_READ_ONLY_ONLY` apenas indica compatibilidade de diagnóstico, **não autoriza reiniciar** ou operar financeiramente.

## Pré-requisitos para eventual reinício supervisionado — somente plano

1. Identificar inequivocamente o processo que escuta a porta 8000 e seu diretório/executável; no Android, um `/proc` inacessível mantém esse passo pendente.
2. Confirmar que ele pertence ao projeto FR Finance e não ao independente FR Caixinha 2.2, sem divulgar credenciais ou conteúdos de `api.env`.
3. Conferir funcionamento de PostgreSQL FR Finance separado na porta 5433, apenas com identidade e diagnóstico de leitura aprovados. Não migrar, não reinicializar clusters, não tentar senhas de outras bases.
4. Preparar plano de retorno e janela operacional; registrar autorização explícita do operador para quaisquer sinais/reinícios.
5. Mesmo após um reinício autorizado por processo próprio, repetir saúde, identidade, marca de código, vínculo de sessão e RLS, mantendo `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF` e `ATIVACAO_REAL=OFF`.

O M40090 **NÃO autoriza reiniciar**, encerrar PIDs, executar `run_termux_fastapi.sh` nem instalar APK. Um reinício sem provar o proprietário pode afetar outro serviço e por isso não faz parte deste pacote.

## Escopo

CI testa ausência do marcador, respostas forjadas, troca de identidade durante consultas, bloqueios de inspeção Android, socket IPv4 não loopback e IPv6 não atestado, tudo offline com dados sintéticos. Na execução local, o script só faz GET loopback e leitura de metadados públicos de socket/processo quando possível.

Comandos locais somente após sincronização CI: `python -B backend/scripts/frfinance_m40090_old_fastapi_diagnosis.py`. Retornar checkpoint e resultado, sem reinício.

`M40090_REAL_REVOCATION=NOT_ATTESTED`; `M40090_LOCAL_DB_WRITES=NONE`; `M40090_MIGRATIONS=NONE`; `M40090_FASTAPI_RESTART=NONE`; `M40090_PIX_REAL=OFF`; `M40090_PRODUCTION=BLOCKED`.
