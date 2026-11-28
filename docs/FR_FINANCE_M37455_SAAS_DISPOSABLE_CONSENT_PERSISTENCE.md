# FR Finance M37455 — consentimento SaaS persistido em PostgreSQL descartável (CI ONLY)

## Base do checkpoint

O M37454 foi homologado no Termux em `28f735d`: 64 testes aprovados, API
respondendo, sem migração local. O GitHub Actions também teve 6/6 PASS.
Este novo pacote acrescenta um **ensaio de escrita e replay em banco descartável**,
sem criar aceite contratual real.

## Implementação

- SQL de teste: `backend/tests/sql/m37455_saas_consent_disposable_ci.sql`.
  Deliberadamente fora das famílias de migrações, sob `backend/tests/sql/`.
  Cria duas tabelas CI de desafios e recibos, **não** modifica
  `contract_acceptances`, `saas_subscription_preparations`,
  `saas_payment_intents` ou `saas_license_entitlements`.
- Runner: `backend/scripts/aistudio_m37455_saas_disposable_ci.py`.
  Exige GitHub Actions e PostgreSQL descartável
  `127.0.0.1:5432/frcaixinha_staging`, com credenciais exclusivamente
  sintéticas `ci-test-only`.
- Papel isolado `frcaixinha_saas_consent_ci` criado **somente** em CI:
  `NOSUPERUSER`, `NOBYPASSRLS`, `NOINHERIT`, sem DML/SELECT
  direto nas tabelas de desafios e recibos.
- Funções `SECURITY DEFINER` são executáveis só pelo papel CI,
  verificam nome do banco, `session_user` e a flag de isolamento,
  vínculo com tenant/administrador, documento publicado,
  versão do preço e preparação sem cobrança.
- A confirmação exige texto exato, UUID de desafio/sessão e digest SHA-256
  sintaticamente válido. O digest é **fornecido pelo fixture CI**: não
  é prova de que um usuário real digitou ou confirmou o contrato.
- Um desafio por preparação; cada desafio admite apenas um recibo.
  Solicitações idênticas retornam `REPLAY_CI_NO_WRITE`; colisões e
  divergências são negadas. A concorrência é testada com conexões distintas.
- Triggers impedem `UPDATE`, `DELETE` e `TRUNCATE` nos recibos,
  com resultado append-only de teste.
- O fixture `contract_acceptances.evidence_hash` existente continua
  com o hash artificial anterior: **não é atualizado**.
  Mesmo a gravação positiva é `RECORDED_CI_NOT_LEGAL_CONSENT`.

## Provas e limites

A SQL contém guard de rollback no banco errado, e o runner recusa Termux,
OCI, `PGPORT=5433` e credenciais do banco local.
A CI compara contagens antes e depois: zero pagamentos, zero entitlements,
zero lançamentos de caixa e nenhuma alteração no aceite antigo.

A persistência é uma **simulação transacional**. Não habilita aceite
juridicamente verificável, cobrança, emissão de licença, Pix,
entrada de participantes nem produção. Uma futura implementação real
precisa de sessão autenticada, consentimento explícito capturado e
registrado pelo servidor, desafio entregue, gestão de chaves de produção,
evidência imutável, controles legais e transação idempotente autorizada.

## Homologação

Apenas o GitHub Actions executa o SQL/runner de persistência no
PostgreSQL descartável, por `aistudio_staging_chain_ci.sh`, após M37453.

No Termux, executar **somente testes estáticos**:

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37455_saas_disposable_consent_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

Não executar os arquivos SQL ou o runner M37455 diretamente no celular.
Confirmar a conclusão do workflow antes de alegar homologação integral.
