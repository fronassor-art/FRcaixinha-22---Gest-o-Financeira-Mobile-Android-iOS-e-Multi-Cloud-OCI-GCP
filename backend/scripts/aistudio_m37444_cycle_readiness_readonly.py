#!/usr/bin/env python3
"""Read-only M37444 opening readiness, existing PG18 only."""
from __future__ import annotations
import getpass,os
from app.dev_m37444_cycle_readiness import CycleReadinessBlocked,examine,report
def main():
    try:
        if os.getenv("FR_FINANCE_CYCLE_OPEN_ENABLED")=="YES":
            raise CycleReadinessBlocked("CYCLE_OPEN_FLAG_MUST_REMAIN_OFF")
        if os.getenv("FR_FINANCE_PIX_REAL")=="ON":
            raise CycleReadinessBlocked("REAL_PIX_MUST_REMAIN_OFF")
        if os.getenv("FR_FINANCE_REAL_USER_ACTIVATION")=="ON":
            raise CycleReadinessBlocked("REAL_USER_ACTIVATION_MUST_REMAIN_OFF")
        import psycopg
        pw=getpass.getpass("Senha PostgreSQL local (oculta): ")
        if not pw:raise CycleReadinessBlocked("PASSWORD_REQUIRED")
        try:
            with psycopg.connect(
                host="127.0.0.1",port=5433,dbname="frcaixinha_aistudio_dev",
                user="frc_ai_owner",password=pw,connect_timeout=5,
                options="-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=3000"
            ) as conn:
                del pw
                result=examine(conn)
        except CycleReadinessBlocked:raise
        except Exception:
            raise CycleReadinessBlocked("READ_ONLY_DATABASE_CONNECTION_FAILED") from None
        for line in report(result):print(line)
        return 0
    except CycleReadinessBlocked as exc:
        print("M37444_STATUS=BLOCKED")
        print("M37444_REASON="+str(exc))
        print("M37444_DB_WRITES=NONE")
        return 2
    except (EOFError,KeyboardInterrupt):
        print("M37444_STATUS=CANCELLED")
        print("M37444_DB_WRITES=NONE")
        return 2
    except Exception:
        print("M37444_STATUS=BLOCKED")
        print("M37444_REASON=LOCAL_RUNTIME_FAILED")
        print("M37444_DB_WRITES=NONE")
        return 2
if __name__=="__main__":
    raise SystemExit(main())
