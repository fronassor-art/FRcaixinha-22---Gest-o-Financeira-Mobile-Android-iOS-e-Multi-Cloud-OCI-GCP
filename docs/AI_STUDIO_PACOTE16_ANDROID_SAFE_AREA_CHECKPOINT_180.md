# Pacote 16 — Safe area Android após inspeção APK 180

Baseline: f3932ab1c3befc02b8794c6095b0a019e71783d0.
PR #2 em Draft; branch atualizacao-ai-studio-9b46a63187.

## Evidências de campo
- APK 180 confirmado na tela pelo build f3932ab.
- HEALTH=200, DATABASE=200, AUTH=200, MASTER sem token=401.
- Capturas mostram barra de status Android por cima do cabeçalho.
- Master, Admin, Membro e contribuições exibidos sem operações reais.
- A simulação Price foi informada como PASS, mas o resultado não
  apareceu nas capturas: confirmação visual pendente.

## Correção
- Capacitor 8 SystemBars com insetsHandling native e viewport-fit cover.
- WebView moderno usa env(safe-area-inset-top) no body e header sticky.
- WebView antigo usa padding nativo e CSS env() zero, sem duplicidade.
- Barra inferior usa env(safe-area-inset-bottom).
- StatusBar com ícones claros e background verde escuro.
- CI verifica layout, config e geração Android no job de build.

## Restrições
- Sem mudanças financeiras, migrations, tokens, app ID, assinatura ou main.
- Layout Android precisa de verificação manual no APK futuro;
  CI aprovado não garante aparência em todos os WebViews.
- Próximo checkpoint Android manual previsto para versão 190.
