# FR Finance — M39700: identificacao do FastAPI carregado e prontidao local

Data de referencia: 14/11/2026. Branch atualizacao-ai-studio-9b46a63187, PR #2 Draft.
Checkpoint do operador: M39600 TERMUX=PASS, SHA 20c5d85, novas migrações NONE, escritas NONE, Pix OFF.

## Problema e objetivo

O arquivo da rota de Crédito Especial existir no Git não garante que a instancia Uvicorn em 127.0.0.1:8000 tenha carregado essa revisao. O processo Python pode continuar utilizando os modulos antigos depois de uma sincronizacao. O antigo /api/health prova apenas identidade FR Finance e estado online, nao prova o commit em execucao.

Este pacote cria um marcador nao secreto de codigo carregado. Ele nao prova SHA exato, reconciliacao financeira, migracoes historicas ou autorizacao de producao.

## Componentes entregues

1. backend/app/m39700_runtime_contract.py: contrato imutavel FR_FINANCE_M39700_RUNTIME_V1, verificacao das seis rotas GET obrigatorias, identidade da aplicacao e prontidao local.
2. backend/app/main.py: novo GET /api/health/checkpoint, sem conexao PostgreSQL, senha ou movimento financeiro, fora do schema OpenAPI. Resposta inclui repository_head_verified=false, database_catalog_attested=false, bank_reconciled=false, real_pix_enabled=false, real_payments_enabled=false e production_authorized=false.
3. backend/scripts/frfinance_m39700_termux_runtime_check.py: ate quatro GETs locais fixos e sem token, exclusivamente no Termux nativo e na arvore FR Finance. Nao reinicia FastAPI, nao le credenciais, nao modifica banco.
4. backend/tests/test_m39700_runtime_attestation_ci.py: regressao de 404, aplicativo incorreto, rota ausente, GET/POST, contrato obsoleto, 503 de prontidao e marcadores falsos.
5. .github/workflows/frfinance-m39700-runtime-handoff-ci.yml e obrigatoriedade em .github/workflows/validacao-atualizacao.yml.

## Matriz de interpretacao segura

| Estado | Significado |
|---|---|
| PASS_SOURCE_ONLY_NO_RUNTIME_ATTESTATION | Os arquivos existem no Git; nao ha evidencia sobre o processo rodando. |
| STALE_OR_NOT_LOADED | O FastAPI rodando nao publicou o checkpoint M39700; primeiro conferir sua origem, nunca reiniciar processo desconhecido. |
| GET_ROUTES_MISSING | Uma ou mais das seis rotas GET obrigatorias estao ausentes; nao inferir problema de banco apenas a partir do 404. |
| WRONG_APP_OR_HEALTH | Resposta de aplicacao diversa ou health invalido; nao migrar nem trocar credenciais. |
| BLOCKED_READINESS_503_AUTH_OR_PG18_REVIEW | A API respondeu 503 no readiness; pode envolver configuracao ou PostgreSQL, sem afirmar causa precisa. |
| PASS_READ_ONLY_RUNTIME_AND_TEST_AUTH | Instancia carregou contrato M39700, todas as rotas GET, identidade FR Finance e prontidao de autenticacao local. Nao e homologacao E2E ou de producao. |

O GET /api/health/ready da API consulta metadados SQL read-only usando a propria configuracao existente. Por isolamento entre projetos, o programa so chama esse endpoint **depois** de validar FR Finance ONLINE, marcador carregado M39700 e todas as rotas GET obrigatorias. Se a aplicacao for desconhecida ou antiga, a consulta de prontidao nem sequer ocorre. O programa de terminal nao conecta diretamente ao banco nem recebe senha.

## Handoff

Apos CI verde, sincronizar novo SHA por fast-forward no Termux nativo, sem reaplicar SQL 110 a 113 e sem repetir comandos de restart. Executar o novo verificador uma vez e retornar a saida. Se o marcador nao estiver carregado, investigar o processo antigo na porta 8000 antes de planejar qualquer reinicio autorizado. O pacote nao gera migracao SQL nova.

## Rastreabilidade / seguranca

P0-02: inspecao de API rodando e readiness do FR Finance. Nao substitui Caderno Mestre, Contrato Tecnico, matriz 330, os 20 gates operacionais, 7 provedores ou 50 cenarios AT. A base FR Finance e 127.0.0.1:5433/frcaixinha_aistudio_dev, separada do FR Caixinha 2.2. O catalogo original permanece nao verificado por esta etapa.

PRODUCTION_RELEASE=BLOCKED; PIX_REAL=OFF; PAGAMENTOS_REAIS=OFF; ATIVACAO_REAL=OFF. Nenhuma migracao local, restart, provider live ou notificacao real.
