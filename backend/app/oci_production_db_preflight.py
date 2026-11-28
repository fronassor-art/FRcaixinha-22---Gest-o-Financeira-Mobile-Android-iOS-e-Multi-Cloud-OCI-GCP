"""M22100: Read-only production OCI Postgres 18 security preflight.

No writes, migrations, payments, raw DSNs or token logging.
"""
from __future__ import annotations
import os
from urllib.parse import urlsplit
from typing import Callable, Mapping
from .production_auth_gate import require_production_auth, ProductionAuthBlocked

CONTRACT="AI_STUDIO_M22100_PG18_ROLE_PREFLIGHT_V1"
ROLES=("frc_ai_app","frc_ai_auth","frc_ai_verifier")
TABLES=("users","credentials","sessions","auth_login_proofs")
READONLY_OPTIONS="-c default_transaction_read_only=on -c statement_timeout=5000 -c lock_timeout=2000"


class DbPreflightBlocked(Exception):
    """Only fixed, redacted errors are emitted."""


def inspect_role(conn,role:str,database:str)->None:
    if role not in ROLES:
        raise DbPreflightBlocked("ROLE_INVALID")
    try:
        identity=conn.execute(
            "SELECT current_database(),current_user,"
            "current_setting('server_version_num')::integer,"
            "current_setting('transaction_read_only')").fetchone()
        tls=conn.execute(
            "SELECT COALESCE((SELECT ssl FROM pg_stat_ssl "
            "WHERE pid=pg_backend_pid()),false)").fetchone()
        flags=conn.execute(
            "SELECT rolcanlogin,rolsuper,rolbypassrls,"
            "rolcreatedb,rolcreaterole,rolreplication "
            "FROM pg_roles WHERE rolname=current_user").fetchone()
        rls=conn.execute(
            "SELECT relname,relrowsecurity,relforcerowsecurity "
            "FROM pg_class JOIN pg_namespace n ON n.oid=relnamespace "
            "WHERE n.nspname='public' AND relname IN "
            "('users','credentials','sessions','auth_login_proofs')").fetchall()
        grants=conn.execute(
            "SELECT "
            "has_column_privilege(current_user,'public.credentials','password_hash','SELECT'),"
            "has_table_privilege(current_user,'public.sessions','INSERT'),"
            "has_table_privilege(current_user,'public.sessions','SELECT'),"
            "has_table_privilege(current_user,'public.auth_login_proofs','INSERT'),"
            "has_function_privilege(current_user,"
            "'public.auth_issue_pending_session(uuid,text,text)','EXECUTE'),"
            "has_function_privilege(current_user,"
            "'public.auth_login_rate_check(text)','EXECUTE')").fetchone()
    except Exception:
        raise DbPreflightBlocked("PG_CATALOG_READ_FAILED") from None
    if (type(identity) not in (tuple,list) or len(identity)!=4
            or identity[0]!=database or identity[1]!=role
            or type(identity[2]) is not int or not 180000<=identity[2]<190000
            or identity[3]!="on"
            or tls!=(True,)
            or flags!=(True,False,False,False,False,False)):
        raise DbPreflightBlocked("PG_IDENTITY_TLS_OR_PRIVILEGE_UNSAFE")
    if (type(rls) is not list or len(rls)!=len(TABLES)
            or {row[0] for row in rls}!=set(TABLES)
            or any(tuple(row[1:])!=(True,True) for row in rls)):
        raise DbPreflightBlocked("FORCE_RLS_MISSING")
    expected={
        "frc_ai_app":(False,False,False,False,False,False),
        "frc_ai_auth":(False,False,True,False,True,True),
        "frc_ai_verifier":(True,False,False,True,False,False),
    }[role]
    if tuple(grants or ())!=expected:
        raise DbPreflightBlocked("ROLE_GRANTS_MISMATCH")


def audit_production_db(env:Mapping[str,str],connect:Callable|None=None)->tuple[str,...]:
    if env.get("FR_FINANCE_DB_PREFLIGHT_CONFIRM")!="READ_ONLY_OCI":
        raise DbPreflightBlocked("OPERATOR_CONFIRMATION_REQUIRED")
    try:
        require_production_auth(env)
    except ProductionAuthBlocked:
        raise DbPreflightBlocked("OCI_PRODUCTION_CONFIG_BLOCKED") from None
    if connect is None:
        import psycopg
        connect=psycopg.connect
    dbname=urlsplit(env["DATABASE_URL"]).path[1:]
    checked=[]
    for role,name in (
        ("frc_ai_app","DATABASE_URL"),
        ("frc_ai_auth","AUTH_DATABASE_URL"),
        ("frc_ai_verifier","AUTH_VERIFIER_DATABASE_URL"),
    ):
        try:
            with connect(env[name],connect_timeout=5,options=READONLY_OPTIONS) as conn:
                inspect_role(conn,role,dbname)
        except DbPreflightBlocked:
            raise
        except Exception:
            raise DbPreflightBlocked("OCI_CONNECTION_OR_TLS_NOT_READY") from None
        checked.append(role)
    return tuple(checked)


def main()->int:
    try:
        assert audit_production_db(os.environ)==ROLES
    except (DbPreflightBlocked,AssertionError) as exc:
        print("M22100_OCI_DB_PREFLIGHT=BLOCKED")
        print("M22100_CAUSE="+str(exc))
        return 2
    print("M22100_OCI_DB_PREFLIGHT=READ_ONLY_PASS")
    print("M22100_TLS_RLS_GRANTS=CATALOG_VERIFIED")
    print("M22100_LOGIN_E2E=NOT_VERIFIED")
    print("M22100_RESTORE_TEST=NOT_VERIFIED")
    print("M22100_REAL_PIX=DISABLED")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
