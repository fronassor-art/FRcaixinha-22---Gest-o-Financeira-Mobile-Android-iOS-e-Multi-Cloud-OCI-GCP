#!/usr/bin/env python3
"""M37450 original PG18 license inventory, zero database writes."""
from __future__ import annotations
import getpass,os
from app.dev_m37450_license_inventory import LicenseInventoryBlocked,examine,report

def main():
 try:
  for name in ("FR_FINANCE_PIX_REAL","FR_FINANCE_REAL_USER_ACTIVATION",
      "FR_FINANCE_CYCLE_OPEN_ENABLED"):
   if os.environ.get(name,"OFF") in ("ON","YES","true","1"):
    raise LicenseInventoryBlocked("REAL_OPERATION_FLAG_ENABLED")
  import psycopg
  password=getpass.getpass("Senha PostgreSQL local (oculta): ")
  if not password:raise LicenseInventoryBlocked("PASSWORD_REQUIRED")
  try:
   with psycopg.connect(
    host="127.0.0.1",port=5433,dbname="frcaixinha_aistudio_dev",
    user="frc_ai_owner",password=password,connect_timeout=5,
    options="-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=3000"
   ) as conn:
    del password
    evidence=examine(conn)
  except LicenseInventoryBlocked:raise
  except Exception:raise LicenseInventoryBlocked("LOCAL_POSTGRES_READ_FAILED") from None
  for line in report(evidence):print(line)
  return 0
 except LicenseInventoryBlocked as exc:
  print("M37450_STATUS=BLOCKED")
  print("M37450_REASON="+str(exc))
  print("M37450_DB_WRITES=NONE")
  return 2
 except (KeyboardInterrupt,EOFError):
  print("M37450_STATUS=CANCELLED")
  print("M37450_DB_WRITES=NONE")
  return 2
 except Exception:
  print("M37450_STATUS=BLOCKED")
  print("M37450_REASON=LOCAL_RUNTIME_ERROR")
  print("M37450_DB_WRITES=NONE")
  return 2

if __name__=="__main__":raise SystemExit(main())
