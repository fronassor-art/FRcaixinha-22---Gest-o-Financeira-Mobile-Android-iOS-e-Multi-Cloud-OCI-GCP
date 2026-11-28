# M21100: instalador local PostgreSQL 044

Foi criado o script M21100, com audit, apply e verify. O apply exige commit exato, banco frcaixinha_aistudio_dev, PG18 na porta 5433, papel frc_ai_owner, 45 tabelas e M043 validada. Cria backup AGE com prova de recuperação antes de executar somente a 044 numa transação.

O operador não aplicou 044 até o checkpoint anterior. A migração 044 acrescenta uma tabela de auditoria, total 46, sem modificar competências 2027 nem movimentar dinheiro. A abertura efetiva não está habilitada no Android e exige integração posterior da rota com sessão autenticada e testes.
