#!/usr/bin/env python3
"""M40570: show untrusted SQL GUC spoof boundary on disposable PG18 ONLY.

This is a negative security finding, not a hardening or production clearance.
No original FR Finance database, Termux, provider or real credentials.
"""
from __future__ import annotations

import os
import sys


def require_disposable() -> None:
    """Before importing psycopg or opening a connection, fail closed outside CI."""
    if (os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("CI_M40570_DISPOSABLE") != "1"
        or os.environ.get("CI_M40560_DISPOSABLE") != "1"
        or os.environ.get("FRCAIXINHA_CI_ISOLATED") != "1"
        or os.environ.get("PIX_REAL") != "OFF"
        or os.environ.get("PAGAMENTOS_REAIS") != "OFF"
        or os.environ.get("ATIVACAO_REAL") != "OFF"):
        raise RuntimeError("M40570_DISPOSABLE_ONLY_GATE")


def reproduce(conn) -> None:
    """SQL-user-only manipulation after synthetic M40560 fixture has run.

    It does NOT bypass HTTP bearer authentication. It illustrates the
    assumption that the application DB role cannot execute arbitrary SQL.
    """
    from m40560_saas_role_dataplane_disposable import run as setup_synthetic
    setup_synthetic(conn)
    conn.execute("RESET ROLE")
    master = conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist"
    ).fetchone()[0]
    # Context resembles an unprivileged member in an already open SQL session.
    conn.execute("SELECT set_config('app.current_role','TENANT_MEMBER',false)")
    conn.execute("SELECT set_config('app.current_user_id','',false)")
    conn.execute("SELECT set_config('app.current_tenant_id','',false)")
    conn.execute("SET ROLE frcaixinha_app_role")
    assert conn.execute(
        "SELECT count(*) FROM public.platform_saas_promotion_revisions"
    ).fetchone()[0] == 0
    print("M40570_WITHOUT_MASTER_CONTEXT=RLS_DENY")

    # Only the low-privilege SQL application role now runs these commands.
    # PostgreSQL custom GUCs are ordinary user-settable session variables.
    conn.execute("SELECT set_config('app.current_role','MASTER',false)")
    conn.execute("SELECT set_config('app.current_user_id',%s,false)", (str(master),))
    visible = conn.execute(
        "SELECT count(*) FROM public.platform_saas_promotion_revisions"
    ).fetchone()[0]
    if visible <= 0:
        raise AssertionError("M40570_EXPECTED_TRUST_BOUNDARY_NOT_REPRODUCED")
    print("M40570_GUC_SPOOFING=EXPOSURE_REPRODUCED_DISPOSABLE")
    print("M40570_RLS_NOT_INDEPENDENT_AUTHENTICATOR=CONFIRMED")
    print("M40570_HTTP_BEARER_BYPASS=NOT_TESTED")
    print("M40570_GATE=NO_GO_UNTIL_SQL_ORIGIN_HARDENING_ATTESTED")


def main() -> int:
    try:
        require_disposable()
        from m40560_saas_role_dataplane_disposable import (
            require_disposable as verify_disposable_target,
        )
        verify_disposable_target()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            reproduce(conn)
    except Exception as exc:
        print("M40570_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40570_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40570_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M40570_LOCAL_SQL=NONE")
        print("M40570_LOCAL_MIGRATIONS=NONE")
        print("M40570_LOCAL_DB_WRITES=NONE")
        print("M40570_FASTAPI_RESTART=NONE")
        print("M40570_PIX_REAL=OFF")
        print("M40570_PAGAMENTOS_REAIS=OFF")
        print("M40570_ATIVACAO_REAL=OFF")
        print("M40570_PRODUCTION=BLOCKED")
    print("M40570_STATUS=PASS_EXPOSURE_DOCUMENTED_NOT_MITIGATED")
    return 0


if __name__ == "__main__":
    sys.exit(main())