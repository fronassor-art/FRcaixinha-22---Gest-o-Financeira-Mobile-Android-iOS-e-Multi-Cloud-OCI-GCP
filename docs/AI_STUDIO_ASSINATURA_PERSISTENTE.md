# Assinatura Android permanente — FRcaixinha AI Studio

## Regra operacional aprovada

A instalação inicial em Android de homologação usa **um único package ID**
\`com.frcaixinha.app.aistudio\`, com **chave de assinatura persistente** e
\`versionCode\` crescente e **maior que o APK instalado**. O workflow geral
adotou na M39089 a fórmula \`3909000 + GITHUB_RUN_NUMBER\` para corrigir
o erro da M39088 (código 1359), inferior ao APK M39065 instalado com
sucesso (código 3906508) e aos candidatos posteriores (código 3906531).
O workflow M39065 é histórico e possui contador independente; **não usar
seus artefatos antigos como atualização da linhagem M39089**. Futuras
versões devem ser instaladas **sobre o mesmo aplicativo**, preservando
o armazenamento local. Não criar applicationIdSuffix novo a cada build.
O certificado SHA-256 de homologação confirmado para M39065 e M39088 é
\`ab003bfd9a496e211370ff4dfcc5044ec19e1151b69ad488d7ec1b0f34ce31c7\`.

O Android exige simultaneamente package ID compatível, mesma assinatura e
versionCode maior ou igual. A troca do certificado sem prova de rotação pode
exigir **uma última desinstalação**, que apaga dados *locais* da app. O
PostgreSQL local não faz parte do APK e não deve ser reinicializado para isso.

## Segurança de assinatura

A chave privada **NUNCA** vai no repositório, logs, capturas de tela ou chat.
O GitHub guarda o arquivo PKCS12 em base64 (é somente codificação, portanto
deve ser armazenado como secret criptografado) e as senhas em **Actions
secrets**. **Não usar senha e chave hardcoded, nem gerar chave aleatória em
cada execução CI.**

Actions secrets exigidos:
- \`FRCAIXINHA_ANDROID_KEYSTORE_BASE64\` — conteúdo base64 do arquivo .p12.
- \`FRCAIXINHA_ANDROID_STORE_PASSWORD\` — senha do arquivo.
- \`FRCAIXINHA_ANDROID_KEY_ALIAS\` — alias estável.
- \`FRCAIXINHA_ANDROID_KEY_PASSWORD\` — senha do alias (PKCS12: igual à senha do arquivo).

O job Android falha fechado quando falta qualquer secret, não publica APK de
assinatura efêmera com nome de produção de testes. O job confirma ID,
versionCode e assinatura v2 via \`apksigner\`.

## Registro inicial com Termux

1. Verificar \`gh auth status\`, \`command -v keytool\`, \`command -v openssl\`.
2. Gerar **uma única vez** um PKCS12 com RSA 3072/4096 e validade prolongada.
3. Definir os quatro segredos com \`gh secret set -R owner/repo\`, enviando
   seus valores por STDIN para não expor em histórico/comando.
4. Fazer backup offline criptografado do PKCS12 **e da senha**. Sem esse
   backup, perda da chave impede futuras atualizações ao mesmo app.
5. Reexecutar o workflow (novo commit ou rerun) e conferir 6/6 PASS.
6. Se necessário, somente depois do APK estável PASS, substituir a versão
   antiga, uma única vez. Próximos APKs de mesma chave atualizam em cima.

Para distribuição automatizada a usuários finais, avaliar **Google Play
App Signing e trilhas fechadas de teste**. Um APK distribuído por arquivo
externo pode exigir confirmação do usuário para atualização; não prometer
atualização silenciosa.

**ATENÇÃO segurança:** em repositórios públicos, segredos devem ter acesso
limitado, branches/workflows revisados e ambiente de assinatura protegido.
Não usar esse material em workflows não confiáveis, forks ou PRs externos.
A assinatura neste momento é **de homologação**, não chave de distribuição
de produção.

Não altera PostgreSQL, tabela de usuários, credenciais existentes, API
financeira ou main. PR #2 continua Draft.

## Script de configuracao disponivel no repositorio

No Termux, apos sincronizar o projeto, rode apenas uma vez:

```bash
cd "$HOME/frcaixinha-aistudio-mobile"
bash scripts/setup_android_signing_termux.sh
```

O script cria PKCS12 protegido em `~/.config/frcaixinha-aistudio-mobile/android-signing`
e envia os quatro secrets sem exibir suas senhas. Se falhar, reenviar
usando a mesma chave local; **nunca** criar uma segunda chave para corrigir
um erro de rede. Se qualquer secret ja existir antes da geracao, o
script bloqueia para evitar rotação inadvertida. O proprietario deve
guardar backup seguro offline da chave e senha e nao enviar ao chat.

### Dependencias e compatibilidade Termux

O script exige `python3`, `keytool` (OpenJDK 21), `gh`, `base64` e `tr`.
A senha aleatoria e gerada com `python3 -B -c 'import secrets; print(secrets.token_hex(32))'`.
Nao depende do comando `openssl`: em algumas instalacoes do Termux, o pacote
`openssl` pode estar instalado sem disponibilizar esse executavel. Nao ha
necessidade de reinstalar o Java ou alterar o PostgreSQL.
