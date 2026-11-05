# FR Caixinha AI Studio — M20700, correção PostgreSQL do piso de R$150

- O antigo M001 define DEFAULT R$100, e o script de homologação criou o ciclo 2027 dessa forma. Essa origem foi confirmada no M20600.
- M043 remove os dois defaults antigos e exige R$150 ou mais para inserções e atualizações de políticas/cotas. O valor é **configurável pelo administrador de cada caixinha**, não igual para todos.
- As constraints são NOT VALID intencionalmente: registros antigos R$100 ainda existem para revisão. O M043 mantém 45 tabelas, não reexecuta 001–042, não reprecifica as 12 competências, não altera auditoria M042, não gera Pix e não muda o ledger.
- A função antiga M042 é renomeada e privada; a função autorizada exige R$150 e delega autenticação e idempotência à rotina original.
- A CI testa o mínimo em PG16 e PG18 descartáveis; o banco Termux **não é alterado pela CI**.
- Aplicação local do M043 exige auditoria, backup AGE recuperável e confirmação explícita do operador no script `backend/scripts/aistudio_cycle_price_043.sh`. Não aplicar antes de 6/6 PASS.
- Ainda pendentes: abertura de ciclo com escolha explícita na interface; plano de correção das 12 competências legadas e aprovação de regularização financeira. Nenhum pagamento real ou fechamento autorizado.
