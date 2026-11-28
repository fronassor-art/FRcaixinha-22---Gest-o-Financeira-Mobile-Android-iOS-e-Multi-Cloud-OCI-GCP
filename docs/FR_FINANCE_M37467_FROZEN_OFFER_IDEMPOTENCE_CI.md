# FR Finance — M37467 | congelamento da oferta contratual e idempotência

## Checkpoint de entrada

M37466: commit `24ae75f`, Termux com 141 testes PASS, GitHub Actions 6/6 PASS, catálogo SQL de 106 migrações íntegro e banco PostgreSQL local 5433 preservado. O consentimento e o login ainda são sintéticos, sem efeito jurídico ou comercial.

## O que foi implementado

Em `backend/tests/sql/m37467_frozen_offer_idempotence_ci.sql`, somente no banco PostgreSQL **descartável da CI**:

- Nova tabela append-only `saas_frozen_offer_m37467_ci`, uma linha por `request_id`, com desafio, sessão, administrador, tenant, documento, SHA-256 publicado, versão do preço, período, valor exato em centavos e carimbo de servidor.
- RLS `ENABLE` + `FORCE`, sem permissões diretas de SELECT, INSERT, UPDATE ou DELETE para os papéis da aplicação e do executor. Gatilhos recusam UPDATE, DELETE e TRUNCATE.
- Função `m37467_frozen_offer_transition_ci`, restrita a `frcaixinha_staging`, ao executor `frcaixinha_saas_preprep_ci` e a três flags explícitas de CI. Usa `FOR SHARE OF d,v` nas linhas do contrato e da versão de preço, preservando-as durante a transação. Recalcula o valor do preço publicado (mensal ou anual) em centavos, exige SHA correto e compara com a fotografia da primeira emissão.
- Somente depois dessas verificações chama `m37464_atomic_consent_ci`, que revalida hash de bearer, identidade, sessão, tenant e revogação sob `FOR UPDATE` em `public.sessions`. Nenhuma autorização real é concedida.
- Emissão repetida com os mesmos identificadores gera replay sem escrita. Mudança de desafio, valor, documento, hash, versão de preço, período, sessão ou administrador retorna negação, sem substituir a fotografia já persistida.

## Prova integrada

`backend/scripts/aistudio_m37467_frozen_offer_ci.py` recupera documento e preço **de tabelas publicadas em PostgreSQL**, sem inventar UUID nem valor. Num só worker transacional fictício:

1. Emite o desafio e comprova replay idempotente.
2. Rejeita desafio concorrente para a mesma requisição.
3. Rejeita preço diferente ou hash contratual diferente na confirmação.
4. Confirma o aceite e prepara o rascunho, ambos exclusivamente sintéticos.
5. De uma segunda conexão, tenta alterar o preço publicado e a versão do contrato. As operações devem falhar por `lock_timeout` enquanto a transação mantém `FOR SHARE`, sem alteração persistida.
6. Após commit, confere uma linha por etapa e uma única oferta congelada. Replay posterior não altera registros.
7. Revoga o token sintético e confirma que nem mesmo a oferta congelada autoriza uma nova preparação.
8. Verifica que `saas_payment_intents`, `saas_license_entitlements` e `ledger_entries` continuam com totais inalterados. Nenhum sinalizador real foi ligado.

A nova suíte `backend/tests/test_m37467_frozen_offer_idempotence_ci.py` inspeciona os guardas transacionais, RLS, bloqueios, IDs, flags e a negativa de execução no Termux. O workflow `validacao-atualizacao.yml` executa a suíte, enquanto `aistudio_staging_chain_ci.sh` executa os testes efetivos no PostgreSQL descartável.

## Limitações expressas

Este é **um ensaio de contrato e preço em CI**. Não há credenciais reais, consentimento juridicamente comprovado, cobrança, assinatura comercial, licença paga, ativação de membro, Pix ou implantação OCI. A fotografia contratual não substitui uma prova de aceite autenticada, um recibo fiscal ou a confirmação de pagamento pelo provedor.

O catálogo original de 106 SQL e o banco `frcaixinha_aistudio_dev` na porta 5433 não sofrem migrações do M37467.

## Homologação local segura

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37467_frozen_offer_idempotence_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não executar** os arquivos `m37467_frozen_offer_idempotence_ci.sql`, `aistudio_m37467_frozen_offer_ci.py` ou `aistudio_staging_chain_ci.sh` no Termux.

## Próxima prioridade

M37468: vincular essa fotografia de preço/contrato à auditoria de recibos e ao contrato HTTP, com uma prova de readback após revogação. A habilitação operacional dependerá de autenticação E2E, OCI/HTTPS, contrato válido e PSP conciliado.
