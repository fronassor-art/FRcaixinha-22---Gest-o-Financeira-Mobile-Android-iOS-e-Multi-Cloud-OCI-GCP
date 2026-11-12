"""M39020 — handoff Termux is separately gated, never run by CI."""
from pathlib import Path
import json
import re
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/"backend"


def test_sql_110_111_require_explicit_atomic_gate_and_are_registered():
    manifest=json.loads((BACKEND/"migration_catalog_ai_studio.json").read_text())
    for number in ("110","111"):
        e=next(x for x in manifest["entries"] if x["id"]=="migrations:"+number)
        assert e["classification"]=="LOCAL_CANDIDATE_REQUIRES_PROOF"
        assert e["local_evidence"] is None
        sql=(ROOT/e["source_path"]).read_text()
        assert "frfinance.m39020_migration_mode" in sql
        assert "CI_DISPOSABLE" in sql and "LOCAL_AUTHORIZED" in sql
        assert "frcaixinha_aistudio_dev" in sql
        assert "frc_ai_owner" in sql
        assert not re.search(r"(?m)^\s*BEGIN\s*;\s*$",sql)
        assert not re.search(r"(?m)^\s*COMMIT\s*;\s*$",sql)
        assert "money_out" not in sql.lower()
        assert "pix_real=on" not in sql.lower()


def test_atomic_apply_is_not_called_by_preflight():
    pre=(BACKEND/"scripts/frfinance_m39020_termux_preflight.sh").read_text()
    for forbidden in ("--single-transaction","pg_dump --format","createdb ","git pull","git merge","psql -f"):
        assert forbidden not in pre
    assert "local-readonly" in pre
    assert "AI_STUDIO_APPROVED_SHA" in pre
    assert "M39020_DATABASE_MIGRATIONS=NONE" in pre


def test_atomic_apply_requires_specific_consent_backup_restore_and_sha():
    script=(BACKEND/"scripts/frfinance_m39020_termux_apply_guarded.sh").read_text()
    assert "YES_AFTER_INDEPENDENT_REVIEW" in script
    assert "FR_FINANCE_M39020_RESTORE_TEST" in script
    assert "AI_STUDIO_APPROVED_SHA" in script
    assert "pg_dump --format=custom" in script
    assert "pg_restore --exit-on-error" in script
    assert "--single-transaction" in script
    assert "frfinance.m39020_migration_mode='LOCAL_AUTHORIZED'" in script
    assert "backend/migrations/110_fr_finance_special_credit_offline.sql" in script
    assert "backend/migrations/111_frfinance_special_credit_integrity_guards.sql" in script
    assert "M39020_PIX_REAL=OFF" in script
    for shell in ("frfinance_m39020_termux_preflight.sh",
                  "frfinance_m39020_termux_apply_guarded.sh"):
        subprocess.run(["bash","-n",str(BACKEND/"scripts"/shell)],
                       check=True,capture_output=True,text=True)
