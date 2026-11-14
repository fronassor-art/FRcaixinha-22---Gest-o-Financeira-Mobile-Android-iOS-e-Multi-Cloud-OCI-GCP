# M22400 — Revisão auditada de contribuições históricas R$100

O banco local tem histórico de 12 competências de R$100, enquanto a nova política de cota exige pelo menos R$150 para novas contribuições. Não é lícito trocar retroativamente sem avaliar contrato e pagamentos anteriores.

M22400 cria GET /api/v1/tenants/{tenant_id}/cycle-contribution-price/legacy-review/{cycle_id}, exclusivamente para o administrador da própria caixinha, com sessão validada e PostgreSQL RLS. A resposta agrega apenas valores e contagens, sem nomes, CPFs, tokens ou identidades dos membros.

A API:
- lê contribuições históricas com valor abaixo de R$150; não edita obrigações;
- apresenta valores devidos, pagamentos CADASTRADOS e saldo cadastral sem dizer que são conciliados;
- detecta centavos inválidos, estados desconhecidos e excesso de grupos;
- obriga revisão do administrador e mantém price_adjustment_authorized=false;
- não autoriza cancelamentos, novos pagamentos, Livro-Razão, fechamento ou dinheiro real.

Essa é uma etapa concreta de verificação, mas a regularização administrativa das competências históricas continua pendente de política aprovada, autorização e prova de banco.
