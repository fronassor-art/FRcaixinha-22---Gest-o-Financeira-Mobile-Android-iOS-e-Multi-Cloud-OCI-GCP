"""M37438: no new local DB, CI-only transactional rehearsal with ROLLBACK."""
from pathlib import Path
import subprocess,os
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/aistudio_m37438_disposable_ci_sql.py"
def test_assembler_refuses_untrusted_context():
 x=subprocess.run(["python",str(SCRIPT)],cwd=ROOT,
    env={"PATH":os.getenv("PATH","")},capture_output=True,text=True)
 assert x.returncode==2
 assert "DISPOSABLE_POSTGRES18_CI_ONLY" in x.stderr
def test_candidate_ci_boundary_and_rollback_only():
 sql=(ROOT/"backend/scripts/aistudio_dev_price_fixture_reset_candidate.sql").read_text()
 asm=SCRIPT.read_text()
 seed=(ROOT/"backend/tests/sql/m37438_seed_disposable_ci.sql").read_text()
 post=(ROOT/"backend/tests/sql/m37438_assert_disposable_ci.sql").read_text()
 assert "frfinance.m37437_ci_disposable" in sql
 assert "current_database()='frcaixinha_ci'" in sql
 assert "session_user='postgres'" in sql
 for k in ("FRCAIXINHA_CI_ISOLATED","PGDATABASE","GITHUB_ACTIONS",
           "PGPORT","DISPOSABLE_POSTGRES18_CI_ONLY","ROLLBACK;"):
  assert k in asm
 assert "DROP CONSTRAINT policy_minimum_150_new" in seed
 assert "ADD CONSTRAINT policy_minimum_150_new" in seed
 assert "ADD CONSTRAINT quota_minimum_150_new" in seed
 assert "generate_series(1,12)" in seed
 assert "2027" in seed and "100.00" in seed
 assert "M37438_REAL_POSTGRESQL18_SYNTHETIC_CLEANUP_BEFORE_ROLLBACK=PASS" in post
def test_assembled_output_has_no_commit_or_new_database():
 env={**os.environ,"GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
 "PGDATABASE":"frcaixinha_ci","PGUSER":"postgres","PGPORT":"5432"}
 x=subprocess.run(["python",str(SCRIPT)],cwd=ROOT,env=env,
 capture_output=True,text=True,check=True)
 assert x.stdout.startswith("BEGIN;")
 assert x.stdout.rstrip().endswith("ROLLBACK;")
 assert "COMMIT;" not in x.stdout
 assert "CREATE DATABASE" not in x.stdout
 assert "DROP DATABASE" not in x.stdout
