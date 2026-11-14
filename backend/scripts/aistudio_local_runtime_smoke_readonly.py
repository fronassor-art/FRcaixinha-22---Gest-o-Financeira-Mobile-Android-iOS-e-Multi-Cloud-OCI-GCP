#!/usr/bin/env python3
"""FR Finance M37400 — read-only localhost FastAPI smoke, no credentials."""
from __future__ import annotations
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.local_runtime_smoke_readonly import (
    LocalSmokeBlocked,check_local_smoke,format_smoke,local_get,
)

def main()->int:
    try:
        report=check_local_smoke(local_get)
        lines=format_smoke(report)
    except LocalSmokeBlocked as exc:
        print("M37400_SMOKE=BLOCKED")
        print("M37400_REASON="+str(exc))
        print("M37400_HTTP_METHODS=GET_ONLY")
        print("M37400_DB_WRITES=NONE")
        print("M37400_PIX_REAL=OFF")
        print("M37400_REAL_USER_ACTIVATION=OFF")
        return 2
    for item in lines:
        print(item)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
