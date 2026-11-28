# FR Finance M40840 — bloqueio irrevogável de pool financeira em produção (NO-GO)

**Base:** M40830 `fdff980` e M40821 sincronizado no Termux. **Escopo:** patch somente no código-fonte, ainda não carregado no FastAPI original. O processo Android/Termux segue sem atestação de origem.

## Motivo do bloqueio

Os controles M40570 e M40730 provaram em CI descartável duas ameaças reais de arquitetura: GUCs de identidade falsificáveis sob SQL arbitrário e login SQL emissor comprometido gerando tickets sem PoP. Uma configuração sintaticamente válida de DSN/segredo ou a aprovação de workflows não pode servir de permissão financeira em produção.

## Alteração

`get_db_pool` nega utilização e criação de **qualquer pool financeira** quando `ENVIRONMENT` não é um modo não produtivo explicitamente reconhecido ou quando qualquer flag `PIX_REAL`, `PAGAMENTOS_REAIS`, `ATIVACAO_REAL` não está exatamente `OFF`. O teste adversarial cobre inclusive um pool já em cache.

`get_rls_db_connection` faz a mesma checagem antes de obter conexão e devolve HTTP 503 genérico. A autenticação HTTP `get_current_session` pode ainda consultar o seu papel Auth separado; esta trava é do canal de dados RLS financeiro, **não um firewall global para a API, SMTP, nem credenciais**. Em desenvolvimento/homologação, o uso de RLS continua condicionado à sessão verificada e aos demais guards de fonte; GUC spoofing não foi corrigido.

## Como desbloquear futuramente

Não existe `override`, variável de aprovação nem bypass neste pacote. Uma futura liberação exige auditoria independente da topologia SQL e revogação completa dos caminhos GUC, revisão de funções `SECURITY DEFINER`, papéis mínimos, testes PostgreSQL18 descartáveis adversariais, release gate explícito e migrações reversíveis com backup/restauração e autorização. Não retirar este guard com base em prints verdes de CI.

**Mudanças de schema ou migrations neste pacote:** nenhuma. **Banco local :5433:** não acessado. **FastAPI:** não reiniciado. **PR #2:** Draft, main intacta.

`M40570_GUC_SPOOF=NOT_REMEDIATED`; `M40730_SQL_SIGNER=NOT_REMEDIATED`; `MIGRATIONS=NONE`; `DB_WRITES=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `PRODUCTION=BLOCKED`.

## M40945 — configuração explícita do bloqueio financeiro SQL (source-only)

A checagem M40840 agora exige `ENVIRONMENT` **explicitamente** dentro da lista
de modos de laboratório e exige que **todas as três flags** `PIX_REAL`,
`PAGAMENTOS_REAIS` e `ATIVACAO_REAL` sejam declaradas exatamente `OFF`.
A ausência de qualquer campo não pode ser convertida implicitamente em
`development` ou `OFF`. Um pool financeiro em cache também é
recusado antes de qualquer operação quando a configuração estiver incompleta.

Os testes offline cobrem ausência de cada campo no validador e no caminho de
pool existente. Para manter o funcionamento local em futuras sincronizações,
a configuração explícita deve ser conferida **antes** de recarregar um processo;
esta alteração não modifica o ambiente do aparelho e não autoriza reinício.

Este controle não atesta o ambiente, não protege contra um processo que declare
`ENVIRONMENT=staging` falsamente, não corrige GUCs falsificáveis e não fornece
custódia independente do emissor SQL. Permanecem `M40840=NO_GO` e
`PRODUCTION=BLOCKED`. Migrações, acesso ao banco original, reinícios e
ativação financeira: NONE.
