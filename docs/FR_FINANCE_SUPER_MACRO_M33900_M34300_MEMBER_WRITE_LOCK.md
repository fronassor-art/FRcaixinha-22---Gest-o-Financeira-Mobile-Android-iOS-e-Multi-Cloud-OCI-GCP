# FR Finance M33900–M34300 — fechamento de escrita não licenciada

**Base homologada:** M33800, commit `bed96ad5ffc3d54d6f0edccead10ac61f688f75a`.
**Projeto:** AI Studio, PR #2, banco exclusivo 5433; sem relacionamento com FRcaixinha 2.2.

## Risco comprovado

A migração inicial 001 concede DML genérico (`INSERT/UPDATE/DELETE`)
para `frcaixinha_app_role` em `public.memberships` e `public.quotas`.
A validação RLS protege por tenant, mas **não consulta licença ativa,
limite do plano, aceite contratado e comprovante de pagamento**.
Consequentemente, um administrador válido poderia extrapolar a capacidade
sem atravessar o `/invitations/preflight/saas-capacity`, que é somente leitura.

## Proteção candidata M33900–M34300

- **M33900:** migração local candidata 046 sujeita a banco, papel e flag
  explícitos; **não aplicada no Termux**.
- **M34000:** revoga DML genérico nas tabelas de vínculos/cotas para
  `app`, `auth`, `verifier` e os usuários técnicos locais conhecidos.
- **M34100:** audita os privilégios efetivos e o FORCE RLS.
- **M34200:** gatilhos `BEFORE INSERT/UPDATE/DELETE`, com bloqueio por
  `session_user`: mesmo que uma rotina antiga `SECURITY DEFINER`
  executasse a gravação, uma sessão de aplicação receberia 42501.
- **M34300:** testes PostgreSQL descartáveis cobrem oito tipos de ataque
  (três DML em memberships, três em quotas, duas tentativas através de
  função SECURITY DEFINER). Confirmam ausência de modificações.

Essa migração não abre cadastro; ela **fecha** os caminhos de escrita
que hoje ignoram licenciamento. Proprietário local `frc_ai_owner`
continua com capacidade administrativa estritamente no banco de
desenvolvimento. Os testes CI admitem `postgres` somente nos bancos
efêmeros `frcaixinha_ci` e `frcaixinha_staging` para montar fixtures.

## Próximo bloqueio

A futura escrita legítima exigirá serviço separado, privilégios mínimos,
dados de licença/faturamento autenticados por provedor, aceite contratual,
idempotência, lock de tenant, verificação de limites dentro da mesma
transação e trilha auditável. **Até essa revisão, nenhum app/usuário real
poderá inserir, editar ou excluir vínculos/cotas.** O script de homologação
deverá permanecer no modo somente leitura e nunca executar 046 no 5433.
