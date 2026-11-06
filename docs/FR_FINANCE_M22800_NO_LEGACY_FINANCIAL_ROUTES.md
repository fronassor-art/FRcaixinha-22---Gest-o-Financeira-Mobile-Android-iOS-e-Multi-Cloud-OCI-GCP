# M22800 — Remoção de caminhos financeiros mortos nas rotas públicas

Embora os endpoints POST /contributions/{id}/pay e POST /closings já estivessem bloqueados por HTTP 503, ambos continham centenas de linhas de operação LEGADA depois de um raise incondicional. Essa situação poderia levar a remoção acidental da guarda e execução de falso QR Pix ou fechamento sem conciliação.

Este pacote exclui o código inalcançável desses dois endpoints, mantendo a autorização original e a resposta 503 em funções pequenas e testáveis. O cálculo de capital-dias e os oráculos financeiros de simulação permanecem separados e disponíveis para testes, mas NÃO liquidam dinheiro nem criam recibos.

A futura operação financeira não será habilitada retirando uma linha de bloqueio. Exigirá um novo serviço transacional com OAuth por tenant, Orders autenticado, extrato independente, idempotência, RLS, livro-razão balanceado e testes E2E OCI.

M22800 não altera migrações, Termux, banco, token Mercado Pago, OCI ou operações reais.
