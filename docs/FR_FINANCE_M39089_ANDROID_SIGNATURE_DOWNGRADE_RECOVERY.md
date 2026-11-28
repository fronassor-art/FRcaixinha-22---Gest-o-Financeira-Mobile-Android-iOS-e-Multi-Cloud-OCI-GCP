# FR Finance M39089 — corrigir falha de atualização Android (downgrade)

## Diagnóstico, confirmado pela comparação entre versões

- **APK principal comprovadamente instalado com sucesso**: M39065, pacote `com.frcaixinha.app.aistudio`, `versionCode=3906508`.
- **Último APK compilado antes da correção**: M39088, `versionCode=1359`, mesmo pacote.
- **SHA-256 do certificado de assinatura** nas evidências do APK M39065 instalado e no log do GitHub do APK M39088: `ab003bfd9a496e211370ff4dfcc5044ec19e1151b69ad488d7ec1b0f34ce31c7`.
- Conclusão: assinatura **compatível** nas versões comparadas; o APK M39088 tem código **menor** que a instalação bem-sucedida, e o Android deve recusar atualização por downgrade. Não afirmar que a assinatura instalada hoje foi relida neste checkpoint; nova inspeção do pacote via Termux é necessária se o usuário instalou outra variante após M39065.
- Causa de código: `.github/workflows/validacao-atualizacao.yml` fixava `FRCAIXINHA_ANDROID_VERSION_CODE` diretamente em `${{ github.run_number }}`; enquanto `.github/workflows/frfinance-android-debug-m39050.yml` (M39065) usava `3906500 + GITHUB_RUN_NUMBER`.

## Mudança M39089

- Preservado **exatamente** o package ID `com.frcaixinha.app.aistudio`, a chave privada dos segredos GitHub e a assinatura PKCS12 persistente.
- Na CI geral, exigida SHA-256 fixa do certificado do M39065 **antes** de gerar novo APK; segredos e chave não aparecem no Git.
- Corrigido código para `3909000 + GITHUB_RUN_NUMBER`. O job bloqueia valores não superiores a `3906531` e não aceita código maior que 2100000000.
- Conferido `versionCode` esperado no `aapt` do APK e o mesmo SHA-256 original no `apksigner`, além de assinatura v2.
- Testes de regressão somente fonte: `backend/tests/test_m39089_android_upgrade_version_ci.py` e workflow `frfinance-m39089-android-upgrade-ci.yml`.
- Atualizado `docs/AI_STUDIO_ASSINATURA_PERSISTENTE.md` para registrar a faixa correta de numeração; workflows antigos M39065 usam contador separado, por isso evitar distribuir seus artefatos como atualizações após M39089.

## Segurança operacional

Sem mudança de código do app, release, SQLite/PG, migrações, PIX, pagamentos, notificações externas, dados ou instalação no Android. PR #2 continua draft. `PIX_REAL=OFF`; `ATIVACAO_REAL=OFF`; `FR_FINANCE_SPECIAL_CREDIT_SANDBOX=NO`.

## Próximo aceite

1. Verificar **CI geral M39089 e novo job APK**: somente `success` permite distribuir APK.
2. Conferir o `versionCode` final, pacote exato, assinatura SHA-256 e artefato disponibilizado pela CI. O novo valor será calculado com o número **real** da execução M39089.
3. Antes da atualização, no Termux nativo, consultar `/system/bin/pm list packages --show-versioncode --user 0 com.frcaixinha.app.aistudio` e comparar código com o novo APK. Não desinstalar, não fazer downgrade e não executar comandos que alterem pacotes.
4. Somente após compatibilidade comprovada, o usuário poderá instalar por cima e executar testes funcionais; sem alterar o PostgreSQL original.
