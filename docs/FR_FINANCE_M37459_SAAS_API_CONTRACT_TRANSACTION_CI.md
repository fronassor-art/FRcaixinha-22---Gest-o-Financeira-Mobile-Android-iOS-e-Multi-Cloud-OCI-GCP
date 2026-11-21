# FR Finance — M37459 | contrato de API SaaS e rollback transacional (CI)

## Checkpoint de referência
M37458 passou no Termux (`5d3068d`, 66 testes, FastAPI respondendo,
banco original preservado). Na CI, foi comprovado que o rascunho sintético é
criado **após** o recibo, sem licença ou pagamento real.

## Objetivo e natureza do macropacote
O M37459 projeta o contrato de uma futura API autenticada para o aceite
pré-contratual SaaS. **Não registra endpoint HTTP em FastAPI**, não autentica
pessoas e não habilita cobranças ou licenças. Sua implementação atual é um
**simulador de contrato de API mais um executor restrito ao banco descartável**.

### Camada 1: fronteira de dados do cliente
`backend/app/saas_acceptance_api_contract_ci.py` recebe exclusivamente:
- `ISSUE`: `action`, `request_id`;
- `ACCEPT`: `action`, `request_id`, `challenge_id`,
  `confirmation` com texto afirmativo exato;
- `PREPARE`: `action`, `request_id`, `challenge_id`.

A sessão, o administrador, a caixinha, a versão contratual, o preço e o
período **não são aceitos no corpo do cliente**. A função exige essas
informações em objetos distintos montados por um executor **sintético
de servidor**. O desafio é gerado no lado de servidor/teste, sem
aceitar UUID do navegador na emissão.

Toda autorização real da resposta é sempre `false`. Rótulos `CI_...`
significam somente avaliação e escrita em fixture descartável, nunca
autenticação real, consentimento legal ou autorização comercial.

### Camada 2: ensaio de atomicidade e idempotência
`backend/scripts/aistudio_m37459_api_transaction_ci.py` chama a função
descartável criada no M37458, usando um novo request e challenge sintéticos.
Testa:
1. Gravar ISSUE → ACCEPT → PREPARE na mesma transação e gerar um erro
   deliberado para verificar **rollback dos três registros**;
2. Confirmar contagem zero após rollback;
3. Repetir com transições confirmadas, sempre em ordem;
4. Recusar PREPARE sem ACCEPT;
5. Reutilizar o request sem gerar outra preparação;
6. Preservar o `contract_acceptances` original e verificar zero pagamentos,
   entitlements e lançamentos de `ledger_entries`.

O executor exige GitHub Actions, `127.0.0.1:5432/frcaixinha_staging`,
credenciais `ci-test-only` e worker isolado
`frcaixinha_saas_preprep_ci`. Nunca usar credenciais ou banco locais.

### Camada 3: testes e CI
- `backend/tests/test_m37459_saas_api_contract_ci.py`
  valida fronteira de autenticação sintética, input estrito,
  fail-closed e respostas sem concessão de licença.
- `backend/tests/test_m37459_saas_api_transaction_ci.py`
  protege o escopo de PostgreSQL descartável, rollback e ausência de
  endpoint em `backend/app/main.py`.
- `.github/workflows/validacao-atualizacao.yml` executa testes Python;
  `backend/scripts/aistudio_staging_chain_ci.sh` executa somente a
  transação descartável após o M37458.

## Pendências para contrato/API REAL
Antes de habilitar a contratação comercial será obrigatório substituir
o principal sintético por `get_current_session` efetivamente verificado
no servidor, validar CSRF para sessões cookie, definir um executor
transacional persistente com RLS, proteção de replay, horários e logs
canônicos, definir política de retenção de consentimento sob revisão
jurídica, homologar o fluxo de cobrança com o provedor, e provisionar
OCI, domínio, HTTPS e observabilidade.

**Nenhuma destas etapas é concedida pelo PASS do M37459.**

## Homologação local segura

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q \
  backend/tests/test_m37459_saas_api_contract_ci.py \
  backend/tests/test_m37459_saas_api_transaction_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

Não executar no Termux o script
`aistudio_m37459_api_transaction_ci.py` ou
`aistudio_staging_chain_ci.sh`. O banco original e o catálogo
de 106 migrações devem permanecer inalterados.
