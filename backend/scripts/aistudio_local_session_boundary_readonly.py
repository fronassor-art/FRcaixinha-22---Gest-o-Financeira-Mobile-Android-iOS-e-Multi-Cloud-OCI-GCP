#!/usr/bin/env python3
"""M37420 — localhost GET-only denial probe: NEVER send an actual bearer token."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.local_session_boundary_readonly import (
    SessionBoundaryBlocked,local_request,assess_session_boundaries,
    format_session_boundary,
)

def main()->int:
    try:
        report=assess_session_boundaries(local_request)
        out=format_session_boundary(report)
    except SessionBoundaryBlocked as exc:
        print("M37420_STATUS=BLOCKED")
        print("M37420_CAUSE="+str(exc))
        print("M37420_SQL_WRITES_REQUESTED=NO")
        print("M37420_REAL_USER_ACTIVATION=OFF")
        print("M37420_PIX_REAL=OFF")
        return 2
    for line in out:
        print(line)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
