# FR Finance — M39960: prontidão de consulta com sessão autenticada

**Data:** 15/11/2026. Branch `atualizacao-ai-studio-9b46a63187`, PR #2 Draft.
**Último checkpoint local recebido:** M39950 `5eb015b`, fast-forward no Termux,
`DB_WRITES=NONE`, `MIGRATIONS=NONE`, `FASTAPI_RESTART=NONE`.

## Objetivo

Os pacotes M39940 e M39950 aceitaram apenas **forma** de evidência e de
revisões *alegadas*: quaisquer UUIDs fornecidos por um cliente NÃO
demonstram identidade ou competência. M39960 acrescenta uma fronteira
de identidade **para consulta somente**, utilizando o
`AuthenticatedSession` já emitido pelo servidor em
`get_current_session`, que valida token hash, revogação, expiração e
vínculo PostgreSQL. Não cria aprovação de revisão, nem valida o
documento original. Não há endpoints de gravação.

## Entrega efetiva

**Biblioteca** `backend/app/exclusive_cashbox_review_readiness.py`:

- Aceita exclusivamente objeto `AuthenticatedSession` vindo de
  `get_current_session` — não aceitar identidade do payload, cabeçalho,
  tela, hash documental ou banco de revisão sintético.
- Exige `verification_source=POSTGRES_TOKEN_HASH_REFRESH`, UUIDs
  não nulos de usuário e sessão, timestamps completos com fuso,
  sessão renovada há no máximo cinco minutos, janela de expiração
  positiva, não expirada e sem prazo maior que 30 minutos.
- Master: `MASTER`, `is_master=true`, tenant nulo, acesso somente
  ao domínio `PLATFORM_MASTER`.
- Administrador: `TENANT_ADMIN`, `is_master=false`, tenant
  do token igual ao requisitado, acesso somente ao domínio
  `TENANT_ADMIN_OWN`. Recusa Master, Membro, UUID zero e
  tentativas de leitura de outro tenant.
- O retorno `SESSION_BOUND_VIEW_ONLY` nunca concede:
  `independent_reviewer_verified`, `documentary_review_authorized`,
  `document_authenticated`, `provider_reconciled`,
  `journal_posted`, `payment_enabled` ou `payout_enabled`.

**Duas rotas GET**, registradas no FastAPI existente, com proteção
`no-store` e sem dados identificadores de pessoas, sem referência de
pagamento, token de sessão ou saldo:

- `GET /api/v1/master/exclusive-cashbox/review-readiness`:
  `Depends(require_master)` e prova de sessão vinculada.
  Não consulta ledger coletivo nem valores de assinatura.
- `GET /api/v1/tenants/{tenant_id}/admin-exclusive-cashbox/review-readiness`:
  `Depends(get_current_session)` e conexão RLS do servidor,
  `require_tenant_access`, prova de sessão vinculada e SELECT
  de `public.tenants.admin_user_id` com status `ATIVO`.
  A titularidade deve coincidir com o usuário autenticado.

Ambas as respostas retornam `document_authenticated=false`,
`documentary_review_authorized=false`, `journal_posted=false`,
`payout_enabled=false`, `available_balance_cents=null`.
`session_bound=true` afirma **somente** que a sessão do observador
foi vinculada pelo mecanismo de autenticação do servidor; não é
assinatura de uma revisão, capacidade de postagem ou prova bancária.

## Limites que permanecem

1. As alegações de revisão M39950 continuam sem assinatura;
   o sistema não vincula dois revisores reais a sessões independentes
   ao longo do tempo, não checa segregação de funções persistida
   e não valida consentimento documental.
2. As políticas RLS e a identidade de um usuário com sessão não
   atestam um comprovante SaaS, nota fiscal, liquidação de Pix ou
   remuneração de administrador. Os 15%/85% permanecem prévia,
   dependentes do fechamento anual auditado.
3. A rota do administrador lê apenas titularidade ativa, sem
   consulta a lançamentos de outro tenant.
4. A dependência `get_current_session` precisa continuar ancorada
   no banco original FR Finance configurado, **não** no PostgreSQL
   FR Caixinha 2.2. M39960 não modifica a infraestrutura.
5. O FastAPI local já foi identificado como versão antiga no Android,
   mas seu processo ainda tem bloqueio `ANDROID_PROC_RESTRICTED`.
   **Não reiniciar, matar, recarregar ou reconfigurar a API**
   neste pacote. Após sincronização, o código novo
   pode não estar sendo executado na porta 8000.

## Testes e segurança

`backend/tests/test_m39960_exclusive_cashbox_readiness_ci.py`
valida Master, Admin titular, troca de tenant, dono errado,
papel incorreto, falta de token-hash vinculado, revogação/expiração
modelada, sessão futura/antiga, prazo irrazoável e ausência de
verbos financeiros de escrita. Regressões M39090/M39600/M39910
comprovam seis endpoints GET com `no-store`.

Workflow: `.github/workflows/frfinance-m39960-session-readiness-ci.yml`.

## Situação documental

A baseline M39100 do Caderno Mestre e Contrato Técnico permanece
selada; novas informações são **aditivos**, não reescritas
do checklist original 330/2310. Nenhum requisito de produção ou
de provedor externo passa automaticamente.

`M39960_MIGRATIONS_LOCAL=NONE`;
`M39960_DB_WRITES_ORIGINAL=NONE`;
`M39960_FASTAPI_RESTART=NONE`;
`PIX_REAL=OFF`;
`PAGAMENTOS_REAIS=OFF`;
`ATIVACAO_REAL=OFF`;
`PRODUCAO=BLOCKED`.
