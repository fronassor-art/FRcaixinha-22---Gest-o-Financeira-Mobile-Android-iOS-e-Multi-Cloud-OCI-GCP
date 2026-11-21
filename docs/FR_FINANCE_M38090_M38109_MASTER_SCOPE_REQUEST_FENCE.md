# FR Finance AI Studio — M38090–M38109 | Pré-análise Master isolada por sessão e caixinha

Checkpoint de origem: M38089, commit f663ed3. Termux: 1.286 testes Python e TypeScript 6 compatíveis PASS. GitHub: workflow de validação geral do commit f663ed3 concluído com sucesso.

## Falha corrigida
A tela `MasterOnboardingView` tinha dois fluxos assíncronos de pré-análise. A resposta de `simulateMasterOnboarding` era exibida incondicionalmente com `setPreflight(check)`. Uma operação iniciada por um perfil Master numa caixinha podia finalizar após alteração do formulário, troca de identidade ou logout. O resultado antigo podia reaparecer visualmente em outro contexto, apesar de não permitir criação de conta.

## Implementação
- M38090–M38094: `createMasterOnboardingFence` usa ticket de sequência, escopo, caixinha e geração de sessão. Uma nova requisição ou cancelamento invalida a anterior.
- M38095–M38099: o componente captura a sessão autenticada, somente aplica resultados de rede enquanto a mesma sessão estiver vigente, e ignora conclusão tardia de falhas e `finally`.
- M38100–M38104: alteração de caixinha, candidato ou justificativa invalida imediatamente o pedido pendente. Evento de logout/troca de sessão limpa o conteúdo e força nova leitura de capacidades.
- M38105–M38109: resultados somente aparecem quando ticket, contexto e geração continuam idênticos; testes Node de escopo, duas caixinhas, duas identidades, replay, mudança de geração, cancelamento e integridade estática dos pontos de aplicação.

## Restrições
Essa proteção é **UI**, não autorização: o servidor deve continuar aplicando autenticação, permissões e RLS independentemente. Não existe envio de e-mail, convite, alteração de membro ou registro de consentimento pelo componente. Sem migrations, sem banco original Termux, sem execução OCI, sem Pix real. Produção permanece BLOQUEADA.

## Teste
```sh
./node_modules/.bin/tsx src/tests/m38090_master_onboarding_request_fence_ci.test.ts
bash backend/scripts/frfinance_m37979_termux_frontend.sh
```
