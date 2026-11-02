#!/usr/bin/env bash
# Configuracao unica da chave de assinatura Android do FRcaixinha AI Studio.
# Somente o proprietario deve executar. Nao imprimir a chave, a senha ou tokens.
set -euo pipefail
umask 077

REPO="fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
ALIAS="frcaixinha_aistudio"
DIR="$HOME/.config/frcaixinha-aistudio-mobile/android-signing"
KEYSTORE="$DIR/frcaixinha-aistudio-stable.p12"
PASSWORD_FILE="$DIR/frcaixinha-aistudio-password.txt"
MARKER="$DIR/secrets-uploaded.txt"

for program in gh keytool openssl base64 tr; do
    if ! command -v "$program" >/dev/null 2>&1; then
        echo "BLOQUEADO: falta '$program'. Instale a dependencia antes de continuar."
        exit 2
    fi
done
if ! gh auth status >/dev/null 2>&1; then
    echo "BLOQUEADO: autentique o GitHub CLI com gh auth login."
    exit 2
fi
if ! gh api "repos/$REPO" --jq '.full_name' >/dev/null 2>&1; then
    echo "BLOQUEADO: nao foi possivel validar o repositorio no GitHub."
    exit 2
fi

mkdir -p "$DIR"
chmod 700 "$DIR"
if [[ -L "$KEYSTORE" || -L "$PASSWORD_FILE" ]]; then
    echo "BLOQUEADO: arquivos de chave/senha nao podem ser links simbolicos."
    exit 2
fi
if [[ -e "$KEYSTORE" && ! -f "$PASSWORD_FILE" ]] ||
   [[ -e "$PASSWORD_FILE" && ! -f "$KEYSTORE" ]]; then
    echo "BLOQUEADO: chave/senha incompletas. Nunca gere chave nova por cima da antiga."
    exit 2
fi

if [[ ! -e "$KEYSTORE" ]]; then
    echo "=== CRIAR CHAVE PERSISTENTE PELA PRIMEIRA VEZ ==="
    # Evitar substituir secrets existentes sem conferir a origem da chave.
    existing="$(gh secret list -R "$REPO" --json name --jq '.[].name')"
    for name in \
      FRCAIXINHA_ANDROID_KEYSTORE_BASE64 \
      FRCAIXINHA_ANDROID_STORE_PASSWORD \
      FRCAIXINHA_ANDROID_KEY_ALIAS \
      FRCAIXINHA_ANDROID_KEY_PASSWORD; do
        if grep -qx "$name" <<< "$existing"; then
            echo "BLOQUEADO: '$name' ja existe. Nao substituir chave de assinatura."
            exit 2
        fi
    done
    FR_KEY_PASS="$(openssl rand -hex 32)"
    export FR_KEY_PASS
    keytool -genkeypair -noprompt \
      -storetype PKCS12 -keystore "$KEYSTORE" \
      -alias "$ALIAS" -keyalg RSA -keysize 3072 -validity 12000 \
      -storepass:env FR_KEY_PASS -keypass:env FR_KEY_PASS \
      -dname "CN=FRcaixinha AI Studio,OU=Homologacao,O=FRcaixinha,C=BR" \
      >/dev/null 2>&1
    printf '%s' "$FR_KEY_PASS" > "$PASSWORD_FILE"
    chmod 600 "$KEYSTORE" "$PASSWORD_FILE"
    unset FR_KEY_PASS
    echo "CHAVE_PERSISTENTE_CRIADA=PASS"
else
    echo "=== REUTILIZAR CHAVE EXISTENTE SEM REGENERAR ==="
fi

FR_KEY_PASS="$(cat "$PASSWORD_FILE")"
export FR_KEY_PASS
if ! keytool -list -storetype PKCS12 -keystore "$KEYSTORE" \
      -alias "$ALIAS" -storepass:env FR_KEY_PASS >/dev/null 2>&1; then
    echo "BLOQUEADO: chave, alias ou senha local invalido."
    exit 2
fi

echo "=== ENVIAR SEGREDOS CRIPTOGRAFADOS AO GITHUB ACTIONS ==="
# CLI le STDIN; nenhum segredo aparece em stdout ou argumento do processo gh.
base64 "$KEYSTORE" | tr -d '\n' | gh secret set FRCAIXINHA_ANDROID_KEYSTORE_BASE64 -R "$REPO"
printf '%s' "$FR_KEY_PASS" | gh secret set FRCAIXINHA_ANDROID_STORE_PASSWORD -R "$REPO"
printf '%s' "$ALIAS" | gh secret set FRCAIXINHA_ANDROID_KEY_ALIAS -R "$REPO"
printf '%s' "$FR_KEY_PASS" | gh secret set FRCAIXINHA_ANDROID_KEY_PASSWORD -R "$REPO"

printf 'FRcaixinha AI Studio: assinatura homologacao registrada.\n' > "$MARKER"
chmod 600 "$MARKER"
unset FR_KEY_PASS

echo "=== CONFERIR NOMES (NAO CONTEUDO) DOS SEGREDOS ==="
gh secret list -R "$REPO" --json name --jq \
  '.[] | select(.name | startswith("FRCAIXINHA_ANDROID_")) | .name'
echo "ASSINATURA_PERSISTENTE_CONFIGURADA=PASS"
echo "IMPORTANTE: guarde backup SEGURO E FORA DO CELULAR de ambos:"
echo "  $KEYSTORE"
echo "  $PASSWORD_FILE"
echo "Nao envie esses arquivos nem seus conteudos ao chat, ao Git ou a outras pessoas."
