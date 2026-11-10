# FR Finance — M37456 | vínculo de evidência sintética à preparação SaaS

## Checkpoint
- M37455 homologado: `6c92b15`, 45 testes PASS no Termux, 6/6 jobs
  GitHub Actions PASS. PostgreSQL local original intacto.
- Zero pagamentos, zero licenças ativas e Pix real desativado, segundo
  a última validação disponível.

## Natureza e limites desta etapa
O M37456 cria um **vínculo persistente e único, apenas em banco
descartável da CI**, entre uma preparação SaaS e um recibo sintético de
consentimento do M37455. Não valida aceite jurídico, não cobra e não
ativa um administrador ou membro.

O protótipo é deliberadamente **pós-preparação**: o desafio foi criado
depois da preparação sintética já existente. O vínculo NÃO corrige a
cronologia anterior nem transforma o `evidence_hash` placeholder da
tabela `contract_acceptances` em prova do aceite. Um fluxo real
precisará exigir a ação comprovada de aceite **antes** de preparar a
assinatura comercial (ou uma nova transação revalidada).

## Arquivos do pacote
- `backend/tests/sql/m37456_saas_consent_preparation_link_ci.sql`:
  tabela CI com FK e UNIQUE por request/preparação/desafio, RLS
  forçada, flags financeiros imutáveis `false` e trigger append-only.
  SQL exclusivamente sob `backend/tests/sql`, **fora** do catálogo
  de migrações do Termux.
- `backend/scripts/aistudio_m37456_saas_preparation_link_ci.py`:
  valida banco `frcaixinha_staging`, porta 5432 e credenciais CI.
  Exige `GITHUB_ACTIONS=true`, testa divergências e concorrência
  de cinco conexões, impede leitura/escrita brutas pelo worker e
  confirma ausência de cobrança/entitlement/ledger.
- `backend/tests/test_m37456_saas_consent_preparation_link_ci.py`:
  testes de invariantes, isolamento e bloqueios, executáveis em
  qualquer ambiente sem conectar ao PostgreSQL.
- `backend/scripts/aistudio_staging_chain_ci.sh` executa o SQL
  descartável após M37455, testando rejeição de banco incorreto
  antes de criar os objetos.
- `.github/workflows/validacao-atualizacao.yml` incluiu os testes.

## Proteções
- O worker `frcaixinha_saas_consent_ci` permanece sem SUPERUSER,
  BYPASSRLS, SELECT/INSERT direto ou privilégios de aplicação.
- A função `SECURITY DEFINER` aceita somente o worker, compara tenant,
  admin, preço, documento, recibo e preparação em uma transação;
  o lock do tenant serializa corridas de mesma caixinha.
- Um único vínculo imutável por preparação e desafio; repetição
  retorna `REPLAY_CI_NO_WRITE` e não duplica linhas.
- O recibo CI tem digest fornecido por fixture: **não é assinatura
  criptográfica operacional, identidade autenticada nem consentimento
  juridicamente comprovado**.
- A flag `POST_PREPARATION_CI_UNATTESTED` e as quatro permissões
  `legal_consent_verified`, `payment_authorized`,
  `license_authorized`, `real_activation_authorized` permanecem
  invariavelmente `false`.
- Nenhuma tabela de assinatura comercial, pagamentos, licenças,
  `contract_acceptances` ou lançamentos da caixinha é escrita.

## Homologação
O GitHub Actions executa o ensaio transacional em PostgreSQL descartável.
No Termux, executar **apenas testes de segurança em código e catálogo**:

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37456_saas_consent_preparation_link_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não executar** o SQL M37456 nem
`aistudio_m37456_saas_preparation_link_ci.py` diretamente no celular.
A aprovação das verificações não libera produção, Pix ou assinaturas.
