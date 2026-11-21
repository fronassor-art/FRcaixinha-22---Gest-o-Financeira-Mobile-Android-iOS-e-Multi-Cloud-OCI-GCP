"""M19300: exact body parity, destructive primitives forbidden and installer guard."""
from pathlib import Path
import subprocess
import pytest
ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize("n,anchor",[
 ("028","CREATE TABLE public.member_lifecycle_requests"),
 ("029","ALTER TABLE public.member_lifecycle_requests"),
 ("030","DROP INDEX IF EXISTS public.member_lifecycle_one_pending_per_cycle_kind"),
])
def test_local_ddl_fork_only_adds_environment_guard(n,anchor):
 src=next((ROOT/"backend/migrations").glob(n+"_*.sql")).read_text()
 local=next((ROOT/"backend/local_migrations").glob(n+"_*.sql")).read_text()
 assert "DO $local_migration_guard$" in local
 assert "current_database()='frcaixinha_aistudio_dev'" in local
 assert "inet_server_port()=5433" in local
 assert "frcaixinha.lifecycle_local_ci" in local
 assert "current_database()='frcaixinha_ci'" in local
 assert local[local.index(anchor):]==src[src.index(anchor):]
 for forbidden in ("UPDATE public.memberships","DELETE FROM public.memberships",
                   "INSERT INTO public.ledger_entries","UPDATE public.ledger_accounts"):
  assert forbidden not in local

def test_local_installer_guard_and_backup_precede_transaction():
 path=ROOT/"backend/scripts/aistudio_lifecycle_local_028_030.sh"
 subprocess.run(["bash","-n",str(path)],check=True)
 r=subprocess.run(["bash",str(path),"audit"],capture_output=True,text=True,timeout=20)
 assert r.returncode!=0
 assert "M19300_BLOQUEADO" in r.stderr
 s=path.read_text()
 for required in ("AI_STUDIO_APPROVED_SHA","AUTORIZO_CICLO_SINTETICO_028_030",
   "AI_STUDIO_APPLY_LIFECYCLE_028_030","pg_dump","age --passphrase",
   "age --decrypt","pg_restore --list","M19300_BACKUP_VERIFIED=PASS",
   "--single-transaction","M19300_MIGRATIONS_028_030_APPLIED=PASS",
   "M19300_POST_VERIFY=PASS","BEGIN READ ONLY","frcaixinha_aistudio_pg18"):
  assert required in s,required
 assert s.index("M19300_BACKUP_VERIFIED=PASS")<s.index("--single-transaction")
 assert "backend/ci_migrations/" not in s
 assert "backend/staging_migrations/" not in s
 assert "DROP DATABASE" not in s
