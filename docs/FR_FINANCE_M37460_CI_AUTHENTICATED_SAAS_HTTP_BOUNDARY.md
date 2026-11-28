# FR Finance — M37460 | fronteira HTTP de autenticação SaaS apenas em CI

## Base homologada

M37459: `a10945d`, 92 testes aprovados no Termux e GitHub Actions 6/6 PASS, rollback transacional e rascunho posterior ao aceite, com banco local intacto.

## Integração feita

O M37460 acrescenta uma rota FastAPI experimental
`POST /api/v1/saas/ci-contract/transition`, registrada **somente** quando,
ao mesmo tempo:
- `GITHUB_ACTIONS=true`
- `FRCAIXINHA_CI_ISOLATED=1`
- `ENVIRONMENT=ci`
- `FR_FINANCE_SAAS_REAL=OFF`
- `FR_FINANCE_PIX_REAL=OFF`
- `FR_FINANCE_M37460_ROUTE=CI_DISPOSABLE_ONLY`
- `FRCAIXINHA_TERMUX_LOCAL_API!=1`

O arquivo `backend/app/main.py` **não monta a rota em ambiente local,
Termux ou produção**. A rota tem `include_in_schema=False`.

A rota usa `Depends(get_current_session)`, a dependência de sessão
PostgreSQL já existente no backend. O administrador deve ser
`TENANT_ADMIN`; Master, membro, outro tenant ou usuário diferente
são recusados. A sessão é confrontada com um *readback* de servidor
separado contendo o identificador técnico de sessão e o administrador
atual. Esse readback é **somente um objeto de teste no M37460**.

As dependências `get_ci_trusted_server_context` e
`get_ci_disposable_executor` retornam **503 por padrão**: não há
credenciais de banco comercial, execução financeira ou cobrança
por meio desse endpoint. Nos testes HTTP, são substituídas por
objetos sintéticos explicitamente injetados via `dependency_overrides`
do FastAPI. Isso comprova somente a fronteira e a passagem correta de
claims testados, não autenticação real de uma pessoa nem funcionamento
de dados de licença do provedor.

## Proteções verificadas

- Corpo JSON mínimo conforme M37459; recusa `role`,
  `tenant_id`, preço, hash contratual ou permissões de ativação
  enviados pelo cliente.
- Confirmação explícita obrigatória em `ACCEPT`, e desafio do
  lado servidor para `ISSUE`; `PREPARE` não confirma contrato
  implicitamente.
- Sessão válida e leitura de contexto menor que 5 minutos,
  admin ativo, documento/preço vinculados ao tenant.
- Corpo limitado a 2048 bytes, `Content-Type: application/json`,
  sem eco de e-mail, documento, token ou segredo; `no-store`.
- Os bloqueios CSRF para cookies do `main.py` permanecem quando
  a rota é registrada no aplicativo principal.
- Todo retorno mantém as permissões reais
  `legal_consent_verified`, `payment_authorized`,
  `license_authorized`, `pix_authorized` e
  `production_authorized` desativadas.

**Limitação de autenticidade:** `AuthenticatedSession` existente
expõe usuário/tenant/papel após leitura de sessão, mas ainda não
transporta um identificador de sessão confiável para esse contrato.
A simulação obtém tal ID de outro objeto fornecido pelo servidor de
testes. Isso NÃO comprova posse de sessão real; será preciso
readback conjunto e vinculação criptográfica antes da produção.

## Arquivos

- `backend/app/routers/saas_authenticated_contract_ci.py` —
  rota, segregação de papéis e guardas de CI, sem executor ativo.
- `backend/app/main.py` — registro estritamente condicionado.
- `backend/tests/test_m37460_saas_authenticated_boundary_ci.py` —
  testes HTTP de papel/tenant, ambiente e payload.
- `.github/workflows/validacao-atualizacao.yml` —
  regressão nova; migrações SQL **não foram alteradas**.

## Teste no Termux (sem banco de dados)

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37460_saas_authenticated_boundary_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

Não executar scripts CI SQL, não habilitar os flags no Termux,
e não ativar Pix ou licenças. O PASS do M37460 não significa
endereço público funcional, assinatura SaaS paga, autenticação
E2E OCI ou aceite juridicamente verificável.

## Próximas dependências

- Readback real em servidor autenticado e captura de consentimento
  em PostgreSQL com RLS e registro imutável.
- Publicação e registro da versão contratual com revisão jurídica.
- Pagamento conciliado com o PSP independente e concessão idempotente
  de licença somente após confirmação financeira.
- OCI, DNS/HTTPS, SMTP, webhooks e habilitações comerciais pendentes.
