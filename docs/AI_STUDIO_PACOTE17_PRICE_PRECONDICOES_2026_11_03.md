# FRcaixinha AI Studio — Pacote 17: diagnóstico seguro da simulação Price

Baseline: 3085256b5692856c71ab7dceda81368d285ae6d6.
PR #2 Draft, branch atualizacao-ai-studio-9b46a63187.

## Evidência no APK 180
- Simulação real pelo membro retornou "Simulação indisponível no FastAPI".
- A captura comprova que não foi apresentado resultado, embora HEALTH,
  DATABASE e AUTH retornem 200 e Master sem sessão retorne 401.
- Status de homologação do cálculo no celular permanece PENDENTE/FAIL.
- Em src/components/ServerLoansView.tsx, todo erro era ocultado no catch.

## Implementação
- FinancialApiHttpError carrega status HTTP explícito, preservando filtro
  de mensagens recebido do servidor; não muda autenticação nem RLS.
- UI apresenta bloqueio específico para HTTP 409 (ciclo ABERTO ou política
  ACTIVE faltante), 422 (calendário, prazo ou valor), sessão, rede e
  resposta inválida; mensagens desconhecidas nunca são exibidas.
- Script de preflight do banco AI Studio apenas SELECT dentro de
  BEGIN READ ONLY / ROLLBACK, com validação de porta 5433, nome do banco,
  proprietário e diretório do cluster PostgreSQL 18 exclusivo.
- Sem criação ou ativação automática de ciclo e política, sem alterar
  juros, limite de 6 parcelas, registros, transações ou credenciais.
- Testes com falhas 409/422 simuladas e nenhuma tentativa automática
  de repetir ou gravar empréstimo.

## Ação necessária após sincronização
Executar no Termux: bash backend/scripts/aistudio_price_diagnose_readonly.sh
e informar somente os rótulos e números agregados. Caso os contadores
indiquem falta de ciclo ou política, propor configuração de homologação
para aprovação explícita, sem ativar operações financeiras reais.

## Limite do diagnóstico
Contadores agregados podem mostrar ciclo/política de OUTRA caixinha;
não comprovam vínculo com a caixinha da sessão. Para afirmar que
uma caixinha específica está apta, é necessário diagnóstico
parametrizado e autorizado de seu tenant, sem expor dados de membros.
