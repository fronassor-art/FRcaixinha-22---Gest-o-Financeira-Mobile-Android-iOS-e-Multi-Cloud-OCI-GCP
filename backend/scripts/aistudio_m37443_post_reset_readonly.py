#!/usr/bin/env python3
"""Independent read-only original PostgreSQL 18 post-reset check."""
import getpass,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.dev_m37443_post_reset import AuditBlocked,examine,report
def main():
 try:
  import psycopg
  pw=getpass.getpass("Senha PostgreSQL local (oculta): ")
  if not pw:raise AuditBlocked("PASSWORD_MISSING")
  try:
   with psycopg.connect(
    host="127.0.0.1",port=5433,dbname="frcaixinha_aistudio_dev",
    user="frc_ai_owner",password=pw,connect_timeout=5,
    options="-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=3000"
   ) as conn:
    del pw
    evidence=examine(conn)
  except AuditBlocked:raise
  except Exception:raise AuditBlocked("LOCAL_PG18_READ_FAILED") from None
  for line in report(evidence):print(line)
  return 0
 except AuditBlocked as e:
  print("M37443_STATUS=BLOCKED")
  print("M37443_REASON="+str(e))
  print("M37443_DB_WRITES=NONE")
  return 2
 except (EOFError,KeyboardInterrupt):
  print("M37443_STATUS=CANCELLED")
  print("M37443_DB_WRITES=NONE")
  return 2
 except Exception:
  print("M37443_STATUS=BLOCKED")
  print("M37443_REASON=LOCAL_ENVIRONMENT_FAILURE")
  print("M37443_DB_WRITES=NONE")
  return 2
if __name__=="__main__":raise SystemExit(main())
