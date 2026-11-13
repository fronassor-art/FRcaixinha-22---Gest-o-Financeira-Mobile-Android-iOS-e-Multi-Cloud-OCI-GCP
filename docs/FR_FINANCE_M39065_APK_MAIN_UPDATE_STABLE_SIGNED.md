# FR Finance M39065 — correção da atualização do APK principal Android

## Prova no aparelho e no Termux
O gerenciador Android listou:
- `com.frcaixinha.app.aistudio`: versionCode **1080**.
- `com.frcaixinha.app.aistudio.diag`: versionCode **1**.

Os dois aplicativos coexistem por causa dos **applicationId diferentes**;
o de diagnóstico nunca é uma atualização do app principal.

`apksigner verify --print-certs` no Android confirmou o certificado principal:
`ab003bfd9a496e211370ff4dfcc5044ec19e1151b69ad488d7ec1b0f34ce31c7`.

A auditoria de leitura M39064 passou no Termux:
10 testes PASS; `M39064_LOCAL_KEYSTORE=MATCH_INSTALLED_MAIN`;
a chave original PKCS12 e sua senha privada permanecem no Termux,
sem geração, alteração ou divulgação.

## Correção do pipeline GitHub Actions
O workflow existente `.github/workflows/frfinance-android-debug-m39050.yml`
foi atualizado, sem criar segundo fluxo que assine APK concorrente.
Nome de execução: `FR Finance M39065 - Atualizacao APK principal original`.

Salvaguardas:
1. `FR_FINANCE_ANDROID_PARALLEL_DIAGNOSTIC=0` fixa o APK principal
   `com.frcaixinha.app.aistudio`, não `.aistudio.diag`.
2. Requer assinatura persistente `FRCAIXINHA_ANDROID_REQUIRE_STABLE_SIGNING=1`.
   Se faltarem segredos existentes de assinatura, **falha fechado**
   (`REQUIRED_EXISTING_GITHUB_SIGNING_SECRET_MISSING`): não gera
   chave substituta e não produz APK de assinatura efêmera.
3. Carrega os quatro GitHub Actions Secrets esperados pelo projeto,
   compara SHA-256 público do certificado do PKCS12 com o instalado.
   Divergência `KEYSTORE_CERT_MISMATCH` bloqueia a compilação.
4. `FRCAIXINHA_ANDROID_VERSION_CODE = 3906500 + GITHUB_RUN_NUMBER`;
   versão superior a 1080 para este fluxo e crescente entre execuções
   novas do mesmo workflow.
5. Compila o frontend com API local `http://127.0.0.1:8000`,
   sincroniza Capacitor e executa `:app:assembleDebug`.
6. Antes de publicar o artifact, usa `aapt dump badging` para
   comprovar applicationId e versionCode, e
   `apksigner verify --print-certs` para confirmar **no APK gerado**
   a mesma impressão digital SHA-256 do app 1080.
7. Publica somente após PASS o arquivo
   `android/app/build/outputs/apk/debug/app-debug.apk`, com checksum SHA-256,
   sob o nome `FR-Finance-M39065-APK-Principal-Assinado`.

O APK é **debug de homologação local**, não release de produção.
Não publica OCI, não inicia FastAPI, não faz login, não cria sessão, não
instala nem desinstala aplicativo, não toca no PostgreSQL e mantém
Pix real e envios Brevo desativados.

## Dependência: secrets do GitHub Actions
A chave local comprovada na M39064 não comprova que os quatro segredos
do GitHub estão criados e correspondem à mesma chave. Se faltarem,
o build ficará bloqueado, sem fallback para chave debug.

Em caso de bloqueio, o operador deve auditar **somente os nomes** dos
segredos remotos e reutilizar a **chave original**, jamais gerar outra.
Não compartilhar o arquivo PKCS12 nem senhas no chat, issue ou commit.

## Uso do APK somente após o CI PASS
Baixe o artifact verificado do workflow M39065. O zip da Action contém
`app-debug.apk` e `app-debug.apk.sha256`. Instale **sobre** o app
principal `com.frcaixinha.app.aistudio`, sem desinstalar nem limpar dados;
o Android deve apresentar *atualizar*. Se oferecer instalar um segundo
app, abortar e conferir o APK. O .diag pode permanecer instalado até
homologação e decisão de limpeza posterior.

Antes de qualquer teste de login, a FastAPI visual da porta 8000 precisa
passar por transição manual e supervisionada para o launcher original
com DSNs do PostgreSQL FR Finance PG18/5433. Essa questão é independente
da assinatura Android. M39063 é apenas pré-verificação read-only.
