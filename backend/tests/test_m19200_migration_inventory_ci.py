"""M19200 regression: no untracked DB migration or accidental OCI/CI apply."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def test_full_migration_catalog():
    data=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    entries=data["entries"]
    assert len(entries)==57
    assert len({x["source_path"] for x in entries})==57
    c=lambda category:sum(x["classification"]==category for x in entries)
    assert c("BASELINE_LOCAL")==27
    assert c("APPLIED_LOCAL_EVIDENCE")==1
    assert c("CI_ONLY_NEEDS_PORT")==3
    assert c("STAGING_ONLY_NEEDS_PORT")==8
    assert c("CI_ONLY_TEST_OR_FIXTURE")==7
    assert c("LOCAL_CANDIDATE_REQUIRES_PROOF")==11
    assert all(x["do_not_apply_source_to_termux"]
               for x in entries if x["source_path"].startswith("backend/staging_migrations/"))

def test_repo_gate_pass_and_local_gate_fails_closed():
    path=ROOT/"backend/scripts/aistudio_migration_inventory.py"
    p=subprocess.run([sys.executable,str(path),"repo-check"],capture_output=True,text=True,timeout=20)
    assert p.returncode==0,(p.stdout,p.stderr)
    assert "M19200_REGISTRY_HASHES=PASS" in p.stdout
    assert "M19200_MIGRATION_SQL_COUNT=57" in p.stdout
    assert "M19200_NEEDS_LOCAL_EQUIVALENT=0" in p.stdout
    assert "M20100_LOCAL_034_041=PREPARED_NOT_APPLIED" in p.stdout
    assert "M19300_LOCAL_028_030=PREPARED_NOT_APPLIED" in p.stdout
    q=subprocess.run([sys.executable,str(path),"local-readonly"],capture_output=True,text=True,timeout=20)
    assert q.returncode!=0
    assert "M19200_BLOQUEADO" in q.stderr
    assert "SET TRANSACTION READ ONLY" in path.read_text()
