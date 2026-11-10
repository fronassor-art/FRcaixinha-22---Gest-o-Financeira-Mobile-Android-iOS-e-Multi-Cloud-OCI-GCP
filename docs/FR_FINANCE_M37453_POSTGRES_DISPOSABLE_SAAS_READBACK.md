# FR Finance M37453 — leitura contratual persistida em PostgreSQL descartável

## Base da homologação

- M37452: 58 testes CI + 14 regressões de licença PASS no Termux; banco local intacto.
- M30900–M31300: já existe preparação de SaaS **sintética** persistida em
  `frcaixinha_staging` durante o GitHub Actions. O M37453 reutiliza essa
  infraestrutura. **Nenhuma migração SQL adicional** é criada.
- O inventário de produção/local permanece com 0 licenças comprovadas,
  0 pagamentos e 0 preparações segundo a última atestação M37450. O
  experimento descartável não altera essas contagens.

## Código novo

- `backend/app/saas_disposable_checkout_readback_ci.py`
  contém a consulta SQL com parâmetros e a validação pura e fail-closed.
- `backend/scripts/aistudio_m37453_disposable_saas_readback.py`
  permite execução **somente no GitHub Actions**, por `postgres`,
  banco `frcaixinha_staging`, host `127.0.0.1`, porta `5432`,
  com `default_transaction_read_only=on`. Rejeita os demais contextos.
- `backend/tests/test_m37453_saas_disposable_readback_ci.py`
  exercita adulteração de IDs, escopo, RLS esperado, validade de datas,
  evidência de documento, versão do preço, valores em centavos,
  conta de pagamentos, licença e ledger. Os testes puros podem ser
  executados no Termux sem conectar ao banco de dados.

## Cadeia auditada pelo readback descartável

1. Consulta o request sintético criado por `059_saas_enrollment_staging_only.sql`.
2. Compara o administrador e tenant com a preparação persistida e
   com o cadastro/vínculo do administrador.
3. Exige `PLATFORM_LICENSE`, documento publicado, aceitação do mesmo
   usuário, hash sintaticamente válido, vínculo à preparação e cronologia.
4. Compara versão do preço, plano ativo, período e regra anual
   `10 × preço mensal`.
5. Exige ZERO intenções de pagamento, ZERO entitlements, ZERO
   lançamentos de ledger de tenant e sinalizadores de cobrança desligados.
6. Executa tentativas de leitura por outra caixinha ou administrador
   e exige zero resultados.

## Lacuna contratual expressa

A tabela `contract_acceptances` possui `evidence_method` e
`evidence_hash`, mas **esses campos, sem prova independente, não
comprovam aceite explícito operacional/legal**. O M37453 verifica
apenas a coerência de um fixture rotulado `CI_VERIFIED_IDENTITY`.
Mesmo um readback aprovado declara sempre
`explicit_consent_operationally_verified=False` e
`payment_verified=False`.

Antes do onboarding real, será necessário integrar coleta de aceite
explícito e prova imutável vinculada à identidade, documento publicado
e versão, com proteção contra replay; também faltam identidade real,
OAuth/provedor, conciliação financeira segregada, licença transacional,
infraestrutura OCI e revisão comercial.

## Homologação

A execução de PostgreSQL **real mas descartável** é feita só na
GitHub Actions, após `M31300_SAAS_ENROLLMENT_POSTGRES=PASS`, por
`backend/scripts/aistudio_staging_chain_ci.sh`.

Para Termux (apenas testes puros e leitura de catálogo SQL):

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37453_saas_disposable_readback_ci.py
python -m pytest -q backend/tests/test_m37452_saas_checkout_chain_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

Nunca execute a rotina `aistudio_staging_chain_ci.sh` nem o
script `aistudio_m37453_disposable_saas_readback.py` no Termux.
O resultado CI não concede usuários, licenças, Pix ou pagamentos reais.
