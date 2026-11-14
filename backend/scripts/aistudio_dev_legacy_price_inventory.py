#!/usr/bin/env python3
"""M37425: SQL counts only on isolated Termux PG18, secret never displayed."""
import getpass
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.dev_legacy_amount_audit import DevPriceAuditBlocked,inspect,report
from app.local_pg18_evidence_readonly import DBNAME,ROLE,PORT,PGDATA,IDENTITY_SQL

def main()->int:
 try:
  import psycopg
  pw=getpass.getpass("Senha PostgreSQL local (oculta): ")
  if not pw: raise DevPriceAuditBlocked("LOCAL_PASSWORD_ABSENT")
  try:
   with psycopg.connect(host="127.0.0.1",port=PORT,dbname=DBNAME,
    user=ROLE,password=pw,connect_timeout=5,
    options="-c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=2000") as conn:
    del pw
    identity=conn.execute(IDENTITY_SQL).fetchone()
    if (not isinstance(identity,tuple) or len(identity)!=6 or
     identity[0]!=DBNAME or identity[1]!=ROLE or identity[2]!=PORT or
     type(identity[3]) is not int or not 180000<=identity[3]<190000 or
     identity[4]!=PGDATA or identity[5]!="on"):
     raise DevPriceAuditBlocked("LOCAL_PG18_IDENTITY_INVALID")
    def scalar(q):
     row=conn.execute(q).fetchone()
     if row is None or len(row)!=1:
      raise DevPriceAuditBlocked("LOCAL_CATALOG_ROW_INVALID")
     return row[0]
    result=inspect(scalar)
  except DevPriceAuditBlocked:
   raise
  except Exception:
   raise DevPriceAuditBlocked("LOCAL_CONNECTION_OR_QUERY_FAILED") from None
  for line in report(result): print(line)
  return 0
 except DevPriceAuditBlocked as exc:
  print("M37425_STATUS=BLOCKED")
  print("M37425_REASON="+str(exc))
  print("M37425_DB_WRITES=NO")
  return 2
 except Exception:
  print("M37425_STATUS=BLOCKED")
  print("M37425_REASON=LOCAL_RUNTIME_FAILED")
  print("M37425_DB_WRITES=NO")
  return 2

if __name__=="__main__":
 raise SystemExit(main())
