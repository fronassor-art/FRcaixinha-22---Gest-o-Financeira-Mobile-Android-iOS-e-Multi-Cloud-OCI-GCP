"""M37431 static checks: backup-only, encrypted, isolated and fail-closed."""
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
P=ROOT/"backend/scripts/aistudio_dev_clean_backup.sh"
def test_shell_syntax_and_invalid_mode_fail_closed():
 assert subprocess.run(["bash","-n",str(P)],capture_output=True).returncode==0
 r=subprocess.run(["bash",str(P)],capture_output=True,text=True,timeout=10)
 assert r.returncode==2 and "M37431_BLOCKED" in r.stderr
def test_backup_safeguards():
 s=P.read_text()
 for x in ("umask 077","pg_isready","FR_FINANCE_APPROVED_SHA",
 "pg_dump -w","age --passphrase","age --decrypt","pg_restore --list",
 "AUTORIZO_BACKUP_DEV_CIFRADO","ISOLATED_LOCAL_DB_MISMATCH",
 "M37431_FULL_RESTORE=NOT_TESTED","M37431_DEV_RESET=NOT_EXECUTED",
 "M37431_DB_WRITES=NONE"):
  assert x in s,x
 assert s.index('if [[ "$mode" == "audit" ]]')<s.index("pg_dump -w")
 for forbidden in ("DROP DATABASE","DROP SCHEMA","TRUNCATE ","DELETE FROM ",
                   "UPDATE public.","ALTER TABLE ","CREATE DATABASE","pg_restore -d"):
  assert forbidden not in s,forbidden
 assert 'role="frc_ai_owner"' in s
 assert 'database="frcaixinha_aistudio_dev"' in s
 assert 'pgdata="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"' in s
