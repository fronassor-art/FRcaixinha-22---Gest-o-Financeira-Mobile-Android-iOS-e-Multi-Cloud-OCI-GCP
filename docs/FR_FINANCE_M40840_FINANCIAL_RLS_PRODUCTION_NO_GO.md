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
