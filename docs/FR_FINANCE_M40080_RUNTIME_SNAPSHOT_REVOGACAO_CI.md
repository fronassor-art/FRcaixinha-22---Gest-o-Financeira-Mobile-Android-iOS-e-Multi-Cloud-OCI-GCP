# FR Finance M40080 — Diferenciar Git sincronizado do FastAPI em execução

**Data:** 15/11/2026. **Checkpoint local recebido:** M40070 `69cad69`, `FAST_FORWARD`, nenhuma migração e FastAPI inalterado.

## Runtime seguro e sem reiniciar

O FastAPI principal recebe `GET /api/health/features/m40080`, que expõe exclusivamente três hashes SHA-256 de arquivos de código capturados **uma vez ao importar** o módulo Python: `main.py`, `exclusive_cashbox_review_gaps.py` e `m40080_loaded_source_marker.py`. Não realiza leitura do banco, de configuração privada, de tokens ou de sessão no endpoint. Não expõe PID, caminho absoluto, variáveis ou dados financeiros.

O comando Termux nativo `python -B backend/scripts/frfinance_m40080_loaded_source_readonly.py` compara essa marca com os arquivos do checkout atual e, usando o verificador M39800, exige evidência do processo Uvicorn original como proprietário da porta `127.0.0.1:8000`. O verificador só faz GET em loopback e inspeciona metadados do processo quando o Android permite; se a inspeção `/proc` estiver restrita, o resultado completo é **BLOCKED**. Se a API antiga não contém a rota, retorna `M40080_NOT_LOADED_OR_ROUTE_ABSENT`, não uma afirmação de erro de PostgreSQL.

**Limite:** os hashes são evidências de arquivos disponíveis na importação, não uma assinatura criptográfica de bytecode efetivamente executado, Git SHA confirmado, autenticidade de binário ou atestado de banco. Mesmo se o snapshot corresponder, nenhuma aprovação, pagamento ou produção fica habilitada. Não reiniciar nem manipular o servidor por este script.

## Regressão de revogação em CI

M40080 reaproveita o banco PostgreSQL 18 **descartável** e as credenciais sintéticas M40070. Executa requisições reais ao `get_current_session` e à RLS pelo `TestClient` sem sobrescrever dependências.

1. Sessões A/B alternadas e acesso cruzado negado.
2. Revogação registrada e confirmada no PostgreSQL descartável por cliente SQL de laboratório; a sessão A passa a receber 401 e B continua a visualizar apenas as próprias lacunas.
3. Transferência do titular de B no fixture SQL; a sessão B, ainda válida, passa a receber 403 no próximo GET por perda de autorização RLS.
4. POST para aprovar segue 405. Não ocorre criação de política ratificada, lançamento financeiro ou PIX.

**Há UPDATE de sessões e titularidade apenas na CI descartável**; são mutações de laboratório previstas para comprovar transição, jamais no PostgreSQL FR Finance 5433, FR Caixinha 2.2 ou bancos de produção.

## Preservações e restrições

Não foi criada migração local, não há restart do FastAPI, instalações APK, liberação de pagamentos, revisão juridicamente válida ou deploy OCI. Documentação M39100 e contrato técnico selado permanecem intocados.

`M40080_RUNTIME_CODE=READ_ONLY_IMPORT_SNAPSHOT`; `M40080_REAL_REVOCATION=NOT_ATTESTED`; `M40080_LOCAL_DB_WRITES=NONE`; `M40080_FASTAPI_RESTART=NONE`; `M40080_REAL_REVIEW_APPROVAL=FALSE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.
