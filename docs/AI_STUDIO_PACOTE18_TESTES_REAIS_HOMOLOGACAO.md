# Pacote 18 — Testes reais e persistentes da plataforma AI Studio Mobile

Baseline b6d980b6362218515de2751df02c88dce0dacf05. PR #2 Draft.
Diretriz do proprietário: todas as funções devem ter testes funcionais
reais na plataforma durante a implementação, mas sem dinheiro real.

## Parte 1: Price com banco real descartável
O CI insere ciclo e política em tabelas reais PostgreSQL, com RLS
e perfis Master/Admin/Membro. A simulação tem que retornar os números
exatos de R$ 500 em 5 prestações a 20% a.m. (total R$ 835,96).
O Master é proibido; outra caixinha sem ciclo é bloqueada.
Nenhuma chamada pode criar empréstimos nem escrituração monetária.

## Parte 2: Caixinha inaugural do próprio banco Termux
O utilitário backend/scripts/aistudio_homologation_cycle.py opera APENAS
no cluster PostgreSQL 18 do AI Studio, banco frcaixinha_aistudio_dev,
porta 5433 e caixinha inaugural com Master vinculado tanto como
TENANT_ADMIN quanto TENANT_MEMBER. Nunca cria Master novo.
--plan confirma os dados e faz ROLLBACK sem alterações.
--apply exige frase de confirmação antes de inserir ciclo/política.
A operação é transacional e idempotente; dados divergentes bloqueiam.

Parâmetros sintéticos de teste do esquema AI Studio, não aprovados
como política comercial final: ano 2027, 01/01 a 31/12,
liquidação 10/01/2028, juros 20% a.m., até 6 parcelas,
contribuição por cota R$ 100, multa R$ 10, mora 0,006667 por dia,
distribuição 15% administrador / 85% membros.

## Arquitetura de testes futuros
Preparar testes funcionais reais de cotas, contribuições, empréstimos,
conciliação sintética, fechamento anual, licenças SaaS, convites,
governança e isolamento por perfis. Usar contas/obrigações e eventos
persistidos em ambiente privado, com trilha e verificação pelo backend.
Mercado Pago deve ser integrado via OAuth autorizado por tenant e,
primeiro, sandbox/credenciais de teste. Dados e dinheiro reais continuam
bloqueados até validação técnica, contratual, regulatória e do provedor.

Nenhuma migration de produção, conta Mercado Pago, Pix, saldo real,
empréstimo efetivo, mudança de Master ou merge para main neste pacote.
