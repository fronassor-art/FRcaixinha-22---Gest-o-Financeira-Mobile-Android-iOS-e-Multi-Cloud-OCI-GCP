"""M19200 regression: no untracked DB migration or accidental OCI/CI apply."""
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def test_full_migration_catalog():
    data=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    entries=data["entries"]
    assert len(entries)>=82
    assert len({x["source_path"] for x in entries})==len(entries)
    c=lambda category:sum(x["classification"]==category for x in entries)
    assert c("BASELINE_LOCAL")==27
    assert c("APPLIED_LOCAL_EVIDENCE")==1
    assert c("CI_ONLY_NEEDS_PORT")==3
    assert c("STAGING_ONLY_NEEDS_PORT")>=16
    assert c("CI_ONLY_TEST_OR_FIXTURE")>=21
    assert c("LOCAL_CANDIDATE_REQUIRES_PROOF")==19
    candidate = next(e for e in entries if e["id"]=="migrations:110")
    assert candidate["source_path"]=="backend/migrations/110_fr_finance_special_credit_offline.sql"
    assert candidate["local_evidence"] is None
    assert candidate["classification"]=="LOCAL_CANDIDATE_REQUIRES_PROOF"
    assert candidate["do_not_apply_source_to_termux"] is False
    assert candidate["requires_local_equivalent_before_use"] is False
    assert all(x["do_not_apply_source_to_termux"]
               for x in entries if x["source_path"].startswith("backend/staging_migrations/"))

def test_repo_gate_pass_and_local_gate_fails_closed():
    path=ROOT/"backend/scripts/aistudio_migration_inventory.py"
    p=subprocess.run([sys.executable,str(path),"repo-check"],capture_output=True,text=True,timeout=20)
    assert p.returncode==0,(p.stdout,p.stderr)
    assert "M19200_REGISTRY_HASHES=PASS" in p.stdout
    assert f"M19200_MIGRATION_SQL_COUNT={len(json.loads((ROOT / 'backend/migration_catalog_ai_studio.json').read_text())['entries'])}" in p.stdout
    assert "M19200_NEEDS_LOCAL_EQUIVALENT=0" in p.stdout
    assert "M20100_SOURCE_LOCAL_034_041=VERSIONED_DB_VERIFICATION_REQUIRED" in p.stdout
    assert "M19300_SOURCE_LOCAL_028_030=VERSIONED_DB_VERIFICATION_REQUIRED" in p.stdout
    # Deterministic negative gate: deliberately wrong approved SHA must block
    # BEFORE getpass/DB access, even when Termux has a real local database.
    # Never allow automated pytest to prompt for frc_ai_owner credentials.
    env={**os.environ, "AI_STUDIO_APPROVED_SHA":"0"*40}
    q=subprocess.run(
        [sys.executable,str(path),"local-readonly"],
        stdin=subprocess.DEVNULL,capture_output=True,text=True,
        timeout=10,env=env,
    )
    assert q.returncode!=0
    assert "M19200_BLOQUEADO" in q.stderr
    assert "Senha frc_ai_owner" not in q.stderr+q.stdout
    assert "SET TRANSACTION READ ONLY" in path.read_text()


def test_inventory_local_runtime_verifies_core_structures_and_m21000_extension():
    src=(ROOT/"backend/scripts/aistudio_migration_inventory.py").read_text()
    for term in (
        'M20200_LOCAL_028_030=OBJECTS_RLS_VERIFIED',
        'M20200_LOCAL_031=OBJECTS_RLS_VERIFIED',
        'M20200_LOCAL_034_041=8_TABLES_RLS_VERIFIED',
        'M20200_MIGRATIONS=',
        "if n not in (44,45,46,47,53):",
        "M39010_LOCAL_110=STRUCTURAL_PRESENT_NO_EXTERNAL_DISPATCH",
        "M39010_LOCAL_110=NOT_APPLIED",
        "special_credit_outbox",
        "M21000_LOCAL_044=OBJECTS_AND_ROLE_BOUNDARY_VERIFIED",
        "M38990_LOCAL_047=STRUCTURAL_PRESENT_NO_DELIVERY_ATTESTATION",
        "M38993_LOCAL_048=FUNCTIONS_AND_ROLE_BOUNDARY_PRESENT",
        "local_m041_notification_outbox",
        "local_m040_immutable_truncate",
        "has_table_privilege('frc_ai_auth'",
        'SET TRANSACTION READ ONLY',
    ):
        assert term in src,term
    assert "PREPARED_NOT_APPLIED" not in src
