"""M37979: Android native TypeScript 7 bug workaround is isolated and fail-closed."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
RUNBOOK=ROOT/"backend/scripts/frfinance_m37979_termux_frontend.sh"


def test_shell_syntax():
    subprocess.run(["bash","-n",str(RUNBOOK)],check=True)


def test_no_project_dependency_or_financial_mutation():
    s=RUNBOOK.read_text(encoding="utf-8")
    assert '--prefix "$CACHE"' in s
    assert "--no-save --no-package-lock --ignore-scripts" in s
    assert "@typescript/typescript6@6.0.2" in s
    assert 'PLATFORM="$(node -p' in s
    assert '"$TSC6" --noEmit --project "$ROOT/tsconfig.json"' in s
    assert "npm run lint" in s
    assert 'test -z "$(git status --porcelain)"' in s
    for forbidden in ("npm install -D", "npm audit fix", "git reset", "git clean",
                      "git push", "psql ", "pg_restore", "oci compute", "mp_order_create",
                      "FR_FINANCE_PIX_REAL=true"):
        assert forbidden not in s
    for flag in ("M37979_SQL_MIGRATIONS=NONE", "M37979_PRODUCTION=BLOCKED",
                 "M37979_ACTIVATION_REAL=OFF"):
        assert flag in s


def test_clients_and_sessions_are_tested_without_source_mutation():
    s=RUNBOOK.read_text(encoding="utf-8")
    for test in (
        "m37974_api_origin_notification_guard_ci.test.ts",
        "m37977_notification_race_ci.test.ts",
        "m37447_mobile_backend_diagnostic_ci.test.ts",
        "m19000_notifications_functional_ui.test.ts",
        "auth_context_security.test.ts",
        "mobile_three_profiles.test.ts",
    ):
        assert test in s
    assert '"./node_modules/.bin/tsx" "$TEST_FILE"' in s
