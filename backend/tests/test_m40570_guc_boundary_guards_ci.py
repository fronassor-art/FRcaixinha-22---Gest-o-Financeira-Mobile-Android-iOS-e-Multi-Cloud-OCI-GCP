"""M40570: source guards and threat boundary; no actual database access."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/tests/m40570_guc_spoof_disposable.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40570-guc-spoof-ci.yml"
DB = ROOT / "backend/app/database.py"
DEP = ROOT / "backend/app/dependencies.py"
POLICY = ROOT / "backend/migrations/113_frfinance_saas_new_admin_promotions.sql"


def test_execution_fails_closed_before_psycopg_without_ci():
    result = subprocess.run(
        [sys.executable, "-B", str(RUNNER)],
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", "")},
        timeout=10,
    )
    assert result.returncode == 2, result.stderr
    assert "M40570_STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "M40570_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in result.stdout


def test_scope_is_disposable_runner_only():
    s = RUNNER.read_text()
    for name in ("GITHUB_ACTIONS", "CI_M40570_DISPOSABLE",
                 "CI_M40560_DISPOSABLE","FRCAIXINHA_CI_ISOLATED",
                 "restricted_connection",
                 "require_disposable",
                 "M40570_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED"):
        assert name in s
    assert s.index("require_disposable()") < s.index("from m39067_postgres18_disposable_runtime import restricted_connection")


def test_authenticated_backend_context_not_request_headers():
    s = DB.read_text()
    dep = DEP.read_text()
    assert "session.user_id" in s
    assert "session.tenant_id" in s
    assert "session.role" in s
    for name in ("app.current_user_id", "app.current_role",
                 "app.current_tenant_id"):
        assert name in s
    assert "true);" in s
    assert "get_current_session" in s
    for name in ("s.token_hash=$1","row['revoked_at']",
                 "row['expires_at']","auth_active_memberships",
                 "auth_refresh_session"):
        assert name in dep


def test_sql113_rls_uses_user_configurable_guc():
    sql=POLICY.read_text()
    for term in ("current_setting('app.current_role',true)='MASTER'",
                 "current_setting('app.current_user_id',true)",
                 "public.rls_is_master("):
        assert term in sql
    s=RUNNER.read_text()
    for term in ("SET ROLE frcaixinha_app_role",
                 "SELECT set_config('app.current_role','MASTER',false)",
                 "SELECT set_config('app.current_user_id',%s,false)",
                 "M40570_GUC_SPOOFING=EXPOSURE_REPRODUCED_DISPOSABLE"):
        assert term in s


def test_expected_finding_cannot_be_misreported_as_secure():
    s=RUNNER.read_text()
    for marker in ("M40570_RLS_NOT_INDEPENDENT_AUTHENTICATOR=CONFIRMED",
                   "M40570_HTTP_BEARER_BYPASS=NOT_TESTED",
                   "M40570_GATE=NO_GO_UNTIL_SQL_ORIGIN_HARDENING_ATTESTED",
                   "M40570_STATUS=PASS_EXPOSURE_DOCUMENTED_NOT_MITIGATED",
                   "M40570_PRODUCTION=BLOCKED"):
        assert marker in s
    for forbidden in ("api.env","pg_ctl", "pg_dump", "requests.post(",
                      "subprocess.Popen(", "os.kill(", "asyncpg.connect("):
        assert forbidden not in s


def test_ci_workflow_uses_ephemeral_pg18_only():
    wf = WORKFLOW.read_text()
    for marker in ("postgres:18","55433:5432",
                   "fr_m39067_disposable_ci",
                   "CI_M40570_DISPOSABLE: '1'",
                   "CI_M40560_DISPOSABLE: '1'",
                   "FRCAIXINHA_CI_ISOLATED: '1'",
                   "PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
                   "ATIVACAO_REAL: 'OFF'","m40570_guc_spoof_disposable.py"):
        assert marker in wf
    assert "ssh " not in wf
    assert "pg_ctl restart" not in wf