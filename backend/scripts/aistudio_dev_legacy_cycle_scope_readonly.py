#!/usr/bin/env python3
"""M37436: local dev financial scope evidence only; passwords never logged."""
import getpass,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.local_pg18_evidence_readonly import DBNAME,PGDATA,PORT,ROLE,IDENTITY_SQL
from app.dev_legacy_cycle_scope_readonly import CycleScopeBlocked,examine,report
def main():
 try:
  import psycopg
  password=getpass.getpass("Senha PostgreSQL local (oculta): ")
  if not password:raise CycleScopeBlocked("PASSWORD_REQUIRED")
  try:
   with psycopg.connect(
    host="127.0.0.1",port=PORT,dbname=DBNAME,user=ROLE,password=password,
    connect_timeout=5,options="-c default_transaction_read_only=on "
      "-c statement_timeout=15000 -c lock_timeout=3000",
   ) as conn:
    del password
    identity=conn.execute(IDENTITY_SQL).fetchone()
    if (not isinstance(identity,tuple) or len(identity)!=6 or
     identity[0]!=DBNAME or identity[1]!=ROLE or
     type(identity[2]) is not int or identity[2]!=PORT or
     type(identity[3]) is not int or not 180000<=identity[3]<190000 or
     identity[4]!=PGDATA or identity[5]!="on"):
     raise CycleScopeBlocked("LOCAL_PG18_IDENTITY_DENIED")
    evidence=examine(conn)
  except CycleScopeBlocked:raise
  except Exception:raise CycleScopeBlocked("DB_READ_FAILED") from None
  for item in report(evidence):print(item)
  return 0
 except CycleScopeBlocked as exc:
  print("M37436_STATUS=BLOCKED")
  print("M37436_REASON="+str(exc))
  print("M37436_DATABASE_WRITES=NONE")
  return 2
 except Exception:
  print("M37436_STATUS=BLOCKED")
  print("M37436_REASON=LOCAL_RUNTIME_FAILED")
  print("M37436_DATABASE_WRITES=NONE")
  return 2
if __name__=="__main__":raise SystemExit(main())
