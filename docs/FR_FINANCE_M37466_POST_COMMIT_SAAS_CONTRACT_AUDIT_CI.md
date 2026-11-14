# FR Finance — M37466 | auditoria histórica pós-commit com sessão revogada (CI)

## Checkpoint anterior

M37465 (`9704e0f`) está homologado: 85 testes PASS no Termux, GitHub Actions 6/6 PASS, banco local 5433 intacto, 106 SQL versionados, pagamentos/licenças/Pix/ativação reais desligados.

## Objetivo do pacote

Comprovar que, **depois de concluir uma transação sintética e revogar a sessão que a originou**, os dados persistidos em PostgreSQL descartável permanecem completos e coerentes, mas não constituem uma nova autorização para acessar o contrato, contratar a assinatura, movimentar dinheiro ou ativar membros.

A auditoria cruza em um único SELECT parametrizado:

- Desafio, recibo e rascunho sintéticos M37458, sem permissões de UPDATE/DELETE.
- Sessão fictícia original e linha de `public.sessions` efetivamente **revogada** pela função de autenticação.
- Administrador, vínculo ativo, tenant, contrato publicado e hash do documento.
- Versão do preço publicada e preços mensais/anuais, com relação anual 10× mensal.
- Ordem temporal `publicação → desafio → recibo → rascunho → revogação`, incluindo validade do desafio no momento do recibo.

## Implementação

`backend/app/saas_post_commit_audit_ci.py` contém a consulta `POST_COMMIT_AUDIT_SQL` e a avaliação `audit_post_commit_ci`. São funções isoladas, sem acesso à rede nem gravações. Uma conclusão positiva retorna `CI_POST_COMMIT_SYNTHETIC_HISTORY_CONSISTENT_NOT_AUTHORITY`, acompanhada de um SHA-256 **apenas diagnóstico**, não assinado e não utilizável como token de autorização. Todos os sinalizadores de consentimento jurídico, identidade real, pagamento, licença, Pix e ativação permanecem falsos.

O runner `backend/scripts/aistudio_m37466_post_commit_readback_ci.py` exige **GitHub Actions isolado** e credenciais exatas do banco efêmero `127.0.0.1:5432/frcaixinha_staging`. Conecta com `default_transaction_read_only=on` e valida o banco/usuário/porta efetivos antes da leitura.

Esse runner é chamado imediatamente após M37464/M37465 na cadeia de staging, quando a sessão de teste foi revogada. Reprova ausência ou duplicidade de registros, combinações de request/administrador/tenant/sessão divergentes e qualquer linha gerada para um token revogado **antes** de iniciar o desafio. Também verifica presença de gatilhos append-only, permissões da conta aplicativo e inexistência de UPDATE direto para o executor.

`backend/tests/test_m37466_post_commit_audit_ci.py` cobre adulteração de IDs, documento/hash, preço, versão, papel, fonte de evidência, status, cronologia e indicadores de autorização. `.github/workflows/validacao-atualizacao.yml` executa a suíte, e a prova integrada ao PostgreSQL valida o estado realmente persistido. **Não há migração nova** e o catálogo permanece com 106 SQL.

## Garantias e limites

A revogação de uma sessão deve impedir novas ações, mas não apagar automaticamente um histórico transacional confirmado. Isso não prova que uma pessoa real aceitou um contrato. A identidade, o desafio, o aceite e o preço do ensaio continuam sendo **fixtures sintéticos de CI**, sem assinatura digital, atestado independente de autenticação humana ou valor jurídico.

Não existe endpoint público novo, infraestrutura OCI implantada, sessão real ativada, cobrança, pagamento conciliado, licença liberada, membro cadastrado ou operação Pix executada.

A ordem da cadeia e o hash de diagnóstico ajudam a detectar inconsistências; não impedem, isoladamente, uma adulteração por alguém com controle administrativo do banco. Produção exigirá trilha de auditoria protegida, logs independentes, gestão de chaves e comprovação operacional.

## Homologação segura no Termux

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37466_post_commit_audit_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não executar no Termux** `aistudio_m37466_post_commit_readback_ci.py`, scripts SQL descartáveis ou `aistudio_staging_chain_ci.sh`.

## Próxima prioridade

M37467: registrar e verificar evidência de idempotência e divergência de preço/contrato entre duas leituras transacionais — ainda em CI — sem jamais converter o resultado em permissão de cobrança ou de ativação.
