"""M39084: Termux recovery is lock-pinned, integrity-checked and offline-safe in CI.

Never execute the recovery itself on CI: it targets Android node_modules only.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/frfinance_m39084_termux_push_recover.sh"


def test_shell_syntax_and_safe_scope():
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    s = SCRIPT.read_text(encoding="utf-8")
    for required in (
        'test "$HOME" = "/data/data/com.termux/files/home"',
        '"android/arm64"',
        "test -z \"$(git status --porcelain --untracked-files=all)\"",
        "git check-ignore -q",
        "npm pack '@capacitor/push-notifications@8.1.2'",
        "--ignore-scripts --pack-destination",
        "crypto.createHash('sha512')",
        "entry.integrity !== actual",
        "test ! -e \"$TARGET\"",
        "test ! -L \"$TARGET\"",
        "backend/scripts/frfinance_m37979_termux_frontend.sh",
        "src/tests/m39083_cycle_readiness_ui_ci.test.ts",
        "src/tests/m39076_tenant_campaigns_navigation_ci.test.ts",
        "src/tests/m39020_credit_push_ui_ci.test.ts",
        "M39084_SQL_MIGRATIONS=NONE",
        "M39084_DATABASE_WRITES=NONE",
        "M39084_PIX_REAL=OFF",
        "M39084_ACTIVATION_REAL=OFF",
    ):
        assert required in s, required
    for forbidden in (
        "npm ci", "npm install", "npm audit fix", "git reset", "git clean",
        "git push", "psql ", "pg_restore ", "oci compute", "FR_FINANCE_PIX_REAL=true",
        "package-lock.json >",
    ):
        assert forbidden not in s, forbidden


def test_package_lock_has_the_exact_missing_dependency():
    import json
    pkg = json.loads((ROOT / "package.json").read_text())
    lock = json.loads((ROOT / "package-lock.json").read_text())
    assert pkg["dependencies"]["@capacitor/push-notifications"] == "8.1.2"
    assert lock["packages"][""]["dependencies"]["@capacitor/push-notifications"] == "8.1.2"
    entry = lock["packages"]["node_modules/@capacitor/push-notifications"]
    assert entry["version"] == "8.1.2"
    assert entry["integrity"].startswith("sha512-")


def test_recovery_will_not_modify_business_logic():
    s = SCRIPT.read_text()
    assert "src/services/specialCreditPushNative.ts" not in s
    assert "backend/app/routers/special_credit.py" not in s
    assert "node_modules/@capacitor/push-notifications" in s
    assert "M39084_OFFICIAL_TS7_CI=NOT_REPLACED" in s
