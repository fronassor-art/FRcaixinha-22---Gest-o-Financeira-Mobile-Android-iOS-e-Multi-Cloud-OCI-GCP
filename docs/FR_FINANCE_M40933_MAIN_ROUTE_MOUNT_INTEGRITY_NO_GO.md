# FR Finance M40933 — integridade do registro de rotas Master no FastAPI (NO-GO)

Extensão **estática e fail-closed** do M40931, somente GitHub. O M40931 já estava aprovado em CI e enumerou seis operações POST no namespace Master, três sempre negadas pelo M40930, duas de pré-análise e uma break-glass contratualmente proibida.

## Lacuna fechada

Um teste que examine apenas arquivos em `backend/app/routers` pode deixar de perceber que o `backend/app/main.py` registra uma rota ou um roteador por caminho não revisado. O M40933 torna obrigatória a revisão do ponto central da aplicação:

- Requer que `master.router`, `_saas_promotions.master_router`, `_exclusive_cashboxes.master_router` e `_review_policy_gaps.master_router` estejam registrados exatamente uma vez, com prefixo `settings.API_V1_STR`;
- Falha ao encontrar inclusão duplicada, remoção de roteador Master ou mudança inesperada de prefixo;
- Rejeita qualquer registro direto de `app.post`, `app.put`, `app.patch`, `app.delete`, `app.route`, `app.api_route` ou `app.add_api_route` em `main.py` até revisão;
- Exercita cenários negativos: rota Master POST sintética e remoção de `_saas_promotions.master_router` são obrigatoriamente reprovadas;
- O workflow M40931 passa a disparar também em modificações de `backend/app/main.py`.

O controle é análise AST, sem importar FastAPI, iniciar servidores, consultar banco ou invocar provedor. Isso **não** detecta todos os registros dinâmicos, monkeypatching, funções SQL de privilégio elevado ou um atacante com credenciais PostgreSQL. Mudanças de roteamento em outros arquivos exigem revisão própria. O M40933 não estabelece custódia independente de comandos Master e não remedia o GUC spoof M40570 nem o emissor legado M40730.

Próximo bloqueio P0: resolver privilégios SQL e `SECURITY DEFINER` com autenticação independente do PostgreSQL (issuer/guardian de identidades operacionais segregadas), provas adversariais no PG18 descartável e só depois homologação em staging. Não criar migrations nem tocar o banco original até plano reversível, aprovações e backups.

**GitHub-only;** `ORIGINAL_PG_CONNECTIONS=NONE`, `MIGRATIONS=NONE`, `RESTARTS=NONE`, `TERMUX_SYNC=NONE`, `PIX_REAL=OFF`, `PAGAMENTOS_REAIS=OFF`, `ATIVACAO_REAL=OFF`, `M40840=BLOCKED`, `PRODUCTION=NO-GO`.
