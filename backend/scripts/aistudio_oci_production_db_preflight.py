#!/usr/bin/env python3
"""Optional OCI runtime-only DB read-only preflight."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.oci_production_db_preflight import main
if __name__=="__main__":
    raise SystemExit(main())
