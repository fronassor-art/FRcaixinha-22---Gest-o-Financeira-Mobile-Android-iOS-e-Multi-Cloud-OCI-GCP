#!/usr/bin/env python3
"""M22600: AI Studio local PG18 auth-boundary verification, strictly read-only.

Checks access boundaries from 001-027. It DOES NOT reconstruct individual
migration execution history and DOES NOT attempt to apply or repair objects.
"""
from __future__ import annotations
import getpass
import os
from pathlib import Path
import subprocess
import sys

from aistudio_migration_inventory import PGDATA, ROOT, BRANCH


class BaselineBlocked(Exception):
    """Only fixed, non-sensitive error codes."""


def _scalar(conn, sql: str):
    return conn.execute(sql).fetchone()[0]


def inspect_local_auth_baseline(conn) -> tuple[str, ...]:
    """Run catalog-only SELECTs; no credential hashes or user records."""
    def need(code: str, sql: str):
        try:
            if _scalar(conn, sql) is not True:
                raise BaselineBlocked(code)
        except BaselineBlocked:
            raise
        except Exception:
            raise BaselineBlocked(code + "_QUERY_FAILED") from None

    need("M22600_AUTH_ROLES_IDENTITY", """
SELECT
 EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frc_ai_app'
  AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frc_ai_auth'
  AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname='frc_ai_verifier'
  AND rolcanlogin AND NOT rolsuper AND NOT rolbypassrls)
 AND pg_has_role('frc_ai_app','frcaixinha_app_role','MEMBER')
 AND pg_has_role('frc_ai_auth','frcaixinha_auth_role','MEMBER')
 AND pg_has_role('frc_ai_verifier','frcaixinha_verifier_role','MEMBER')
 AND NOT pg_has_role('frc_ai_auth','frcaixinha_verifier_role','MEMBER')
 AND NOT pg_has_role('frc_ai_app','frcaixinha_verifier_role','MEMBER')
""")
    need("M22600_AUTH_ACCESS_DENIED", """
SELECT
 NOT has_table_privilege('frc_ai_app','public.credentials','SELECT')
 AND NOT has_table_privilege('frc_ai_auth','public.credentials','SELECT')
 AND NOT has_column_privilege('frc_ai_auth','public.credentials','password_hash','SELECT')
 AND has_column_privilege('frc_ai_verifier','public.credentials','password_hash','SELECT')
 AND NOT has_table_privilege('frc_ai_app','public.sessions','SELECT')
 AND NOT has_table_privilege('frc_ai_auth','public.sessions','INSERT')
 AND NOT has_table_privilege('frc_ai_verifier','public.sessions','INSERT')
 AND NOT has_table_privilege('frc_ai_auth','public.auth_login_proofs','INSERT')
 AND has_column_privilege('frc_ai_verifier','public.auth_login_proofs','credential_fingerprint','INSERT')
 AND NOT has_table_privilege('frc_ai_auth','public.auth_login_proofs','SELECT')
 AND NOT has_table_privilege('frc_ai_auth','public.auth_login_rate_limits','SELECT')
""")
    need("M22600_AUTH_FUNCTIONS_BOUND", """
SELECT
 has_function_privilege('frc_ai_auth',
  'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')
 AND NOT has_function_privilege('frc_ai_app',
  'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')
 AND NOT has_function_privilege('frc_ai_verifier',
  'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')
 AND has_function_privilege('frc_ai_auth',
  'public.auth_login_rate_check(text)','EXECUTE')
 AND has_function_privilege('frc_ai_auth',
  'public.auth_login_rate_failure(text)','EXECUTE')
 AND has_function_privilege('frc_ai_auth',
  'public.auth_login_rate_success(text)','EXECUTE')
 AND NOT has_function_privilege('frc_ai_app',
  'public.auth_login_rate_check(text)','EXECUTE')
 AND has_function_privilege('frc_ai_auth',
  'public.auth_refresh_session(text)','EXECUTE')
 AND has_function_privilege('frc_ai_auth',
  'public.auth_revoke_all_sessions(text)','EXECUTE')
 AND NOT has_function_privilege('frc_ai_app',
  'public.auth_revoke_all_sessions(text)','EXECUTE')
""")
    need("M22600_AUTH_FORCE_RLS", """
SELECT COUNT(*)=4 AND bool_and(c.relrowsecurity AND c.relforcerowsecurity)
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname
 IN ('users','sessions','auth_login_proofs','auth_login_rate_limits')
""")
    need("M22600_AUTH_REVOCATION_TRIGGERS", """
SELECT COUNT(*)=2
FROM pg_trigger
WHERE tgrelid='public.credentials'::regclass
 AND tgname IN ('auth_password_changed_revoke',
                'auth_password_deleted_revoke')
 AND NOT tgisinternal AND tgenabled='O'
""")
    need("M22600_AUTH_PROOF_FINGERPRINT", """
SELECT EXISTS (
 SELECT 1 FROM pg_constraint
 WHERE conrelid='public.auth_login_proofs'::regclass
 AND conname='auth_proof_fingerprint_format'
)
AND EXISTS (
 SELECT 1 FROM pg_constraint
 WHERE conrelid='public.sessions'::regclass
 AND conname='sessions_absolute_8h_guard'
)
""")
    return (
        "AUTH_ROLES", "ROLE_ISOLATION", "AUTH_FUNCTIONS", "FORCE_RLS",
        "CREDENTIAL_REVOCATION", "SESSION_AND_PROOF_CONSTRAINTS",
    )


def check_repo() -> None:
    try:
        branch=subprocess.check_output(
            ["git","-C",str(ROOT),"branch","--show-current"],text=True
        ).strip()
        head=subprocess.check_output(
            ["git","-C",str(ROOT),"rev-parse","HEAD"],text=True
        ).strip()
        dirty=subprocess.check_output(
            ["git","-C",str(ROOT),"status","--porcelain","--untracked-files=no"],
            text=True,
        ).strip()
    except (OSError,subprocess.CalledProcessError):
        raise BaselineBlocked("GIT_UNAVAILABLE") from None
    if (ROOT!=Path.home()/"frcaixinha-aistudio-mobile"
            or branch!=BRANCH or dirty
            or head!=os.getenv("AI_STUDIO_APPROVED_SHA","")):
        raise BaselineBlocked("PROJECT_BRANCH_OR_SHA_UNAPPROVED")


def inspect() -> tuple[str,...]:
    check_repo()
    import psycopg
    secret=getpass.getpass("Senha frc_ai_owner (oculta): ")
    if not secret:
        raise BaselineBlocked("PASSWORD_MISSING")
    try:
        with psycopg.connect(
            host="127.0.0.1",port=5433,
            dbname="frcaixinha_aistudio_dev",user="frc_ai_owner",
            password=secret,connect_timeout=5,
            options="-c default_transaction_read_only=on -c statement_timeout=10000",
        ) as conn:
            del secret
            with conn.transaction():
                identity=conn.execute(
                    "SELECT current_database(),current_user,inet_server_port(),"
                    "current_setting('data_directory'),"
                    "current_setting('server_version_num')::integer,"
                    "current_setting('transaction_read_only')"
                ).fetchone()
                if (identity!=(
                    "frcaixinha_aistudio_dev","frc_ai_owner",5433,PGDATA,
                    identity[4],"on"
                ) or type(identity[4]) is not int
                    or not 180000<=identity[4]<190000):
                    raise BaselineBlocked("WRONG_PG18_CLUSTER")
                return inspect_local_auth_baseline(conn)
    except BaselineBlocked:
        raise
    except Exception:
        raise BaselineBlocked("PG18_READ_ONLY_PROBE_FAILED") from None


def main() -> int:
    try:
        results=inspect()
    except BaselineBlocked as exc:
        print("M22600_LOCAL_AUTH_BASELINE=BLOCKED")
        print("M22600_REASON="+str(exc))
        return 2
    for part in results:
        print("M22600_"+part+"=PASS")
    print("M22600_LOCAL_AUTH_BASELINE=STRUCTURAL_PRIVILEGES_PASS")
    print("M22600_MIGRATION_001_027_EXECUTION_HISTORY=UNVERIFIED")
    print("M22600_PRODUCTION_AUTH_E2E=NOT_TESTED")
    print("M22600_DB_WRITES=NONE")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
