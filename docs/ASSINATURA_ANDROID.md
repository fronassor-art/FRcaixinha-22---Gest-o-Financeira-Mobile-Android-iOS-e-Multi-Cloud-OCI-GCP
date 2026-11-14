# Identidade e assinatura Android

O aplicativo novo usa `com.frcaixinha.app` em `capacitor.config.ts` e `android/app/build.gradle`. Preserve esse identificador e aumente `versionCode` a cada futura atualização distribuída. Ele é separado do APK antigo `com.fronassor.frcaixinha.aistudio`, conforme autorização do proprietário.

O GitHub Actions compila **APK debug de teste** e o publica como artefato temporário. A chave debug não serve como assinatura durável de distribuição.

Antes de distribuir versões atualizáveis, crie a keystore fora do clone, faça backup offline protegido e registre com segurança o alias, a validade e as senhas. Configure assinatura release por segredos do ambiente de build, sem imprimir material sensível, sem salvar `*.jks`, `*.keystore`, `*.p12` ou senhas no repositório. Teste instalação e atualização em aparelho de teste com o mesmo certificado. Nenhuma assinatura release foi configurada ou usada nesta rodada.
