# M22802 — Como testar as rotas assíncronas no Termux (Python 3.14)

Resultado local anterior: M22700 (17 failures, 1 pass) e M22800 (2 failures, 3 passes). O marcador de pytest-asyncio não foi reconhecido: plugin não instalado no Python Termux. Nenhum desses 19 erros informa um bug de regras de negócio; o teste nem executou a coroutine.

No Termux Android, fora do banco e sem migrar dados:

    python3 -m pip show pytest pytest-asyncio
    python3 -m pip install --user --upgrade 'pytest>=8.4,<10' 'pytest-asyncio==1.4.1.post1'
    PYTHONPATH=backend python3 -m pytest -q backend/tests/test_m22700_oauth_multitenant_hardening_ci.py backend/tests/test_m22800_no_legacy_financial_routes_ci.py

O projeto GitHub Actions usa seu lock de dependências Python para a CI; não alterar as versões de produção em backend/requirements.txt apenas para consertar o ambiente local de testes. Este pacote corrige adicionalmente um teste estático antigo que confundia a disposição dos espaços em HTTPException com a ausência da proteção 503.

Os testes usam simulações de transporte do Mercado Pago, não invocam requisições externas, não lançam Pix nem consultam tokens privados. Não executar migrações para "consertar" os testes. Caso o plugin local não instale, registrar a versão do Python e do pytest, sem enviar senhas ou tokens.

Status real: OAuth por administrador e OCI staging continuam pendentes. Dinheiro real segue desligado.
