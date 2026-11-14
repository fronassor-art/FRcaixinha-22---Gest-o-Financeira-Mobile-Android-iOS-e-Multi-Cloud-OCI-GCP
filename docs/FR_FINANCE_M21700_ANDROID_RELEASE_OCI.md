# M21700 — Preparação de APK release OCI (sem publicação)

A aplicação debug AI Studio utiliza sufixo .aistudio. Release usa outra identidade Android; não atualiza o debug instalado por cima. O identificador comercial definitivo deve ser aprovado antes de publicar.

## Fronteiras implementadas

- Tarefa Gradle release exige keystore PKCS12 dedicado e quatro variáveis FR_FINANCE_ANDROID_RELEASE_*; não aceita a chave persistente do debug.
- Artefato nativo release deve ter androidScheme=https, cleartext=false e não pode carregar URL do FastAPI local http://127.0.0.1:8000.
- Perfil FR_FINANCE_ANDROID_RELEASE_PROFILE=1 exige VITE_API_URL HTTPS pública sem login, query, path ou domínio local. A sincronização Capacitor falha se esses limites não forem atendidos.
- CI valida os contratos estaticamente. Nenhuma chave ou certificado real foi criada nem transmitida.

## Somente depois da API OCI homologada

    export FR_FINANCE_ANDROID_RELEASE_PROFILE=1
    export VITE_API_URL=https://api.SEUDOMINIO.com.br
    npm run cap:build
    cd android
    # Injetar as quatro variáveis FR_FINANCE_ANDROID_RELEASE_* via cofre.
    ./gradlew --no-daemon assembleRelease

Não executar com domínio fictício. Antes da produção faltam: autenticação de produção (explicitamente bloqueada hoje), OCI e HTTPS, banco com RLS/backup, OAuth de cada tenant, webhooks de testes, conciliação independente, assinatura release e testes Android completos. M21700 não libera dinheiro real.
