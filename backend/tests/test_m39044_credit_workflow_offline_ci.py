"""M39044: cenário completo FastAPI sintético, sem acessar PostgreSQL do Termux."""
from pathlib import Path

from backend.scripts import frfinance_m39044_credit_workflow_offline as m


def test_complete_admin_member_scenario_fails_closed(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    m.run_scenario()
    result = capsys.readouterr().out
    for marker in (
        "M39044_RBAC_AND_TENANT=PASS",
        "M39044_GRANT_IDEMPOTENCY=PASS",
        "M39044_CAMPAIGN_DRAFT_AND_IDEMPOTENCY=PASS",
        "M39044_IN_APP_PUBLISH_ONLY=PASS",
        "M39044_OUTBOX_BLOCKED_EXTERNAL=PASS",
        "M39044_MEMBER_ISOLATION_AND_SINGLE_REPLY=PASS",
        "M39044_MEMBER_OPT_OUT=PASS",
        "M39044_SANDBOX_OFF_DENIES_WRITES=PASS",
        "M39044_POSTGRESQL_ORIGINAL=NOT_CONNECTED",
        "M39044_EXTERNAL_DELIVERY=OFF",
        "M39044_DATABASE_WRITES=NONE",
        "M39044_PIX_REAL=OFF",
        "M39044_STATUS=PASS",
    ):
        assert marker in result


def test_runner_never_opens_database_or_external_provider():
    source = (Path(__file__).resolve().parents[1] / "scripts" /
              "frfinance_m39044_credit_workflow_offline.py").read_text()
    assert "SyntheticRlsDb" in source
    assert 'FR_FINANCE_SPECIAL_CREDIT_SANDBOX"] = "NO"' in source
    assert 'make_client(' in source
    for banned in (
        "psycopg.connect", "asyncpg.connect", "get_db_pool(",
        "requests.post(", "httpx.post(", "smtplib.", "subprocess.run(",
        "pg_dump", "psql -f", "git clone", "os.system(",
    ):
        assert banned not in source
