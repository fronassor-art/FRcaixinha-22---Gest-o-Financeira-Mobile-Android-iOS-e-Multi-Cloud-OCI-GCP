"""M37433 static protections: schema-only, no old data or database cutover."""
from pathlib import Path
import subprocess
SCRIPT=Path(__file__).resolve().parents[2]/"backend/scripts/aistudio_clean_dev_schema_isolated.sh"
def test_shell_syntax_and_invalid_mode():
 assert subprocess.run(["bash","-n",str(SCRIPT)],capture_output=True).returncode==0
 x=subprocess.run(["bash",str(SCRIPT)],capture_output=True,text=True,timeout=8)
 assert x.returncode==2 and "M37433_BLOCKED" in x.stderr
def test_only_new_fixed_database_and_schema_no_data():
 s=SCRIPT.read_text()
 assert 'source_db="frcaixinha_aistudio_dev"' in s
 assert 'target_db="frfinance_clean_dev_m37433"' in s
 for text in ("TARGET_EXISTS_NO_OVERWRITE","SOURCE_DB_IDENTITY_MISMATCH",
              "BACKUP_SHA_MISMATCH","AUTORIZO_BASE_LIMPA_M37433",
              "REVOKE ALL ON DATABASE","--schema-only","--no-owner --no-acl",
              "--exit-on-error --single-transaction","M37433_EMPTY_IDENTITIES=PASS",
              "M37433_EMPTY_FINANCIAL_HISTORY=PASS",
              "M37433_BACKEND_CUTOVER=NOT_AUTHORIZED","M37433_ORIGINAL_DB_WRITES=NO"):
  assert text in s,text
 assert s.index('if [[ "$mode" == "preflight" ]]') < s.index("createdb -w")
 for denied in ("DROP DATABASE frcaixinha_aistudio_dev","TRUNCATE ","DELETE FROM public.",
                "UPDATE public.","pg_restore -d frcaixinha_aistudio_dev","--data-only"):
  assert denied not in s,denied
