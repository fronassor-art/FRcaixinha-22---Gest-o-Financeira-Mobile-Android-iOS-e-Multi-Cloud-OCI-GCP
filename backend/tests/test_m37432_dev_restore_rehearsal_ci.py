"""CI for M37432 isolated restore rehearsal safeguards; never invoke database."""
from pathlib import Path
import subprocess
P=Path(__file__).resolve().parents[2]/"backend/scripts/aistudio_dev_restore_rehearsal.sh"
def test_shell_syntax_and_fail_closed():
 assert subprocess.run(["bash","-n",str(P)],capture_output=True).returncode==0
 x=subprocess.run(["bash",str(P)],capture_output=True,text=True,timeout=8)
 assert x.returncode==2 and "M37432_BLOCKED" in x.stderr
def test_original_db_never_targeted():
 s=P.read_text()
 assert 'database="frcaixinha_aistudio_dev"' in s
 assert 'scratch="frfinance_restore_check_m37432"' in s
 for term in ("FR_FINANCE_BACKUP_SHA256","FR_FINANCE_APPROVED_SHA",
              "BACKUP_INTEGRITY_MISMATCH","SCRATCH_ALREADY_EXISTS_NO_OVERWRITE",
              "AUTORIZO_ENSAIO_M37432","M37432_FULL_RESTORE=PASS",
              "M37432_ORIGINAL_DB_WRITES=NO","M37432_DISPOSABLE_CLEANUP=PASS",
              "age --decrypt","pg_restore --no-password","--single-transaction",
              "createdb -w","dropdb -w","umask 077"):
  assert term in s,term
 assert s.index('if [[ "$mode" == preflight ]]') < s.index("createdb -w")
 for unsafe in ("DROP DATABASE frcaixinha_aistudio_dev",
                "TRUNCATE ","DELETE FROM public.","UPDATE public.",
                "pg_restore -d frcaixinha_aistudio_dev"):
  assert unsafe not in s
