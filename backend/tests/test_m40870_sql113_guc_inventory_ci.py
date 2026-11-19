"""M40870: explicit SQL113 authority NO-GO regression, offline only."""
from __future__ import annotations
import ast
from pathlib import Path
import pytest
from scripts.frfinance_m40870_sql113_guc_inventory import (
    ROOT, SQL, ROUTER, GATE, inspect, inventory,
)
from app.m40840_financial_sql_release_no_go import (
    FinancialSQLReleaseBlocked, require_nonproduction_financial_sql,
)

def test_all_five_known_guc_authority_boundaries_remain_no_go():
    found={f.code for f in inventory()}
    assert {
        "M40870_MASTER_SELECT_USES_GUC",
        "M40870_MASTER_INSERT_USES_GUC",
        "M40870_SECURITY_DEFINER_USES_GUC",
        "M40870_APP_ROLE_EXECUTES_DEFINER",
        "M40870_LIVE_ROUTE_USES_GUC_DEFINER",
    } <= found

def test_clean_source_does_not_invent_vulnerabilities():
    assert inspect("CREATE FUNCTION safe() RETURNS int LANGUAGE SQL AS 'SELECT 0';",
                   "def read_safe(): pass","M40840_FINANCIAL_SQL_NO_GO")==()

def test_production_remains_blocked_despite_valid_sql113_catalog():
    with pytest.raises(FinancialSQLReleaseBlocked):
        require_nonproduction_financial_sql({
          "ENVIRONMENT":"production","PIX_REAL":"OFF",
          "PAGAMENTOS_REAIS":"OFF","ATIVACAO_REAL":"OFF",
        })

def test_audit_contains_no_sql_connection_or_modification():
    s=(ROOT/"backend/scripts/frfinance_m40870_sql113_guc_inventory.py").read_text()
    ast.parse(s)
    for disallowed in ("import psycopg","import asyncpg","subprocess",
                       "CREATE ROLE ","DROP TABLE ","psql "):
        assert disallowed not in s
    assert "M40870_LIVE_DATABASE_ATTESTED=FALSE" in s
    assert "M40870_DB_WRITES=NONE" in s

def test_sql113_is_historical_not_a_new_migration():
    assert "CREATE POLICY frfinance_saas_promo_master_select" in SQL.read_text()
    assert "SECURITY DEFINER" in SQL.read_text()
    assert "get_rls_db_connection" in ROUTER.read_text()
    assert "M40840_FINANCIAL_SQL_NO_GO" in GATE.read_text()

def test_no_go_document_and_ci():
    y=(ROOT/".github/workflows/frfinance-m40880-android-sql-inventory-ci.yml").read_text()
    d=(ROOT/"docs/FR_FINANCE_M40880_ANDROID_SQL_SECURITY_NO_GO.md").read_text()
    for marker in ("PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
                   "ATIVACAO_REAL: 'OFF'","contents: read",
                   "test_m40870_sql113_guc_inventory_ci.py"):
        assert marker in y
    for marker in ("M40570","M40730","SQL113","GUC","NO-GO",
                   "M40860","PRODUCTION=BLOCKED"):
        assert marker in d
