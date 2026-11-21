"""M40800 supermacropacote: pure role/DSN & Git-only migration gates.

No connections to DB, no filesystem modifications, no application startup.
"""
from __future__ import annotations

import ast
from pathlib import Path
import pytest

from app.m40800_financial_dsn_guard import (
    require_financial_dsn_shape, FinancialDSNBlocked,
)
from scripts.frfinance_m40800_migration_delta_readonly import (
    needs_independent_migration_review,
)

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "backend/app/database.py"
SCRIPT = ROOT / "backend/scripts/frfinance_m40800_migration_delta_readonly.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m40800-security-migration-preflight-ci.yml"
DOC = ROOT / "docs/FR_FINANCE_M40800_SUPERMACRO_SECURITY_MIGRATION_NO_GO.md"
FIN = "postgresql://frc_ai_app:offline-only-test-secret@127.0.0.1:5433/frcaixinha_aistudio_dev"
AUTH = "postgresql://frc_ai_auth:offline-only-test-secret@127.0.0.1:5433/frcaixinha_aistudio_dev"
VER = "postgresql://frc_ai_verifier:offline-only-test-secret@127.0.0.1:5433/frcaixinha_aistudio_dev"
LOCAL = {"FRCAIXINHA_TERMUX_LOCAL_API": "1", "ENVIRONMENT": "development",
         "AUTH_DATABASE_URL": AUTH, "AUTH_VERIFIER_DATABASE_URL": VER}


def test_exact_local_role_segregation_shape_no_db():
    assert require_financial_dsn_shape(FIN, LOCAL) == "TERMUX_DSN_SHAPE_ONLY_NOT_DB_ATTESTED"


@pytest.mark.parametrize("bad", [
    FIN.replace("frc_ai_app:", "postgres:"),
    FIN.replace("frc_ai_app:", "frc_ai_owner:"),
    FIN.replace("127.0.0.1", "localhost"),
    FIN.replace("127.0.0.1", "192.168.1.12"),
    FIN.replace(":5433/", ":5432/"),
    FIN.replace("frcaixinha_aistudio_dev", "frcaixinha_2_2"),
    FIN + "#fragment",
    FIN + "?sslmode=require",
    FIN + "?connect_timeout=0",
    FIN + "?connect_timeout=9999",
    FIN + "?options=-c%20search_path%3Dpublic",
    FIN + "?sslmode=disable&sslmode=require",
    FIN.replace("offline-only-test-secret", "offline-only-test-secret\nother"),
    "postgresql:///frcaixinha_aistudio_dev",
])
def test_local_rejects_wrong_account_cluster_and_query_options(bad):
    with pytest.raises(FinancialDSNBlocked):
        require_financial_dsn_shape(bad, LOCAL)


@pytest.mark.parametrize("name,value", [
    ("AUTH_DATABASE_URL", FIN),
    ("AUTH_DATABASE_URL", AUTH.replace("frc_ai_auth", "frc_ai_owner")),
    ("AUTH_DATABASE_URL", AUTH.replace(":5433/", ":5432/")),
    ("AUTH_VERIFIER_DATABASE_URL", AUTH),
    ("AUTH_VERIFIER_DATABASE_URL", VER.replace("frc_ai_verifier", "frc_ai_app")),
])
def test_local_rejects_unsegregated_auxiliary_credentials(name, value):
    with pytest.raises(FinancialDSNBlocked):
        require_financial_dsn_shape(FIN, {**LOCAL, name: value})


def test_nonlocal_dev_is_explicitly_unattested():
    assert require_financial_dsn_shape(FIN, {"ENVIRONMENT": "development"}) == "NONPRODUCTION_UNATTESTED"


def test_production_local_pg_denied():
    with pytest.raises(FinancialDSNBlocked):
        require_financial_dsn_shape(FIN, {"ENVIRONMENT": "production", "DATABASE_URL": FIN})


def test_production_syntax_does_not_certify_live_environment():
    url = "postgresql://frc_ai_app:offline-only-test-secret@pg.frfinance.com.br:5432/frfinance_prod?sslmode=verify-full"
    assert require_financial_dsn_shape(url, {"ENVIRONMENT": "production", "DATABASE_URL": url}) == "PRODUCTION_SHAPE_REQUIRES_EXTERNAL_REVIEW"


@pytest.mark.parametrize("path,expected", [
    ("backend/migrations/114_new.sql", True),
    ("backend/local_migrations/114_new.sql", True),
    ("backend/ci_migrations/114_new.sql", True),
    ("backend/staging_migrations/114_new.sql", True),
    ("backend/migration_catalog_ai_studio.json", True),
    ("backend/scripts/aistudio_local_migration.sh", True),
    ("backend/scripts/aistudio_db_local.sh", True),
    ("backend/scripts/aistudio_migration_inventory.py", True),
    ("backend/scripts/additional_financial.sql", True),
    ("backend/app/database.py", False),
    ("backend/app/mp_connect_http_runtime.py", False),
    ("backend/tests/test_m40800_security_migration_offline.py", False),
    ("docs/FR_FINANCE_M40800_SUPERMACRO_SECURITY_MIGRATION_NO_GO.md", False),
])
def test_migration_delta_sensitive_files(path, expected):
    assert needs_independent_migration_review(path) is expected


def test_source_actual_pool_calls_gate_before_driver():
    source = DB.read_text(encoding="utf-8")
    assert source.index("require_financial_dsn_shape(settings.DATABASE_URL, os.environ)") < source.index("import asyncpg")
    assert "require_production_auth(os.environ)" in source
    assert "M40800_FINANCIAL_DSN_BLOCKED" in source
    ast.parse(source)
    ast.parse(SCRIPT.read_text(encoding="utf-8"))


def test_readonly_migration_tool_has_no_db_or_mutations():
    source = SCRIPT.read_text(encoding="utf-8")
    for blocked in ("psycopg", "asyncpg", "psql", "pg_dump", "git push",
                    "subprocess.run([\"psql\"", "pg_ctl"):
        assert blocked not in source
    assert '"diff", "--name-only", old, target' in source
    assert '"merge-base", "--is-ancestor", old, target' in source
    assert "M40800_MIGRATIONS=NONE" in source


def test_ci_and_docs_preserve_all_no_go_boundaries():
    yml = WORKFLOW.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")
    for s in ("PIX_REAL: 'OFF'", "PAGAMENTOS_REAIS: 'OFF'",
              "ATIVACAO_REAL: 'OFF'", "test_m40800_security_migration_offline.py",
              "contents: read"):
        assert s in yml
    for s in ("M40570", "M40730", "GUC", "NO-GO", "PRODUCTION=BLOCKED",
              "MIGRATIONS=NONE"):
        assert s in doc
