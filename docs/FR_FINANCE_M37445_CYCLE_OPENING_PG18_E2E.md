# FR Finance M37445 — ensaio funcional da abertura no PostgreSQL 18 descartável

Depois do M37444 Termux PASS (20 testes), o schema do PostgreSQL original
está pronto, sem ciclos antigos. M37445 valida o fluxo **real da função SQL**
`cycle_open_create` exclusivamente no PostgreSQL 18 descartável do GitHub,
com três caixinhas e sessões sintéticas diferentes e preços selecionados
expressamente por administradores: R$ 150,00, R$ 200,00 e R$ 325,00.

Em uma única transação de CI com ROLLBACK, exercita a criação, recibos,
replay idempotente, conflitos de chaves, rejeição de R$ 100 e R$ 149,99,
membro sem privilégios, sessão inválida, cruzamento de tenant, segundo
ciclo aberto e imutabilidade da trilha de abertura. Confirma que a abertura
não gera cotas, contribuições, Pix, lançamentos no Livro-Razão ou empréstimos.

O teste tem guarda explícita para `frcaixinha_ci`, porta 5432, usuário
postgres, sinalizador de CI e PG18. ROLLBACK obrigatório; após a execução
o workflow exige que todos os usuários/ciclos/auditorias criados no teste
tenham desaparecido.

Nenhuma escrita, login, migração ou abertura de ciclo é feita no Termux.
O banco `frcaixinha_aistudio_dev` permanece o único banco local.

Próximo passo depois do 6/6 PASS: sincronizar o commit na branch original,
executar a suíte estática no Termux e revalidar o banco original somente
com M37444. Testes operacionais do administrador com sessão legítima,
valores reais e persistência requerem autorização e procedimento separados.
