"""M21100 - safe Termux installer; no implicit DB changes in CI."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[2]
def test_installer_fail_closed_and_syntax():
 p=ROOT/"backend/scripts/aistudio_cycle_open_044.sh"
 r=subprocess.run(["bash","-n",str(p)],capture_output=True,text=True)
 assert r.returncode==0,r.stderr
 s=p.read_text()
 for x in ("AI_STUDIO_APPROVED_SHA","M21100_BLOQUEADO",
  "pg_isready","frcaixinha_aistudio_pg18","AUTORIZO_ABERTURA_CICLO_044",
  "AI_STUDIO_APPROVE_CYCLE_044","age --passphrase","age --decrypt",
  "pg_restore --list","M21100_BACKUP_VERIFIED=PASS",
  "044_cycle_opening_audit.sql","--single-transaction",
  "M21100_LOCAL_044_VERIFY=PASS"):
  assert x in s,x
 assert "staging_migrations/" not in s
 fail=subprocess.run(["bash",str(p),"audit"],capture_output=True,text=True,timeout=15)
 assert fail.returncode!=0 and "M21100_BLOQUEADO" in fail.stderr
