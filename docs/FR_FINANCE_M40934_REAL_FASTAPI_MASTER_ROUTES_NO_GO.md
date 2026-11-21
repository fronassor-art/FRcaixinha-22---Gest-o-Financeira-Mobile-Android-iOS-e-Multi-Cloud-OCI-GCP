# FR Finance M40934 — verificação das rotas Master realmente registradas no FastAPI (NO-GO)

Continuidade de M40930–M40933, **somente GitHub**. M40933 analisa a sintaxe de `main.py`; M40934 examina as rotas e dependências que o FastAPI efetivamente registra quando o aplicativo é importado para a CI, sem iniciar o servidor nem executar hooks de startup.

## Prova em dois níveis

`backend/tests/test_m40934_fastapi_real_master_route_registry_ci.py` importa `app.main.app` e verifica `APIRoute`, rota HTTP e grafo de dependências:

1. A aplicação deve conter exatamente as seis rotas mutáveis Master conhecidas no namespace `/api/v1/master/` (não apenas seis funções definidas no repositório).
2. Todas exigem a dependência real `require_master`, inclusive suas dependências encadeadas.
3. `license-prices`, `saas-promotions/draft` e `saas-promotions/transition` precisam da dependência incondicional `require_unreleased_master_write` (HTTP 503). As demais devem preservar as classificações de prévia ou proibição contratual.
4. Duas mutações sintéticas de rota em uma aplicação FastAPI de laboratório devem ser recusadas: inclusão de rota não inventariada e substituição por uma rota de mesmo caminho sem autenticação Master.
5. M40840 nega o uso de SQL financeiro em `ENVIRONMENT=production` mesmo com flags de pagamentos OFF.

O workflow `frfinance-m40934-master-registered-routes-ci.yml` usa ambiente Linux efêmero, Python 3.12, importação das dependências do backend e flags financeiras OFF. Não cria PostgreSQL, não lê segredos, não chama rede do provedor, não recebe pagamentos e não inicia processos FastAPI/Termux. **O trabalho é de CI de código**, não prova do código efetivamente carregado em um servidor de staging, não de identidade do banco ou do executor.

## Restrições mantidas

M40934 **não resolve** o ataque M40570 com GUC SQL falsificável, não neutraliza um login SQL app/issuer/guardian comprometido (M40730–M40929), não substitui ACL/RLS nem autoriza Master a acessar dados financeiros de membros. A autorização de escrita Master só poderá ser redesenhada com fronteiras reais de identidade, processo, credenciais, custódia de chave independente e função de autorização SQL não contornável.

Permanecem: `M40840=PRODUCTION_BLOCKED`, `M40930=MASTER_WRITES_HTTP_503`, `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `TERMUX_SYNC=NONE`, `ORIGINAL_PG_5433_CONNECTIONS=NONE`, `MIGRATIONS=NONE`, `SERVICE_RESTARTS=NONE`, `PRODUCTION=NO-GO`.
