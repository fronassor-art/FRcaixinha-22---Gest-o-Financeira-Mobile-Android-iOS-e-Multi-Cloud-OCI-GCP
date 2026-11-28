# Pacote 15 — Integridade Price e Checkpoint Android 180

Baseline 0753525cb3934d6aa3da1caca95d198e4df65bd7;
PR #2 Draft, branch atualizacao-ai-studio-9b46a63187.

- Interface aceita somente resposta de simulação Price com principal e
  prazo solicitados, parcelas mensais dia 10 e somatórios íntegros.
- Cada parcela concilia abertura, juros, amortização, pagamento e
  saldo final; última parcela zera saldo e preserva ajuste de centavos.
- Dados sensíveis inesperados são rejeitados. Não são feitos cálculos
  autoritativos nem alterações na taxa/política ACTIVE do FastAPI.
- Cliente rejeita principal com fração de centavo, valor/prazo inválido.
- Formulário impede resposta tardia de consulta anterior após alteração
  de principal, prazo, tenant, usuário ou nova simulação.
- CI inclui regressões adversariais com valores sintéticos de
  R$ 500,00, 20% a.m., 5 parcelas, total R$ 835,96.
- Sem operações financeiras reais, migrations, GRANT, alteração de
  assinatura/app ID ou merge na main.
- Após CI 6/6 e sincronização, checkpoint manual APK 180 para três
  perfis, sessões, governança, contribuições e simulação Price.
