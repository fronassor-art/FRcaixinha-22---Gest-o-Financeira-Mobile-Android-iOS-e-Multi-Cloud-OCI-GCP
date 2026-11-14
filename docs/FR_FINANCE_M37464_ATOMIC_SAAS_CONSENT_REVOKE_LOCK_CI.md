# FR Finance — M37464 | aceite sintético atômico sob revogação concorrente

## Checkpoint de entrada

M37463, commit `406bceb`, homologado no Termux: 78 testes aprovados, FastAPI operacional, 106 SQL íntegros e banco local preservado. GitHub Actions 6/6 PASS.

## Objetivo

Eliminar, **em teste descartável**, a janela entre a verificação de token/sessão e o registro sintético do aceite SaaS. O M37463 já provava a leitura do contrato após autenticação; o M37464 exige a verificação e o bloqueio da **mesma linha de sessão PostgreSQL** em que a transição é executada.

## Arquitetura implementada

- `backend/tests/sql/m37464_atomic_consent_lock_ci.sql`: cria somente na CI PostgreSQL `frcaixinha_staging` a função `m37464_atomic_consent_ci`, protegida por `SECURITY DEFINER`, `session_user` exato, duas flags de isolamento e `FOR UPDATE OF s` na linha de `public.sessions`.
- Os argumentos são: ação, SHA-256 do bearer calculado no servidor, sessão, desafio, requisição, tenant, administrador, documento, versão de preço, período e confirmação afirmativa. A função rejeita escopo ou token divergente, sessão revogada/expirada, administrador sem vínculo ativo e confirmações não explícitas.
- Após revalidar a sessão **dentro da transação**, chama a função M37458, que verifica documento publicado, versão comercial e ordem ISSUE → ACCEPT → PREPARE. As três transições ocorrem dentro de uma única transação no ensaio de CI, e todos os seus registros podem ser revertidos em conjunto.
- A função de revogação já existente `auth_revoke_session` precisa atualizar a mesma linha de `public.sessions`; portanto, não pode concluí-la entre a validação e a gravação do aceite enquanto a primeira transação detém o bloqueio.
- Os papéis `frcaixinha_saas_preprep_ci` (executor sem DML direto) e `frcaixinha_auth_atomic_ci` (revogador de teste sem superusuário) não recebem acesso direto a dados de pagamentos ou licença. A segunda conta é criada somente no banco descartável, sem credenciais reais.

## Provas transacionais automatizadas

O runner `backend/scripts/aistudio_m37464_atomic_consent_ci.py` exige GitHub Actions e as credenciais específicas `127.0.0.1:5432/frcaixinha_staging`.

1. **Revogação vence:** revoga a segunda sessão antes de ISSUE; a função nega a transição, sem nenhuma gravação contratual.
2. **Rollback completo:** emite desafio, registra aceite e cria rascunho dentro de uma transação que deliberadamente falha; após o rollback, as três tabelas ficam sem registros dessa requisição.
3. **Consentimento vence:** a sessão é bloqueada por `FOR UPDATE`, registra ISSUE → ACCEPT → PREPARE e mantém a transação aberta. Uma revogação concorrente com `lock_timeout` falha com SQLSTATE `55P03` — não pode passar no meio da contratação.
4. **Commit e replay:** conclui a transação, verifica uma linha por etapa e um único rascunho, sem duplicação em repetição.
5. **Revogação posterior:** revoga o token após o commit; tentativas seguintes de ACCEPT ou PREPARE retornam negação.
6. **Invariantes financeiras:** totais de `saas_payment_intents`, `saas_license_entitlements` e `ledger_entries` permanecem inalterados, assim como `contract_acceptances`. Nenhuma permissão real é ativada.

A regressão `backend/tests/test_m37464_atomic_consent_lock_ci.py` confere os guardas de função, limites de papéis, isolamento de banco, transação atômica, ausência de escrita financeira e fail-closed.

O pipeline executa esse ensaio **depois de M37459 e antes dos testes de faturamento** para não confundir os registros de outras fixtures. Nenhuma migração do catálogo de 106 SQL foi alterada.

## Limites de homologação

A sessão e o contrato ainda são **fictícios**. Esta prova não cria consentimento juridicamente válido, validação E2E de uma identidade real, cobrança por provedor, assinatura ativa ou autorização Pix. O fato de uma revogação ser impedida por um lock durante a transação somente define a ordem correta das operações; não reverte registros já confirmados antes da revogação.

Os próximos requisitos de produção continuam: API real com sessão verificada em servidor, política de consentimento/jurídica, idempotência e trilha de auditoria, conciliação de pagamento no PSP, HTTPS, OCI, credenciais e testes de usuário reais.

## Homologação segura no Termux

```bash
export PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1
python -m pytest -q backend/tests/test_m37464_atomic_consent_lock_ci.py
python backend/scripts/aistudio_migration_inventory.py repo-check
```

**Não executar** os arquivos `backend/tests/sql/m37464_atomic_consent_lock_ci.sql`, `backend/scripts/aistudio_m37464_atomic_consent_ci.py` ou a cadeia de staging no Termux.

Todos os pagamentos, licenças, Pix e ativações reais permanecem desligados.
