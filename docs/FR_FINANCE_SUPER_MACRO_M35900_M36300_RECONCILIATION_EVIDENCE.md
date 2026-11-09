# FR Finance AI Studio — M35900–M36300 | conciliação SaaS e trilha de reversão

Base homologada: M35800 `73ea71b0f4d99d6f201284052936f71c54af671d`.

## Implementação

O banco **descartável da CI**, exclusivamente `frcaixinha_staging`, recebe a migração
`065_saas_reconciliation_review_staging_only.sql`. Ela cria um livro de
**revisões candidatas**, não uma tabela de pagamentos quitados.

A função `saas_reconciliation_review_ci`:

- exige papel PostgreSQL exclusivo e flag de execução de CI;
- bloqueia a linha da caixinha e da intenção de pagamento durante a
  verificação, sem misturar patrimônio das caixinhas com licenças SaaS;
- verifica vínculo entre tenant, pagamento, identificador do provedor e
  modo de teste; status desconhecido é negado;
- mantém uma chave de requisição única e unicidade do digest da evidência
  por pagamento/tipo. Replay idêntico retorna o mesmo estado sem gravação;
  colisão divergente e evidência repetida são rejeitadas;
- registra candidatos `GET_MATCH_CANDIDATE`, suspensões `REVERSAL_HOLD`
  e indisponibilidade do provedor `PROVIDER_UNAVAILABLE_HOLD`;
- rejeita novo candidato de aprovação após uma reversão, impedindo que
  uma consulta antiga sobreponha o bloqueio;
- usa gatilhos para recusar `UPDATE`, `DELETE` e `TRUNCATE` na trilha;
- retorna sempre `activation_authorized=false`.

Nenhuma tabela de pagamentos, licenças, usuários, membros, cotas, Pix,
webhooks ou razão é alterada. Mesmo na simulação positiva, não existe
liquidação, atribuição de acesso ou promessa de saldo.

## Ensaios de segurança

PostgreSQL CI simula duas tentativas concorrentes com a mesma evidência:
uma única gravação candidata é aceita. Testa replay, colisão, estorno
posterior, indisponibilidade, imutabilidade, papel indevido e bloqueio de
escrita por `frcaixinha_app_role`. Também compara contagens das tabelas
reais antes/depois, exigindo nenhuma mudança.

O digest SHA-256 e os valores inseridos na CI são **sintéticos**; não
provam origem no Mercado Pago, existência de pagamento bancário,
webhook verdadeiro nem revisão independente. A trilha não é uma
implementação de reconciliação autorizada em produção.

## Pendências verdadeiramente operacionais

OCI VM/HTTPS/DNS/Vault, credencial de conta da plataforma vinculada e
segregada, confirmação efetiva pelo Mercado Pago, readback em execução
com ambiente comercial autorizado, prova do extrato/recebimento,
revisão independente, custódia e retenção de evidências, ensaios de
backup e revogação em staging OCI. Essas provas precisam de
infraestrutura real e não se tornam verdes com mais testes sintéticos.

Migrations locais no PostgreSQL 5433: **nenhuma executada**.
Pix real, cobrança e ativação de usuários: **OFF**.
