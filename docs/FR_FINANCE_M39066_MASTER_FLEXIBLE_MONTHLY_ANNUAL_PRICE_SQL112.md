# FR Finance M39066 — Master: preços mensal e anual livres e independentes

## Pedido e estado

- O APK M39065 foi atualizado e a autenticação local passou `TEST_MODE` e
  `READY_FOR_TEST_AUTH`. Capturas do Android mostram as áreas reais de
  TENANT_ADMIN e MASTER, a tela de licenças e valores históricos do catálogo.
- Na migração base 011, `annual_price` era GENERATED ALWAYS AS
  `monthly_price * 10`. Mesmo o Master não conseguia editar a anuidade.
- O usuário decidiu que preços mensal/anual de assinatura SaaS são
  **independentes**, editáveis pelo dono da plataforma; promoções mensais e
  anuais serão igualmente livres, em fase comercial separada.
- A contribuição de cada membro (mínimo **R$ 150/cota/ciclo**, decidida pelo
  TENANT_ADMIN) é diferente das assinaturas da plataforma e não foi alterada.

## SQL112 — migração incremental, SEM RECÁLCULO HISTÓRICO

`backend/migrations/112_frfinance_master_independent_saas_prices.sql`:

1. Só aceita o `frcaixinha_aistudio_dev` de `127.0.0.1:5433`,
   `frc_ai_owner` e PGDATA nativo PostgreSQL 18.
2. Confirma o tipo gerado legado da coluna anual.
3. `ALTER COLUMN annual_price DROP EXPRESSION`: os anuais históricos já
   armazenados continuam intactos; novas versões recebem preços explícitos.
4. Mantém RLS e FORCE RLS; libera ao papel app SOMENTE INSERT da coluna anual,
   preservando a política Master pré-existente e sem UPDATE/DELETE de versões.
5. Preserva as FK de `saas_subscription_preparations.price_version_id`.
   Contratos, cobranças e licenças não são alterados.
6. Catalogada sob `migrations:112` com SHA Git blob imutável. Não repetir
   as migrações 011, 110 ou 111.

## Fluxo de edição após migração e nova API

- `GET /api/v1/master/licenses` lê preços vigentes e os UUIDs das versões
  de Essencial e Intermediário.
- O Master edita mensalidade, anuidade e justificativa em separado.
- `POST /api/v1/master/license-prices` exige preços positivos até centavos,
  `expected_version_id`, motivo longo e sessão MASTER validada.
- Lock transacional por plano + comparação do UUID evita edição concorrente
  desatualizada; histórico novo é **INSERT** e gera `audit_events`.
- Se o banco não recebeu SQL112, a escrita devolve HTTP 503, sem preço
  parcialmente persistido. Perfil não Master recebe autorização negada.
- Plano AMPLIADO continua bloqueado; nenhum preço demonstrativo é divulgado
  como preço ativo.
- Leitura de ofertas congeladas usa a anuidade real da versão registrada,
  sem impor o antigo fator 10×.

## Execução no Termux Nativo — SOMENTE após CI e sincronização exata

Pré-requisitos: servidor original PostgreSQL 18.6 já online na porta 5433,
repositório original `$HOME/fr-finance` na branch
`atualizacao-ai-studio-9b46a63187`, worktree limpo, SHA aprovado
e senha `frc_ai_owner` digitada no prompt oculto. Não usar o Debian e
não tocar no PostgreSQL FR 2.2 da porta 5432.

1. Sincronizar GitHub com `git fetch --no-tags`, comparar FETCH_HEAD com
   o SHA aprovado e executar `git merge --ff-only FETCH_HEAD`, sem reset.
2. Conferir testes e o inventário versionado `repo-check`.
3. `AI_STUDIO_APPROVED_SHA="$SHA" python3 -B -m backend.scripts.frfinance_m39066_master_prices_sql112_termux --inspect`
   retorna `LEGACY_10X_GENERATED_READY_FOR_SQL112` se ainda falta aplicar
   ou `SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT` se já aplicado.
4. Somente com a inspeção aprovada, o operador executa
   `AI_STUDIO_APPROVED_SHA="$SHA" python3 -B -m backend.scripts.frfinance_m39066_master_prices_sql112_termux --apply`.
   O instalador solicita confirmação literal **APLICAR_SQL112_FR_FINANCE**.
5. Antes de qualquer SQL, cria backup privado `pg_dump` PG18 custom
   no Termux e verifica `pg_restore --list`. **A restauração não foi
   ensaiada nesta etapa** (não se cria outro banco). O backup é preservado.
6. Aplica apenas SQL112 em uma transação; verifica o novo schema, grants
   e os valores positivos. Em caso de falha DDL, transação é revertida.
7. `PASS_APPLIED_WITH_POSTCHECK` é a única prova local de alteração;
   testes GitHub não significam SQL aplicado no aparelho.
8. Após a aplicação, realizar reinicialização MANUAL controlada da
   FastAPI original já identificada, somente na sessão correta, para
   recarregar os novos módulos e evitar statement caches antigos.
   Preservar o `api.env` privado e as flags de Pix/Brevo/ativação OFF.
9. O APK existente não recebe automaticamente novas telas. Usar nova
   compilação Android assinada e verificada com o mesmo package/certificado
   antes de testar o formulário de preços.

## Delimitação de promoções

O catálogo de versões de preços é base para futuras campanhas de desconto
separadas por periodicidade e destinatário (admin contratante). Campanhas,
cupom, notificação externa e cobrança por provedor **NÃO** são ativadas
por SQL112 nem pela API de preços. Criar publicação/versionamento de
promoções e vínculo a oferta assinada somente após outro circuito de
auditoria contratual.

## Status e segurança

O trabalho é exclusivo do FR Finance AI Studio. Nunca alterar bancos da
FR Caixinha 2.2, usuários reais, senhas, saldo, Pix, taxas de empréstimo,
cotas dos membros, serviços OCI ou produção como efeito colateral.
