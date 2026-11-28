# FRcaixinha AI Studio — Macropacote 180
Data: 03/11/2026. Escopo: simulações Price, auditoria de centavos e consentimentos puros.
É o projeto AI Studio, NÃO o FRcaixinha 2.2 independente.

## Checkpoint
- Baseline: 341246022e1bcdbbc0d13e7c9530397560ae6bb9 (APK 200)
- GitHub Actions #200 6/6 PASS, usuário informou seis verificações Android PASS
- PR #2 Draft; sem merge; um único backend FastAPI e PostgreSQL AI Studio 5433
- Sem migrações locais, sem dinheiro real, sem segunda conta Master

## 20 verificações
| ID | Critério | Evidência |
|---|---|---|
| 180-01 | Price com Decimal | solver Python |
| 180-02 | 500 BRL, 5x, 20%, total 835,96 BRL | solver + parser |
| 180-03 | Juros 335,96 BRL reconciliam com parcelas | Python + TS |
| 180-04 | Última prestação 167,20 BRL, ajuste de centavos | Python + TS |
| 180-05 | Amortização total = principal; saldo final zero | Python + TS |
| 180-06 | Vencimento das parcelas dia 10 | Python |
| 180-07 | Primeiro intervalo irregular, dias/30 | Python + TS |
| 180-08 | Primeiro vencimento só no mês seguinte | Python |
| 180-09 | Ciclo financeiro limita última prestação | Python |
| 180-10 | Taxa vem exclusivamente da política ACTIVE | backend |
| 180-11 | Taxa arbitrária enviada pelo cliente é recusada | CI preexistente |
| 180-12 | Prazo ativo da política validado | backend |
| 180-13 | Principal 0,01 a 50000 BRL e prazo 1 a 6 | solver + backend |
| 180-14 | Simulação só lê PostgreSQL, sem INSERT/UPDATE | CI com mocks |
| 180-15 | Master e outro tenant negados antes de SELECT | backend |
| 180-16 | Payload extra, identificadores ou valores incoerentes recusados | TS |
| 180-17 | Sessão anterior não restaura dados na tela | frontend snapshot |
| 180-18 | Consentimento anual exige unanimidade e revogação prevalece em empate | Python |
| 180-19 | Desembolso, baixa e quitação reais bloqueados | backend |
| 180-20 | GitHub CI, APK assinado, ff-only Termux, homologação física | pendente |

## Escopo e bloqueios obrigatórios
Não criar bancos, registros de pagamento, contratos, usuários, migrações ou
identidades humanas. Não movimentar Pix, desembolsar, reconciliar, aprovar
crédito real ou encerrar ciclo. Testes usam dados sintéticos e funções puras.
As rotas antigas de pedido/aprovação em ambiente de homologação NÃO
autorizam operação real, e requerem revisão contratual independente.

O avaliador de consentimento anual NÃO persiste votos, não substitui assinatura
anual versionada, não cria permissão e não torna elegível qualquer empréstimo.
Mesmo que o avaliador puro retorne autorizado, a integração persistente
permanece bloqueada.

## Homologação Android
Instalar nova versão sobre APK 200 e conferir hash de sete caracteres.
Logar com Membro e Administrador e simular R$500 em cinco parcelas apenas
se ciclo ABERTO e política ACTIVE existirem no PostgreSQL.
Com taxa 20% e parcelas regulares, o total esperado é R$835,96; se a taxa
ou política for diferente, o resultado deve seguir o banco.
Ausência de ciclo/política resulta em bloqueio explícito, sem valor fictício.
Master não pode visualizar dados financeiros.
Modo offline deve negar consulta ou mostrar erro sem dados de outro perfil.
Não fazer pedido/aprovação/desembolso e não usar dinheiro real.
