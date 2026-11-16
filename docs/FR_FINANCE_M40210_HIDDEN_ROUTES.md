# FR Finance M40210 — corrigir falso positivo M40200 sem expor rotas privadas

Data: 15/11/2026. Evidência M40200 executada no Termux em commit c945ca4:
- M40190 pré-condição operacional: PASS
- OpenAPI público: 33 dos 35 pares de rota/método esperados
- Falhas reportadas: apenas GET /api/v1/tenants/{tenant_id}/admin-exclusive-cashbox/review-policy-gaps e GET /api/v1/master/exclusive-cashbox/review-policy-gaps
- Todas as cinco rotas POST de campanhas e as demais 28 rotas documentadas foram encontradas como declarações no OpenAPI, mas não executadas
- Nenhuma migração, POST, pagamento ou reinício.

## Causa conferida no repositório

Os dois routers em `backend/app/routers/exclusive_cashbox_review_gaps.py` têm `include_in_schema=False` no **APIRouter**. Portanto seus endpoints deliberadamente **não aparecem no `/openapi.json`**, mesmo que registrados por `app.include_router` em `backend/app/main.py`. Essa opção não é prova de endpoint ausente nem permissão para descobrir usuários por requisições. M40200 supunha incorretamente que os 35 pares de rota/método apareceriam na documentação pública.

Não remover `include_in_schema=False`, não relaxar `require_master`, `get_current_session`, `get_rls_db_connection`, `verify_review_readiness` nem titularidade ativa para fazer diagnóstico passar.

## Correção

M40210 distingue:
- **33 rotas visíveis** em OpenAPI (incluindo apenas documentação de POST, sem executar nenhum).
- **2 rotas intencionalmente ocultas**, com comprovação **somente estática** de decoradores GET, dependências de autenticação e registro em `main.py` (análise AST, sem importar a API).
- **35 declarações esperadas** no código; não são 35 endpoints publicamente documentados.

O M40190 continua como gate de saúde, versão de contrato, hashes de importação de três arquivos e readiness da autenticação de testes. Mesmo com PASS M40210, a execução das duas rotas ocultas, seus controles de papel, RLS real, proprietários de processo Android, políticas contratuais, aprovação de revisores, pagamentos e PIX reais NÃO foram testados.

Não há erro demonstrado nas rotas de crédito ou no PostgreSQL. Não é necessário reiniciar o FastAPI. Migrações, criação de sessões, alterações de esquema e novos ambientes estão fora do escopo.

## Uso no Termux nativo

`python -B backend/scripts/frfinance_m40210_hidden_route_openapi_correction.py`

PASS esperado com documentação pública consistente: `M40210_PUBLIC_VISIBLE_FOUND=33`, `M40210_PUBLIC_MISSING_COUNT=0`, `M40210_HIDDEN_SOURCE=PASS_TWO_HIDDEN_SOURCE_DECLARATIONS_NOT_RUNTIME_TESTED`, `M40210_STATUS=PASS_33_PUBLIC_AND_2_HIDDEN_SOURCE_ONLY`. A implementação dos dois endpoints ocultos em execução não é atestada.

Produção, PIX, pagamentos reais e autorização financeira continuam OFF.
