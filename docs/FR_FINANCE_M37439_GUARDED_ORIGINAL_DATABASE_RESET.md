# FR Finance M37439 — aplicação excepcional autorizada no mesmo PostgreSQL

A autorização explícita do responsável cobre apenas o saneamento de
registros sintéticos de 2027, inclusive a única revisão de preço
append-only. Não cobre dados de usuários reais nem transações financeiras.

A migração candidata M37437 foi ensaiada no PostgreSQL 18 descartável
do GitHub (M37438), dentro de transação com rollback obrigatório.
O original está protegido por backup cifrado M37431, recuperado com
sucesso no ensaio completo M37432. Nem o ensaio nem o código do GitHub
alteram a base do Termux.

O aplicador M37439 em modo preflight só consulta a base original
frcaixinha_aistudio_dev na porta 5433. Em modo apply exige
FR_FINANCE_M37439_ENABLE_APPLY=YES, SHA de commit homologado,
confirmação de duas frases, ausência de FastAPI e de outras
conexões ao PostgreSQL, conferência de contagens exatas e
releitura do backup cifrado com age.

A candidata executa uma única transação, remove estritamente 12
contribuições não pagas, uma cota, uma política, uma revisão de
preço sintética e o ciclo antigo. O trigger imutável da auditoria
é excepcionalmente suspenso e reativado dentro da mesma transação.
Se qualquer operação ou pós-condição falhar antes do COMMIT,
o PostgreSQL reverte a transação. O backup original guarda a
evidência antiga e um novo evento geral documenta a exceção.

Os usuários, a caixinha, os dois vínculos e as sessões continuam.
Nenhum segundo banco será criado e nenhum valor fixo será imposto
aos novos ciclos. A escolha do valor permanece exclusiva do
administrador, com mínimo contratual de R$ 150 por cota.

Só executar após CI integral 6/6 PASS para o commit que introduz
o aplicador. Pix real e ativação de usuários reais permanecem OFF.
