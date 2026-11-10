# FR Finance M37458 — aceite antes do rascunho SaaS em PostgreSQL descartável

## Situação anterior
M37457 homologado no Termux: 101 testes, commit `55b326c`. GitHub Actions 6/6 PASS. O teste M37457 comprovou que os recibos históricos criados **depois** da preparação não podem ser usados como aceite anterior.

## Novo ensaio CI, isolado de dados comerciais
O M37458 implementa, apenas no banco descartável `frcaixinha_staging`:

1. Identidade de sessão sintética registrada por `postgres` no servidor CI, sem aceitar sinais de autenticação gerados pela interface.
2. Desafio vinculado ao administrador ativo da caixinha, documento `PLATFORM_LICENSE` publicado, versão de preço e período.
3. Ação afirmativa explícita: `ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE`, gravada pelo servidor CI dentro de cinco minutos.
4. Rascunho **somente após** o recibo, em tabela de CI independente `saas_preprep_drafts_m37458_ci`.
5. Idempotência por request/desafio, uma única linha diante de cinco requisições concorrentes, e imutabilidade contra UPDATE/DELETE/TRUNCATE.

Os dados temporais são definidos por `clock_timestamp()` no PostgreSQL, não pelo relógio do cliente.

O papel `frcaixinha_saas_preprep_ci` não tem privilégios diretos de leitura/escrita das tabelas. A única função de transição é `SECURITY DEFINER`, verifica o papel de login, o banco e a flag CI. O script de execução exige GitHub Actions, host `127.0.0.1`, porta `5432`, banco `frcaixinha_staging` e credenciais exclusivamente de teste.

## Arquivos
- `backend/tests/sql/m37458_saas_consent_before_preparation_ci.sql`: novas tabelas **descartáveis**, papel de função e transações.
- `backend/scripts/aistudio_m37458_preprep_transaction_ci.py`: ensaio de PostgreSQL com erros intencionais, replays, concorrência e conferência dos dados após commit.
- `backend/tests/test_m37458_saas_consent_before_preparation_ci.py`: testes locais sem conexão.
- `backend/scripts/aistudio_staging_chain_ci.sh` e `.github/workflows/validacao-atualizacao.yml`: execução automática na CI.

## Limites importantes
Este pacote **não implementa autenticação real**. A sessão é um fixture do servidor de testes. O texto de confirmação não substitui captura/registro legal ou uma assinatura eletrônica. O rascunho não equivale à tabela de assinaturas reais, contrato juridicamente válido ou licença.

Os objetos criados estão exclusivamente em `backend/tests/sql`, fora do catálogo original de 106 SQL. Não são executados no Termux nem aplicados em OCI. As tabelas `contract_acceptances`, `saas_subscription_preparations`, `saas_payment_intents`, `saas_license_entitlements` e `ledger_entries` permanecem intocadas. Os campos de autorização de pagamento, licença, Pix e ativação ficam sempre falsos.

## Homologação no Termux — sem migração
```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37458_saas_consent_before_preparation_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não executar manualmente** o SQL M37458, o runner de transações ou o pipeline `aistudio_staging_chain_ci.sh` no celular.

## Próxima etapa
M37459: adaptar e auditar um contrato de API autenticada de aceitação SaaS e seu executor transacional **ainda sem produção**, garantindo vínculo com documento e preço publicados e reversão integral de falhas. Pagamento real, Pix, licença ativa, e-mail real e infraestrutura OCI continuam dependências separadas.
