# FR Finance — M40330: matriz RLS com registros sintéticos em duas caixinhas

## Checkpoint de origem

M40320 foi executado no Termux nativo, com o Debian existente e o PostgreSQL
original de FR Finance (127.0.0.1:5433), no commit 597327c. Retorno reportado:
36/36 SELECT COUNT negativos sob a função real \`frc_ai_app\`, quatro contextos
fictícios negativos, sem alterações locais. Identidades efetivamente
autenticadas ainda **não** foram avaliadas.

## Escopo M40330

Reutilizar a migração SQL110+111, o esquema mínimo e a fixture M39020 existentes
no **PostgreSQL 18 descartável do GitHub Actions**, banco \`frfinance_ci_credit\`
na porta 5432. A etapa M40330 insere dados fictícios para **duas caixinhas**
em uma transação que obrigatoriamente termina em ROLLBACK.

São dez contextos testados contra seis tabelas de crédito especial:

- Administrador A e administrador B: visibilidade positiva das seis tabelas
  de sua própria caixinha e negativa para a outra.
- Membro A e membro B: visibilidade positiva de concessão, campanha publicada,
  destinatário e preferência próprios; acesso zero à outbox/auditoria e à
  caixinha alheia.
- Administradores A/B e membros A/B reivindicando falsamente a outra caixinha:
  nenhum dado visível.
- Papel Master sem caixinha e Master reivindicando caixinha A:
  nenhum dado patrimonial visível.

A matriz calcula **60 verificações de visibilidade própria**, além de 60
checagens de caixinha oposta. O teste falha se uma leitura autorizada retornar
zero ou uma leitura proibida retornar linhas. Confere também o \`frc_ai_app\`,
FORCE RLS, a ausência de privilégios de contorno implícitos, a limpeza dos
SET LOCAL e o descarte integral de registros ao final do ROLLBACK.

## Limites da evidência

Registros e papéis do teste existem apenas na CI e não correspondem a contas
reais do aplicativo. Os contextos de papel e tenant são atribuídos pelo teste
e **não passam pela validação de tokens/sessões do FastAPI**. Portanto, mesmo
com o resultado verde, \`AUTHENTICATED_BEARER_ISOLATION=NOT_TESTED\`.

O próximo teste deverá integrar tokens de sessões sintéticas efetivamente
emitidos e validados pela API com o acesso às seis tabelas, também em banco
descartável. Nenhuma credencial real, sessão de usuário ou dado de cliente
deve ser transportado para a CI.

## Regras de segurança

- Proibido executar \`m40330_two_tenant_rls_matrix_disposable_ci.sql\` no Termux,
  Debian do telefone, PostgreSQL 5433, FR Caixinha 2.2 ou OCI.
- A própria SQL recusa banco, porta, papel ou gate de CI divergentes.
- SQL110/111 são aplicadas **apenas no runner descartável**, não no banco original.
- Fora da CI, o M40320 permanece o último checkpoint local aprovado.
- \`PIX_REAL=OFF\`; \`PAGAMENTOS_REAIS=OFF\`; \`ATIVACAO_REAL=OFF\`;
  \`PRODUCTION=BLOCKED\`; PR #2 permanece Draft.
