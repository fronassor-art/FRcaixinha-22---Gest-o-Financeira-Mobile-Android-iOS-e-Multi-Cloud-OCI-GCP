#!/usr/bin/env python3
"""M40630: disposable-only audit of SQL roles, ACL, RLS and forged GUC boundary.

No original PostgreSQL or Termux connection. The synthetic PG18 database is
deliberately isolated in GitHub Actions, and production remains NO-GO.
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlsplit

EXPECTED_DB = "fr_m39067_disposable_ci"
EXPECTED_PORT = 55433


def require_disposable() -> None:
    for k, v in {
        "GITHUB_ACTIONS": "true",
        "CI_M40630_DISPOSABLE": "1",
        "CI_M40560_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }.items():
        if os.environ.get(k) != v:
            raise RuntimeError("M40630_DISPOSABLE_ONLY")
    try:
        url = urlsplit(os.environ.get("CI_PROMOTIONS_DATABASE_URL", ""))
        if (
            url.scheme != "postgresql"
            or url.hostname != "127.0.0.1"
            or url.port != EXPECTED_PORT
            or url.path != "/" + EXPECTED_DB
            or url.username != "postgres"
            or not url.password
            or url.query or url.fragment
        ):
            raise RuntimeError("M40630_WRONG_DATABASE_IDENTITY")
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("M40630_WRONG_DATABASE_IDENTITY") from exc


def audit(conn) -> None:
    from m40560_saas_role_dataplane_disposable import run as bootstrap_synthetic

    bootstrap_synthetic(conn)
    conn.execute("RESET ROLE")
    app, auth = "frcaixinha_app_role", "frcaixinha_auth_role"
    roles = conn.execute(
        "SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolcanlogin "
        "FROM pg_catalog.pg_roles WHERE rolname IN (%s,%s)",
        (app, auth),
    ).fetchall()
    assert len(roles) == 2
    for name, superuser, bypass, create_role, create_db, can_login in roles:
        assert not any((superuser, bypass, create_role, create_db, can_login)), name
    print("M40630_SYNTHETIC_ROLES_LEAST_PRIVILEGE=PASS")

    table = "public.platform_saas_promotion_revisions"
    rls = conn.execute(
        "SELECT relrowsecurity,relforcerowsecurity FROM pg_catalog.pg_class "
        "WHERE oid=%s::regclass",
        (table,),
    ).fetchone()
    assert rls == (True, True)
    print("M40630_SYNTHETIC_RLS_FORCED=PASS")

    def can_table(role: str, privilege: str) -> bool:
        return conn.execute(
            "SELECT has_table_privilege(%s,%s,%s)",
            (role,table,privilege),
        ).fetchone()[0]

    for permission in ("SELECT","INSERT"):
        assert can_table(app,permission), permission
    for permission in ("UPDATE","DELETE","TRUNCATE","REFERENCES","TRIGGER"):
        assert not can_table(app,permission), permission
    for permission in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE"):
        assert not can_table(auth,permission), permission
    print("M40630_SYNTHETIC_TABLE_ACL=PASS")

    function = "public.frfinance_saas_new_admin_published_promotions()"
    def can_execute(role: str) -> bool:
        return conn.execute(
            "SELECT has_function_privilege(%s,%s,'EXECUTE')",
            (role,function),
        ).fetchone()[0]
    assert can_execute(app)
    assert not can_execute(auth)
    print("M40630_SYNTHETIC_FUNCTION_EXECUTE_GRANTS=PASS")

    master_id = conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist"
    ).fetchone()[0]
    # Start with a synthetic member role, without administrative GUCs.
    conn.execute("SELECT set_config('app.current_role','TENANT_MEMBER',false)")
    conn.execute("SELECT set_config('app.current_user_id','',false)")
    conn.execute("SELECT set_config('app.current_tenant_id','',false)")
    conn.execute("SET ROLE frcaixinha_app_role")
    visible_before = conn.execute(
        "SELECT count(*) FROM public.platform_saas_promotion_revisions"
    ).fetchone()[0]
    assert visible_before == 0

    # Non-superuser SQL roles can set custom GUC values. This is a known,
    # unmitigated failure of treating GUC claims as independent authentication.
    conn.execute("SELECT set_config('app.current_role','MASTER',true)")
    conn.execute(
        "SELECT set_config('app.current_user_id',%s,true)",
        (str(master_id),),
    )
    visible_after = conn.execute(
        "SELECT count(*) FROM public.platform_saas_promotion_revisions"
    ).fetchone()[0]
    assert visible_after > 0
    assert conn.execute("SELECT current_user").fetchone()[0] == app
    print("M40630_SYNTHETIC_APP_GUC_SPOOF=EXPOSURE_REPRODUCED")
    print("M40630_SQL_ROLE_ACL_NOT_SESSION_ATTESTATION=CONFIRMED")
    print("M40630_HTTP_AUTH_BYPASS=NOT_TESTED")
    print("M40630_GUC_SPOOF_EXPOSURE=NOT_REMEDIATED")

    conn.execute("RESET ROLE")
    conn.execute("RESET app.current_role")
    conn.execute("RESET app.current_user_id")
    conn.execute("RESET app.current_tenant_id")


def main() -> int:
    print("=== FR FINANCE M40630 — ROLE PRIVILEGES IN DISPOSABLE PG18 ===")
    try:
        require_disposable()
        # Import and connect only *after* the exact disposable CI gate.
        from m40560_saas_role_dataplane_disposable import (
            require_disposable as require_existing_ci,
        )
        require_existing_ci()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            audit(conn)
    except Exception as exc:
        print("M40630_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40630_LOCAL_DATABASE_CONNECTIONS=NONE")
        print("M40630_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40630_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M40630_LOCAL_DB_WRITES=NONE")
        print("M40630_MIGRATIONS=NONE")
        print("M40630_SERVICE_RESTARTS=NONE")
        print("M40630_PIX_REAL=OFF")
        print("M40630_PAGAMENTOS_REAIS=OFF")
        print("M40630_ATIVACAO_REAL=OFF")
        print("M40630_PRODUCTION=BLOCKED")
    print("M40630_STATUS=PASS_AUDIT_WITH_KNOWN_NO_GO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
