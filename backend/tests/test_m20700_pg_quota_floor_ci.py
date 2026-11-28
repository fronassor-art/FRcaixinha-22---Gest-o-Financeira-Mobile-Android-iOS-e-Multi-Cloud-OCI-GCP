"""M20700 prepared SQL floor, CI and Termux script cannot apply by accident."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[2]
def test_staged_043_guard_and_legacy_preservation():
    sql=(ROOT/"backend/local_migrations/043_cycle_contribution_contract_minimum.sql").read_text()
    for term in ("M20700 wrong PG18","quota_floor_local_ci","ALTER COLUMN contribution_per_quota DROP DEFAULT",
      "ALTER COLUMN value_brl DROP DEFAULT","NOT VALID","150.00","BETWEEN 15000 AND 1000000",
      "cycle_price_change_legacy_m20400","REVOKE ALL ON FUNCTION","frcaixinha_aistudio_dev"):
      assert term in sql,term
    for illegal in ("UPDATE public.contributions","DELETE FROM public.contributions",
      "UPDATE public.quotas SET","TRUNCATE public.quotas","INSERT INTO public.ledger"):
      assert illegal not in sql
def test_incremental_043_installer_fail_closed():
    p=ROOT/"backend/scripts/aistudio_cycle_price_043.sh"
    assert subprocess.run(["bash","-n",str(p)],capture_output=True).returncode==0
    s=p.read_text()
    for term in ("AI_STUDIO_APPROVED_SHA","AUTORIZO_MINIMO_COTA_043",
       "pg_dump","age --passphrase","age --decrypt","pg_restore --list",
       "--single-transaction","M20700_BACKUP_VERIFIED=PASS"):
       assert term in s,term
    assert "backend/migrations/001" not in s
