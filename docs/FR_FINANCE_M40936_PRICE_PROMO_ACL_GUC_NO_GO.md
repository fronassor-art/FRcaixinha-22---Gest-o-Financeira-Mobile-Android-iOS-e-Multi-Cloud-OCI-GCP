# FR Finance M40936 — revogação de ACL de preços e campanhas SaaS no PostgreSQL 18 descartável (NO-GO)

**Escopo exclusivamente GitHub Actions**, sem alteração no PostgreSQL original, no FR Caixinha 2.2, no Termux, nos recursos do OCI nem no Mercado Pago. Este pacote não é uma migration e não deve ser aplicado por script ao banco do telefone ou a qualquer produção.

## Problema objetivo encontrado

- **SQL011** concedia `INSERT(plan_tier,monthly_price,changed_by,reason)` para `frcaixinha_app_role` nas versões de preços.
- **SQL112** acrescentou `GRANT INSERT (annual_price)` na mesma tabela.
- **SQL113** concedia `INSERT` por colunas nas revisões de campanhas SaaS e acesso por função `SECURITY DEFINER`.
- As políticas de preços e promoções verificavam `app.current_role` e `app.current_user_id` (GUCs de sessão falsificáveis por credenciais SQL da aplicação, demonstrado por M40570). O Master SQL de aplicação compartilhado não autentica a origem dessas variáveis.

O M40930 responde HTTP 503 nas três rotas mutáveis Master, e M40932 marca transações de consulta Master como READ ONLY. Isso protege o caminho HTTP conhecido, mas **não revoga privilégios de uma conexão SQL direta roubada**.

## Ensaio M40936

O runner `backend/tests/m40936_price_promo_acl_rehearsal_disposable.py` reusa M40560/M40900 e somente se conecta a um PostgreSQL **18 efêmero**, com identidade `postgresql://postgres:…@127.0.0.1:55433/fr_m39067_disposable_ci`, flags CI e pagamentos reais OFF. A credencial de CI é fictícia e confinada ao serviço efêmero.

1. Carrega apenas fixtures e registros sintéticos de SQL112/SQL113. Restabelece **em memória da instância descartável** a concessão SQL011 e a política de RLS da tabela de preços que o fixture M40560 havia simplificado.
2. Simula uma role membro, que inicialmente não deve inserir preços. Falsifica as GUCs `MASTER` e `current_user_id` usando a **mesma role de aplicativo**, e registra a possibilidade anterior de inserir **uma versão de preço e um rascunho de campanha sintéticos** sem aprovação HTTP.
3. Com o proprietário sintético, revoga todas as concessões de `INSERT` por coluna e tabela das versões de preços; reusa a revogação M40900 para escrita, SELECT de campanhas e execução de função comercial. Confere `has_table_privilege` e `has_column_privilege` para **cada coluna concedida**.
4. Falsifica novamente as GUCs e exige erro PostgreSQL **42501** ao tentar uma nova inserção de preço e de campanha. Verifica que o SELECT do catálogo de preços permanece possível e que as linhas sintéticas anteriores não foram apagadas.
5. **Prova negativa preservada:** a role ainda consegue alterar a GUC e realizar leitura de preços como Master — portanto a autenticação SQL e RLS continuam vulneráveis, e a medida é **apenas contenção das escritas diretas**.

M40936 reusa o ensaio M40900 e o expande ao conjunto **SQL011 + SQL112 + SQL113**. A revogação de leitura e de execução da antiga função de promoções afetaria os endpoints legados de consulta. Por isso **não há aplicação automática** e a substituição por fronteira de leitura autenticada independente é pré-requisito.

## Exigências para um futuro desenho aceito

- Custódia independente, não forjável por um detentor do DSN app, autenticação de sessão e autorização de escrita vinculadas ao conteúdo da ação e a aprovação auditável.
- Identidades SQL segregadas de app, emissor e guardian, sem compartilhamento de segredo/UID como única prova, com permissões por função e princípio de mínimo privilégio.
- Prova em PostgreSQL descartável de sessão revogada, replay, concorrência, injeção SQL e roubo combinado de credenciais; M40730, M40928 e M40929 permanecem NO-GO até revisão independente.
- Testes de compatibilidade da API real, planejamento reversível, staging, aprovação específica e backup conferido antes de **qualquer** mudança no banco original. M40840 não será retirado com base só nesta evidência.

**Invariantes:** `MIGRATIONS=NONE`; `ORIGINAL_PG_READS_WRITES=NONE`; `TERMUX_SYNC=NONE`; `SERVICE_RESTARTS=NONE`; `PIX_REAL=OFF`; `PAGAMENTOS_REAIS=OFF`; `ATIVACAO_REAL=OFF`; `M40840=BLOCKED`; `M40930_MASTER_WRITES=HTTP_503`; `PRODUCTION=BLOCKED`; `NO-GO`.
