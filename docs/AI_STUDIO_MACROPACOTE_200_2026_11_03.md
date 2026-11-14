# FRcaixinha AI Studio — Macropacote 200: contabilidade, fechamento e recuperação
Data: 03/11/2026. Projeto **AI Studio independente** (NÃO FRcaixinha 2.2).
Baseline: `dbec2b8eaaa3d75c8e5bee5acdd7cc289334a121`, APK 202, CI #202 6/6 PASS.
Operador confirmou 7/7 verificações Android do Macropacote 180.
PR #2 Draft; não mesclar main nem criar novos ambientes.

## Macropacote 200 — 20 verificações com gates separados
| ID | Critério | Prova / condição |
|---|---|---|
| 200-01 | Lançamentos só no tenant da sessão | SQL parametrizado + RLS de CI |
| 200-02 | Master negado antes da consulta | teste Python 403 |
| 200-03 | Membro negado antes da consulta | teste Python 403 |
| 200-04 | Administrador de outro tenant negado | teste Python 403 |
| 200-05 | Soma DR deve igualar soma CR em centavos | agregador Python |
| 200-06 | Existência de pelo menos um DR e CR | agregador Python |
| 200-07 | Entradas sem conta contábil autorizada são falhas | JOIN + filtro |
| 200-08 | Valor zero, negativo ou tipo inválido é falha | Python |
| 200-09 | Transação sem contrapartida exige revisão | Python |
| 200-10 | Mais de 500 transações bloqueia a prévia parcial | HTTP 503 |
| 200-11 | Payload diferente ou sigiloso recusado pelo cliente | parser TS |
| 200-12 | Lista vazia não equivale a razão conciliado | NO_TRANSACTIONS |
| 200-13 | Divergência impede mostrar detalhamento no APK | UI |
| 200-14 | Troca de sessão invalida resultado tardio | snapshot UI |
| 200-15 | Nenhuma prévia declara banco conciliado | API/UI false |
| 200-16 | Fechamento financeiro real continua HTTP 503 | teste Python |
| 200-17 | Eventos manuais de auditoria sem procedência são bloqueados | 403/503 sem SQL |
| 200-18 | Simulação Hamilton estável e resíduos segregados | motor puro Python |
| 200-19 | Backup cifrado/restauração descartável + RLS | job PostgreSQL CI existente |
| 200-20 | CI 6/6, APK, Termux ff-only e homologação física | PENDENTE operador |

## O que o novo painel verifica
O painel Livro-Razão do TENANT_ADMIN solicita uma prévia somente de contagens.
Se houver divergência, exceder 500 transações ou o servidor estiver indisponível,
não exibe saldos ou lançamentos como confirmados. Sem transações, comunica ausência.
Se os débitos/ créditos estiverem matematicamente equilibrados, permite consultar
as rotas existentes do tenant. Isso NÃO garante que pagamentos foram reconciliados,
que livros são completos, que cada conta está no saldo certo, nem é parecer de auditor.

## Prévia matemática de fechamento
A função Python `annual_allocation_preview` recebe exclusivamente pesos
sintéticos. Calcula 15% administrativo provisório e 85% pool de membros,
com regra de maiores restos e desempate determinístico. Se ninguém tiver peso
positivo, preserva o pool como `segregated_undistributed_cents`.
Retorna exclusivamente `PREVIEW_NOT_SETTLED`. Sem tabelas, Pix ou liquidação.
A política real de receitas, inadimplência, restituição de principal e autorização
de fechamento permanece PENDENTE de homologação específica.

## Auditoria e recuperação
O endpoint legado de inclusão manual de evento autodeclarado pelo cliente
permanece bloqueado até existir verificação de origem; isso não altera a
trilha append-only produzida por operações legítimas do backend.
A CI existente utiliza PostgreSQL descartável e faz teste de backup age e
restauração. Essa prova não substitui ensaio de restauração em infraestrutura
real nem a auditoria de unicidade dos serviços do Termux.

## Proibições
- Não criar banco, migrar base real, limpar git, reescrever histórico ou mesclar PR.
- Não habilitar Pix, empréstimos, saques, fechamento real ou distribuição.
- Não recriar Master nem usar cluster/credenciais do projeto FRcaixinha 2.2.
- Não afirmar que integridade de DR/CR significa conciliação financeira.

## Teste físico APK
1. Conferir SHA 7 caracteres, cabeçalho e rolagem.
2. Admin da caixinha: abrir Livro-Razão, verificar seção de prévia e o estado
   `NO_TRANSACTIONS`, `BALANCED` ou `REVIEW_REQUIRED` conforme banco real.
3. Master e Membro não podem consultar painel analítico da caixinha.
4. Falha de rede não pode exibir valores antigos ou fictícios.
5. Confirmar que o painel não oferece botão de liquidação ou de auditoria manual.
6. Validar login/logout e troca de perfis sem vazamentos de dados.
7. Reiniciar FastAPI após ff-only; **PostgreSQL 5433 intocado**.
8. Não criar lançamentos para forçar resultado; reportar estado realmente existente.
