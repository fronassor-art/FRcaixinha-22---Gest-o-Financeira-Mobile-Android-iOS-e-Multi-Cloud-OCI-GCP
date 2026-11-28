"""M40580: source-only SQL injection drift guard for sensitive auth/SaaS paths."""
from pathlib import Path
import ast
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from backend.scripts.frfinance_m40580_sql_static_guard import (
    SENSITIVE_PATHS, audit_source, is_literal_sql, source_report,
)


def expression(src: str):
    return ast.parse(src,mode="eval").body


def test_only_literal_string_sql_allowed():
    assert is_literal_sql(expression("'SELECT 1'"))
    assert is_literal_sql(expression("'SELECT ' + '1'"))
    for bad in (
        "sql",
        "f'SELECT {unsafe}'",
        "'SELECT ' + unsafe",
        "'SELECT {}' .format(unsafe)",
        "'SELECT %s' % unsafe",
        "build_sql(unsafe)",
    ):
        assert not is_literal_sql(expression(bad)),bad


def test_scans_each_sensitive_file_and_all_existing_sql_sites():
    result = source_report()
    assert set(result)==set(SENSITIVE_PATHS)
    for path,(count,issues) in result.items():
        assert count >= 3,(path,count)
        assert issues==[],(path,issues)


def test_guard_detects_a_new_fstring_sql_call(tmp_path):
    path=tmp_path/"injected.py"
    path.write_text("def handler(conn,name):\n  conn.fetch(f'SELECT {name}')\n")
    count,issues=audit_source(path)
    assert count==1 and "DYNAMIC_SQL_ARGUMENT" in issues[0]


def test_guard_catches_renamed_connection_alias(tmp_path):
    path=tmp_path/"db_alias.py"
    path.write_text("def handler(db,sql):\n  db.fetch(sql)\n")
    count,issues=audit_source(path)
    assert count==1 and len(issues)==1


def test_guard_detects_new_variable_query_argument(tmp_path):
    path=tmp_path/"queries.py"
    path.write_text("def handler(conn,user_sql):\n  conn.execute(user_sql)\n")
    count,issues=audit_source(path)
    assert count==1 and len(issues)==1


def test_authenticated_context_values_come_from_server_session():
    s=(ROOT/"backend/app/database.py").read_text()
    assert 'user_id = str(session.user_id)' in s
    assert 'role = str(session.role)' in s
    assert 'tenant_id = str(session.tenant_id)' in s
    for marker in (
        "set_config('app.current_user_id', $1, true)",
        "set_config('app.current_role', $1, true)",
        "set_config('app.current_tenant_id', $1, true)",
        "RESET ALL; DISCARD TEMP;",
    ):
        assert marker in s
    assert "tx = conn.transaction()" in s
    assert "await tx.rollback()" in s


def test_auth_bearer_hash_revocation_membership_checks_remain():
    s=(ROOT/"backend/app/dependencies.py").read_text()
    for marker in (
        "digest = hash_token(raw_token)",
        "WHERE s.token_hash=$1",
        "row['revoked_at']",
        "row['expires_at']",
        "auth_active_memberships($1::text)",
        "auth_refresh_session($1::text)",
    ):
        assert marker in s
    assert "request.headers.get('X-Role'" not in s
    assert "request.headers.get('X-User-Id'" not in s


def test_saas_master_and_tenant_route_dependencies():
    s=(ROOT/"backend/app/routers/saas_promotions.py").read_text()
    assert "Depends(require_master)" in s
    assert "Depends(get_rls_db_connection)" in s
    assert "Depends(get_current_session)" in s
    assert "require_tenant_access(" in s
    assert "pg_advisory_xact_lock" in s
    assert "saas_payment_intents" not in s


def test_cli_reports_no_production_or_bypass_claim():
    path=ROOT/"backend/scripts/frfinance_m40580_sql_static_guard.py"
    run=subprocess.run([sys.executable,"-B",str(path)],text=True,
                       capture_output=True,check=False,timeout=10)
    assert run.returncode==0,run.stdout+run.stderr
    assert "M40580_STATUS=PASS_STATIC_LITERAL_SQL_ONLY" in run.stdout
    assert "M40580_SQL_EXECUTION=NONE" in run.stdout
    assert "M40580_GUC_SPOOF_EXPOSURE=NOT_REMEDIATED" in run.stdout
    assert "M40580_PRODUCTION=BLOCKED" in run.stdout