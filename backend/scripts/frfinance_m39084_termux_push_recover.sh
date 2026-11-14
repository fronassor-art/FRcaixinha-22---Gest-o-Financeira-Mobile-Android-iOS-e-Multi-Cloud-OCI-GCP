#!/usr/bin/env bash
# FR Finance M39084 — recover the missing, lock-pinned Capacitor push
# package on Termux Android/arm64 only. No source, lockfile, DB or Pix writes.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
test "$HOME" = "/data/data/com.termux/files/home"
test "$(node -p 'process.platform + "/" + process.arch')" = "android/arm64"
test -z "$(git status --porcelain --untracked-files=all)"
test -x ./node_modules/.bin/tsx
test -d ./node_modules/@capacitor/core
command -v npm >/dev/null
command -v python3 >/dev/null
command -v tar >/dev/null
test "$(node -p "require('./package.json').dependencies['@capacitor/push-notifications']")" = "8.1.2"
test "$(node -p "require('./package-lock.json').packages['node_modules/@capacitor/push-notifications'].version")" = "8.1.2"

echo "=== FR FINANCE M39084 — RESTAURAR PUSH NATIVO LOCAL ==="
TARGET="$ROOT/node_modules/@capacitor/push-notifications"
CACHE="$HOME/.cache/frfinance-m39084-capacitor-push"
mkdir -p "$CACHE"
git check-ignore -q "$TARGET"

if [ -f "$TARGET/package.json" ]; then
  echo "M39084_PUSH_PACKAGE=PRESENT"
  test "$(node -p "require('./node_modules/@capacitor/push-notifications/package.json').version")" = "8.1.2"
else
  # Never replace an existing package or symlink automatically.
  test ! -e "$TARGET"
  test ! -L "$TARGET"
  echo "=== BAIXAR PACOTE EXATO SEM INSTALAR ARVORE DE DEPENDENCIAS ==="
  npm pack '@capacitor/push-notifications@8.1.2' \
    --ignore-scripts --pack-destination "$CACHE" --silent
  ARCHIVE="$CACHE/capacitor-push-notifications-8.1.2.tgz"
  test -f "$ARCHIVE"
  node - "$ARCHIVE" <<'NODE'
const fs = require('node:fs');
const crypto = require('node:crypto');
const archive = process.argv[2];
const lock = JSON.parse(fs.readFileSync('package-lock.json','utf8'));
const entry = lock.packages['node_modules/@capacitor/push-notifications'];
if (!entry || entry.version !== '8.1.2') throw Error('Lockfile version mismatch');
const actual = 'sha512-' + crypto.createHash('sha512')
  .update(fs.readFileSync(archive)).digest('base64');
if (entry.integrity !== actual) throw Error('Push package integrity mismatch');
console.log('M39084_PACKAGE_INTEGRITY=PASS_SHA512');
NODE
  STAGING="$(mktemp -d "$CACHE/staging.XXXXXXXX")"
  trap 'rm -rf -- "$STAGING"' EXIT
  tar -xzf "$ARCHIVE" -C "$STAGING"
  test -f "$STAGING/package/package.json"
  mkdir -p "$ROOT/node_modules/@capacitor"
  test ! -e "$TARGET"
  mv "$STAGING/package" "$TARGET"
  test "$(node -p "require('./node_modules/@capacitor/push-notifications/package.json').version")" = "8.1.2"
  echo "M39084_PUSH_PACKAGE=RESTORED_IN_IGNORED_NODE_MODULES"
fi

echo "=== TYPECHECK COMPATIVEL E TESTES HISTORICOS ==="
bash backend/scripts/frfinance_m37979_termux_frontend.sh

echo "=== M39083 — TESTES DE INTERFACE ==="
for TEST_FILE in \
  src/tests/m39083_cycle_readiness_ui_ci.test.ts \
  src/tests/m39076_tenant_campaigns_navigation_ci.test.ts \
  src/tests/m39020_credit_push_ui_ci.test.ts
do
  ./node_modules/.bin/tsx "$TEST_FILE"
done

test -z "$(git status --porcelain --untracked-files=all)"
echo "M39084_LOCAL_FRONTEND=PASS_TS6_COMPAT"
echo "M39084_OFFICIAL_TS7_CI=NOT_REPLACED"
echo "M39084_GIT_VERSIONED_CHANGES=NONE"
echo "M39084_DATABASE_WRITES=NONE"
echo "M39084_SQL_MIGRATIONS=NONE"
echo "M39084_EXTERNAL_DELIVERY=OFF"
echo "M39084_PIX_REAL=OFF"
echo "M39084_ACTIVATION_REAL=OFF"
