# FR Finance M37465 — contrato HTTP ligado à transação SaaS de CI

## Checkpoint de entrada

M37464: commit `224662e`; Termux 82 testes PASS, GitHub Actions 6/6 PASS, 106 arquivos de migração intactos. O teste PostgreSQL descartável comprovou bloqueio da mesma linha de `public.sessions` durante ISSUE → ACCEPT → PREPARE e revogação concorrente. O teste não é consentimento de usuários reais.

## O que o M37465 implementa

Este pacote liga **o contrato de API HTTP isolado do M37459** ao **executor PostgreSQL transacional M37464**, sem substituir a função central de segurança nem liberar a rota de produção.

O novo módulo `backend/app/saas_atomic_api_adapter_ci.py` oferece:

- `derive_server_binding_ci`: constrói um vínculo efêmero a partir de `AuthenticatedSession` verificado por `get_current_session` e do bearer bruto já recebido pelo servidor. Calcula SHA-256 para que a função SQL M37464 confira o token *outra vez*, sob `FOR UPDATE`, antes de inserir evidências sintéticas. Não grava ou devolve o token bruto.
- `CIAtomicSQLExecutor`: só aceita conta PostgreSQL descartável `frcaixinha_saas_preprep_ci`, banco `frcaixinha_staging`, porta 5432, sem superusuário e flags CI. Vincula de forma imutável usuário, tenant, sessão, versão do contrato, documento, preço e período. Recusa oferecer o mesmo contrato para sessão, documento ou caixinha divergentes.
- `evaluate_atomic_api_ci`: aplica a validação de corpo HTTP, ação, idempotência, confirmação afirmativa e escopo do M37459 antes de chamar o executor SQL. Devolve somente decisões hipotéticas CI, com permissões reais **sempre falsas**.

O runner da cadeia `backend/scripts/aistudio_m37464_atomic_consent_ci.py` foi reforçado. Durante o ensaio de commit, antes do `worker` iniciar a transação, o runner chama **a dependência real `get_current_session`** contra a conta técnica `frcaixinha_auth_atomic_ci` e uma sessão *artificial* versionada em PostgreSQL descartável. Lê a versão de preço da tabela staging e o contrato publicado de `contract_documents`. As três ações passam então por `evaluate_atomic_api_ci` e `CIAtomicSQLExecutor`, **dentro da mesma transação PostgreSQL**.

A revogação concorrente segue submetida ao bloqueio `FOR UPDATE` do M37464; nenhuma função de API ou adapter pode contornar as verificações de escopo na função SQL.

## Regressões automáticas

`backend/tests/test_m37465_saas_http_atomic_adapter_ci.py` exercita o adaptador, sem banco local, com ambientes incorretos, sessão adulterada, papel Master, tentativas de troca de administrador, documento, preço, tenant e token, datas expiradas, campos HTTP inesperados e executor ausente.

A cadeia PostgreSQL continua verificando revogação antes/depois, rollback completo, idempotência, alteração zero em `saas_payment_intents`, `saas_license_entitlements`, `ledger_entries` e `contract_acceptances`.

Nenhum SQL novo foi adicionado ao catálogo migratório. O worker, o bearer de teste e os IDs são exclusivamente da CI efêmera.

## Limitações que ainda impedem produção

- A sessão é um fixture de banco do GitHub e não comprova senha ou identidade real de um administrador cadastrado.
- O contrato e o aceite são sintéticos. A resposta HTTP não constitui aceite jurídico válido.
- O adaptador não executa cobranças ou provisionamento de licenças. No código real, uma licença deverá depender de confirmação autenticada pelo provedor, conciliação, políticas de risco e auditoria.
- Não há rota de produção nova: a rota de CI existente permanece desabilitada por padrão.
- OCI, TLS/HTTPS, credenciais de autenticação operacional, publicação contratual e testes E2E com contas reais continuam pendentes.

As flags **PIX_REAL, PAGAMENTO_REAL, LICENCA_REAL e ATIVACAO_REAL continuam OFF**.

## Homologação Termux, apenas testes Python

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37465_saas_http_atomic_adapter_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

Não execute manualmente `aistudio_m37464_atomic_consent_ci.py`, SQL de CI ou `aistudio_staging_chain_ci.sh` no PostgreSQL local.

## Próxima prioridade

M37466: prova de readback de sessão + aceite sintético persistido + oferta publicada após commit, com comparação da cadeia inteira e garantias de que nenhum estado de licença/pagamento/ativação foi escrito por engano. Esse readback também será **somente CI**, sem habilitar a operação comercial.
