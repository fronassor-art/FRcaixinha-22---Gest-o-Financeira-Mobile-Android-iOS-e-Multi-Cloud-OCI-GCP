#!/usr/bin/env python3
"""Only SELECT on the ORIGINAL isolated Termux PG18 database."""
import getpass,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.local_pg18_evidence_readonly import DBNAME,PGDATA,PORT,ROLE,IDENTITY_SQL
from app.dev_legacy_dependency_readonly import DependencyBlocked,examine,report
def main():
 try:
  import psycopg
  password=getpass.getpass("Senha PostgreSQL local (oculta): ")
  if not password: raise DependencyBlocked("LOCAL_PASSWORD_MISSING")
  try:
   with psycopg.connect(host="127.0.0.1",port=PORT,dbname=DBNAME,
    user=ROLE,password=password,connect_timeout=5,
    options="-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=3000") as conn:
    del password
    ident=conn.execute(IDENTITY_SQL).fetchone()
    if (not isinstance(ident,tuple) or len(ident)!=6
      or ident[0]!=DBNAME or ident[1]!=ROLE or type(ident[2]) is not int or ident[2]!=PORT
      or type(ident[3]) is not int or not 180000<=ident[3]<190000
      or ident[4]!=PGDATA or ident[5]!="on"):
     raise DependencyBlocked("LOCAL_PG18_IDENTITY_DENIED")
    evidence=examine(conn)
  except DependencyBlocked:raise
  except Exception:raise DependencyBlocked("LOCAL_READ_FAILED") from None
  for line in report(evidence):print(line)
  return 0
 except DependencyBlocked as exc:
  print("M37435_STATUS=BLOCKED")
  print("M37435_REASON="+str(exc))
  print("M37435_DB_WRITES=NONE")
  return 2
 except Exception:
  print("M37435_STATUS=BLOCKED")
  print("M37435_REASON=LOCAL_RUNTIME_FAILED")
  print("M37435_DB_WRITES=NONE")
  return 2
if __name__=="__main__":raise SystemExit(main())
