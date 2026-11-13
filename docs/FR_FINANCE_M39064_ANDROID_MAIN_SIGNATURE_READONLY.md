# FR Finance — M39064: comparação da chave original com o APK instalado

## Evidências diretas do Android

Consulta /system/bin/pm no próprio aparelho do usuário:

- `com.frcaixinha.app.aistudio`: versionCode **1080**.
- `com.frcaixinha.app.aistudio.diag`: versionCode **1**.
- Ambos coexistem porque os package names são diferentes.
- `apksigner verify --print-certs` retornou exit 0 para ambos.
- SHA-256 do certificado **principal**:
  `ab003bfd9a496e211370ff4dfcc5044ec19e1151b69ad488d7ec1b0f34ce31c7`.
- SHA-256 do certificado do **diagnóstico**:
  `db1e87f4a271d5af1aa2659c15eaff9136b2534dbca2c2661681906d9dfb298a`.

O certificado principal exibe DN de homologação FRcaixinha AI Studio.
O diagnóstico tem DN Android Debug. DN igual, isoladamente, NÃO prova
que a chave local é a mesma. Só impressão SHA-256 coincide com certeza.

## O problema de atualização Android

O projeto principal deve permanecer com
`applicationId=com.frcaixinha.app.aistudio` em debug.

O diagnóstico usa o sufixo extra `.diag`, portanto gera outra instalação.
O workflow de debug M39050 tem
`FR_FINANCE_ANDROID_PARALLEL_DIAGNOSTIC=0`, mas não exige assinatura
persistente e não força versionCode acima do já instalado (1080).
Esses controles devem ser corrigidos antes de distribuir novo APK principal.

## O que a M39064 faz

- Verifica worktree/branch/SHA aprovados, sem alterar Git.
- Confere existência, proprietário e permissões privadas do diretório,
  do PKCS12 e do arquivo de senha do Termux nativo.
- Usa apenas `keytool -list -v` com senha passada ao processo filho via
  variável de ambiente, não via argumento shell.
- Extrai somente SHA-256 público do certificado, em memória.
- Compara com o certificado principal já observado no Android.
- Mostra `M39064_LOCAL_KEYSTORE=MATCH_INSTALLED_MAIN` se compatível.
- Bloqueia se a chave não existir, estiver inacessível, ou for diferente.
- Nunca gera nova chave, imprime senha, envia arquivo, modifica Android,
  acessa o PG18 ou a FastAPI.

## Interpretação

`M39064_STATUS=PASS_SIGNER_MATCH_READ_ONLY`:
a chave privada local preservada aparentemente permite assinar atualizações
compatíveis com o certificado principal. Ainda será necessário compilar
com mesmo applicationId, versionCode >=1081 e verificar a assinatura da
build antes de instalar.

`M39064_STATUS=BLOCKED_*`:
**não regenerar chave nem desinstalar o app instalado**. Revisar backups
e/ou segredos já publicados no GitHub (somente nomes, nunca seus valores).

## Independência da FastAPI

O bloqueio da FastAPI M39060 continua separado: api.env contém três DSNs
homologadas mas a instância visual 8000 não carregou DATABASE_URL.
A instalação paralela Android não alterou o ambiente do processo Termux.
Pix real, ativação real, worker Brevo e login real permanecem OFF.

## Instruções

Sincronize por fast-forward a branch original até SHA aprovado e execute:

    AI_STUDIO_APPROVED_SHA="$SHA" PYTHONDONTWRITEBYTECODE=1 \
    python3 -B -m backend.scripts.frfinance_m39064_installed_apk_signer_readonly

Nenhum dado de usuário é solicitado e nenhum segredo deve ser colado no chat.
