# FR Caixinha AI Studio — M20600, correção do mínimo de contribuição

- Comprovado no GitHub: o valor R$100 veio de DEFAULT 100 da migração histórica 001 (tabelas policies e quotas) e do bootstrap de homologação de 2027 (`aistudio_homologation_cycle.py`).
- Regra aprovada: cada **TENANT_ADMIN** estabelece valor para o ciclo de sua caixinha, **mínimo de R$150,00 por cota**. R$150 é o piso, não um preço único. Membro não escolhe valor individual fora da política.
- M20600 protege UI e FastAPI contra **novas requisições** abaixo do piso; mostra o histórico legado abaixo do mínimo e a revisão de R$150 PENDING_REVIEW.
- O bootstrap antigo fica bloqueado para criar ciclo/política nova com R$100. Não recriar ciclos via esse script.
- A infraestrutura de banco ainda exige migração incremental posterior para remover DEFAULT 100 e aplicar o piso no PostgreSQL; **não afirmar que ela foi aplicada**.
- As 12 competências históricas de 2027 a R$100 **não foram reprecificadas**. Corrigir obrigações emitidas exige revisão auditada específica, aprovação e testes; nenhum Pix, quitação, ledger ou dinheiro real.
- A criação de novos ciclos pelo administrador com valor explícito permanece trabalho obrigatório futuro. Não confundir este bloqueio preventivo com implementação integral da abertura.
