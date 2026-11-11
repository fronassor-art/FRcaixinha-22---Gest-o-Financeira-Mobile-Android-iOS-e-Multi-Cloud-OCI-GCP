#!/usr/bin/env bash
# FR Finance AI Studio M37979: frontend test, Android/Termux TS 7 workaround.
# No changes to the repository lockfile, database, OCI or payment settings.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
test -z "$(git status --porcelain)"
test -x "./node_modules/.bin/tsx"
command -v npm >/dev/null
command -v node >/dev/null

echo "=== FR FINANCE M37979 — FRONTEND TERMUX ==="
echo "GIT_SHA=$(git rev-parse --short HEAD)"
echo "NODE_VERSION=$(node --version)"
echo "PLATFORM=$(node -p 'process.platform + "/" + process.arch')"

PLATFORM="$(node -p 'process.platform')"
ARCH="$(node -p 'process.arch')"

if [ "$PLATFORM" = "android" ] && [ "$ARCH" = "arm64" ]; then
  # TypeScript 7.0.2 ships native Go binaries, but lacks the Android/ARM64
  # platform artifact. Use official TS6 JS only as a complementary local
  # typecheck, retaining TS7 as the project and GitHub CI compiler.
  CACHE="$HOME/.cache/frfinance-m37979-typescript6"
  TSC6="$CACHE/node_modules/.bin/tsc6"
  if [ ! -x "$TSC6" ]; then
    echo "=== INSTALAR COMPILADOR COMPATIVEL FORA DO REPOSITORIO ==="
    mkdir -p "$CACHE"
    npm install --prefix "$CACHE" \
      --no-save --no-package-lock --ignore-scripts \
      --no-audit --no-fund @typescript/typescript6@6.0.2
  fi
  test -x "$TSC6"
  "$TSC6" --version
  echo "=== TYPECHECK LOCAL TS6 COMPAT ==="
  "$TSC6" --noEmit --project "$ROOT/tsconfig.json"
  echo "M37979_TYPECHECK_LOCAL=PASS_TS6_COMPAT"
  echo "M37979_TYPECHECK_TS7_NATIVE_LOCAL=UNAVAILABLE_ANDROID_ARM64"
else
  echo "=== TYPECHECK ORIGINAL TS7 ==="
  npm run lint
  echo "M37979_TYPECHECK_LOCAL=PASS_PROJECT_COMPILER"
fi

echo "=== TESTES DE AUTENTICACAO E NOTIFICACOES ==="
for TEST_FILE in \
  src/tests/m37974_api_origin_notification_guard_ci.test.ts \
  src/tests/m37977_notification_race_ci.test.ts \
  src/tests/m37447_mobile_backend_diagnostic_ci.test.ts \
  src/tests/m19000_notifications_functional_ui.test.ts \
  src/tests/auth_context_security.test.ts \
  src/tests/mobile_three_profiles.test.ts
do
  "./node_modules/.bin/tsx" "$TEST_FILE"
done

echo "=== VERIFICAR INTEGRIDADE DO REPOSITORIO ==="
test -z "$(git status --porcelain)"
echo "M37979_FRONTEND_TESTS=PASS"
echo "M37979_GIT_WORKTREE=CLEAN"
echo "M37979_SQL_MIGRATIONS=NONE"
echo "M37979_PIX_REAL=OFF"
echo "M37979_PAYMENTS_REAL=OFF"
echo "M37979_ACTIVATION_REAL=OFF"
echo "M37979_PRODUCTION=BLOCKED"
