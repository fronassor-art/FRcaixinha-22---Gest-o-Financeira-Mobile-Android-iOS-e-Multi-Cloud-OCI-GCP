#!/usr/bin/env python3
"""Build only a disposable CI PG18 ROLLBACK-only migration rehearsal script."""
from pathlib import Path
import os,sys
def main()->int:
 required={
  "GITHUB_ACTIONS":"true",
  "FRCAIXINHA_CI_ISOLATED":"1",
  "PGDATABASE":"frcaixinha_ci",
  "PGUSER":"postgres",
  "PGPORT":"5432",
 }
 if any(os.getenv(k)!=v for k,v in required.items()):
  print("M37438_BLOCKED=DISPOSABLE_POSTGRES18_CI_ONLY",file=sys.stderr)
  return 2
 root=Path(__file__).resolve().parents[2]
 script=(root/"backend/scripts/aistudio_dev_price_fixture_reset_candidate.sql").read_text()
 start="\nBEGIN;\n"
 end="\nCOMMIT;\n"
 if script.count(start)!=1 or script.count(end)!=1 or not script.endswith(end):
  print("M37438_BLOCKED=MIGRATION_TRANSACTION_MARKERS_CHANGED",file=sys.stderr)
  return 2
 candidate=script.split(start,1)[1].removesuffix(end)
 if "COMMIT;" in candidate or "ROLLBACK;" in candidate:
  print("M37438_BLOCKED=NESTED_TRANSACTION_CHANGED",file=sys.stderr)
  return 2
 pre=(root/"backend/tests/sql/m37438_seed_disposable_ci.sql").read_text()
 post=(root/"backend/tests/sql/m37438_assert_disposable_ci.sql").read_text()
 sys.stdout.write(
  "BEGIN;\nSET LOCAL lock_timeout='5000ms';\n"+
  pre+"\n"+candidate+"\n"+post+"\nROLLBACK;\n"
 )
 return 0
if __name__=="__main__":raise SystemExit(main())
