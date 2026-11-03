# FRcaixinha AI Studio Mobile — Pacote 11: retomada segura

Baseline: dbd62eeb0ddbfe417918b82199e48277a115194c
PR #2 Draft, branch atualizacao-ai-studio-9b46a63187.

## Risco mitigado
Um Android com o aplicativo suspenso pode retardar o timer local. Ao
voltar do segundo plano, o app deve exigir uma nova confirmação /auth/me
antes de reexibir telas protegidas, independentemente do perfil.

## Implementação
- Lifecycle observa visibilitychange (retorno a visible) e pageshow
  apenas em recuperação bfcache.
- Guard concentra chamadas simultâneas, não solicita sem token
  e torna a interface temporariamente opaca/protegida.
- GET /auth/me confirma credencial, vínculo e revogação conforme a API;
  falha de autenticação/rede invalida localmente, sem modo offline.
- Uma requisição de inicialização antiga não pode apagar um login novo:
  a atualização do contexto depende da sessão capturada.
- O guard descarta erros e alterações após desmontagem e valida
  snapshot antes de limpar sessão em falha inesperada.
- CI cobre concorrência, troca de sessão, erro de rede, ausência
  de token, descarte após desmontagem e presença das rotas lifecycle.

## Restrições
Sem migrations, grants, convite, alterações reais de contas/saldos,
operações financeiras, merge ou alteração do identificador/assinatura.
A inspeção manual está reservada à versão 180, salvo necessidade crítica.
