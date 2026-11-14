# APK de teste paralelo — perfis isolados (02/11/2026)

O Android exibiu "App não instalado" ao atualizar o debug anterior.
Como a assinatura debug do CI pode mudar entre execuções, preparou-se uma
variante **temporária de homologação instalável ao lado** do app anterior.

- Debug applicationId: `com.frcaixinha.app.aistudio2` (o anterior permanece `com.frcaixinha.app.aistudio`).
- Nome visível: **FRcaixinha Perfis** para distinguir dois ícones.
- Mesma base de código, login seguro, perfis Master/Admin/Membro isolados,
  API local em `http://127.0.0.1:8000` na build debug e ícone premium.
- Nenhum dado de instalação existente é apagado ou migrado; novo app
  começa com armazenamento local próprio e exige novo login.
- Testes no celular podem ocorrer usando dados móveis; não exigem ADB Wi-Fi.
- Teste de compilação CI confere explicitamente novo ID do pacote.
- A assinatura debug **ainda não é persistente**. Novas atualizações do
  mesmo identificador poderão falhar novamente se as chaves diferirem.
  Para distribuição estável será necessário implantar assinatura permanente
  com chave protegida em segredos do CI e política de rotação segura.

PR permanece Draft; sem alterar main, banco ou cadastros.
