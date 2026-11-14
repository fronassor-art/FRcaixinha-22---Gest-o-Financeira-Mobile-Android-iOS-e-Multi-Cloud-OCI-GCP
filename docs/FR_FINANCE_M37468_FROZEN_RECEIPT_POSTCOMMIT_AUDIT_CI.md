# FR Finance M37468 — auditoria pós-revogação da oferta congelada e recibo (CI)

## Entrada homologada

M37467 (`a4741e4`): Termux 90 testes PASS, GitHub Actions 6/6 PASS. Em PostgreSQL descartável foram comprovados hash e valor da oferta imutáveis, replay sem duplicação e bloqueio de atualizações concorrentes de preço/contrato. Catálogo do aplicativo preservado em 106 arquivos SQL.

## Escopo implementado

O módulo `backend/app/saas_frozen_receipt_audit_ci.py` compõe um SELECT histórico único do M37466 com a tabela append-only `saas_frozen_offer_m37467_ci`. O vínculo exige **mesmo request, desafio, sessão, tenant, administrador, documento, hash SHA-256, versão de preço e período**. A leitura não usa bearer bruto nem devolve token de acesso.

`verify_frozen_receipt_ci` valida a cadeia de quatro registros sintéticos: desafio → fotografia da oferta congelada → recibo de aceite fictício → rascunho. Exige que a revogação da sessão tenha ocorrido depois da preparação, que o contrato corresponda ao documento publicado e que o preço em centavos esteja exato (mensal ou anual) e coerente com o preço versionado.

O resultado positivo contém apenas um estado de **consistência histórica sintética** e um hash diagnóstico determinístico, **não assinado**. Campos de identidade verdadeira, aceite jurídico, pagamento, licença, Pix e ativação são todos falsos.

`historical_receipt_view_ci` retorna um resumo interno somente no ambiente `GITHUB_ACTIONS=true` / `ENVIRONMENT=ci` e com SaaS/Pix/licença reais OFF. **Não há rota HTTP pública**. Um registro histórico de sessão revogada nunca permite executar nova contratação.

## Integração PostgreSQL descartável

O executor `backend/scripts/aistudio_m37468_frozen_receipt_readback_ci.py` roda na mesma cadeia M37467, após a revogação da sessão, com conexão restrita a `127.0.0.1:5432/frcaixinha_staging`, `default_transaction_read_only=on` e confirmação do banco/ator/porta.

Ele exige apenas uma linha por etapa, repete a leitura para verificar estabilidade, testa outros IDs de request/tenant/admin/sessão sem vazamento, valida os gatilhos append-only e o RLS FORCE, e assegura que a conta do aplicativo e o executor não receberam acesso direto à fotografia.

O workflow `.github/workflows/validacao-atualizacao.yml` inclui `backend/tests/test_m37468_frozen_receipt_audit_ci.py`: alterações de campos, IDs, centavos, assinatura inexistente, hash, timestamps, sessão, status e flags reais devem falhar fechadas.

O runner executa somente SELECT e não modifica a base original do Termux ou as 106 migrações do aplicativo.

## Limites e pendências

Tudo é CI sintético: nenhum login de pessoa real, consentimento juridicamente atestado, assinatura comercial, pagamento conciliado, licença habilitada ou Pix real. Mesmo a auditoria íntegra não comprova autenticidade contra um invasor com controle de banco; produção precisa de logs externos protegidos e política de consentimento, além de OCI/HTTPS, autenticação e provedor de pagamentos homologados.

## Verificação local segura

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37468_frozen_receipt_audit_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não execute** `aistudio_m37468_frozen_receipt_readback_ci.py`, SQL de staging ou `aistudio_staging_chain_ci.sh` no banco PostgreSQL do Termux.

## Próxima prioridade

M37469: consolidar o caminho de auditoria em um relatório de segurança operacional e uma matriz de bloqueios para implantação na OCI, evitando regressões de permissões reais sem repetir testes exclusivamente sintéticos.
