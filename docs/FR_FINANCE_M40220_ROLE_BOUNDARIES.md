# FR Finance M40220 — checkpoint de negação de acesso anônimo no FastAPI local

Data: 15/11/2026, após M40210 PASS no Termux. O usuário confirmou `M40210_PUBLIC_VISIBLE_FOUND=33`, `M40210_HIDDEN_SOURCE_EXPECTED=2`, `M40210_DIAGNOSTIC_EXIT=0`.

## Objetivo

Provar que **12 rotas GET protegidas** da instância FastAPI já em execução retornam **HTTP 401** quando chamadas sem Authorization ou cookies, incluindo as duas rotas intencionalmente ocultas da documentação `M40060` e rotas de administrador, membro, Master, caixa exclusivo e Crédito Especial/Extraordinário.

O comando não envia tokens, cookies, usuários, senhas, IDs de membros reais, POST ou payloads financeiros. Utiliza apenas o endereço literal 127.0.0.1:8000 e um UUID sintético fixo para a caixinha; não segue redirecionamentos nem utiliza proxy. Não lê nem imprime corpos de respostas; limita-se ao status HTTP.

A auditoria estática adicional confirma que a função `get_current_session` do código local chama `bearer_token(request)` antes de `asyncpg.connect`, de modo que requisições sem token são negadas antes da consulta de autenticação. O teste de CI força falha caso uma requisição sem token tente abrir um banco.

## Pré-condições

- M40190: app/contrato/código/rotas/readiness locais coerentes e disponíveis;
- M40210: os dois routers ocultos continuam com autenticação obrigatória e configuração `include_in_schema=False`;
- Código-fonte de autenticação estático mantém rejeição de tokens ausentes antes da abertura de conexão.

Se qualquer pré-condição falhar, não chama as rotas protegidas.

## Limites do PASS

- `PASS_ANONYMOUS_401_BOUNDARIES_ONLY` **não atesta** que perfis autenticados respeitam RLS real, que a sessão não possa vazar entre caixinhas, nem que permissões de POST, política de crédito ou caixa exclusivo funcionem.
- Testes de RBAC com sessões sintéticas executados na CI são evidência adicional, **não** prova de segurança do PostgreSQL do celular.
- A prontidão de autenticação M40190 vem de endpoints públicos, e a verificação pode consultar metadados internos de banco somente para leitura, conforme a rota de readiness.
- Não iniciar/reiniciar PostgreSQL, FastAPI, nenhuma VM ou ligação de provedor; não criar sessões de usuário; não ativar comunicações, PIX, operações financeiras ou produção.

## Execução

Em Termux **nativo** (fora do Debian), depois de sincronizar o novo commit na branch AI Studio, usar:

`python -B backend/scripts/frfinance_m40220_anonymous_role_boundaries_readonly.py`

Sucesso esperado `M40220_EXPECTED_ANONYMOUS_401=12`, `M40220_ANONYMOUS_401_COUNT=12`, `M40220_STATUS=PASS_ANONYMOUS_401_BOUNDARIES_ONLY`. Caso falhe, reportar somente a categoria e HTTP observado, sem dados privados.
