"""M39069: regressão do falso bloqueio pós-COMMIT das SQL112+113.

Nenhum PostgreSQL é acessado. Reproduz introspecção de proconfig PG18
com e sem espaços e verifica que o inspetor legado reconhece APPLIED.
"""
from contextlib import nullcontext
from pathlib import Path

import pytest

from backend.scripts.frfinance_m39067_apply_saas_prices_promotions_pg18 import (
    inspect_sql112_113, search_path_is_restricted,
)

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "backend/scripts/frfinance_m39067_apply_saas_prices_promotions_pg18.py"


@pytest.mark.parametrize("config", [
    ["search_path=pg_catalog, pg_temp"],
    ["search_path=pg_catalog,pg_temp"],
    ["search_path=PG_CATALOG, Pg_Temp"],
    ("other=1", "search_path= pg_catalog , pg_temp "),
])
def test_pg18_restricted_catalog_path_handles_formatting(config):
    assert search_path_is_restricted(config)


@pytest.mark.parametrize("config", [
    None, [], "search_path=pg_catalog,pg_temp", {},
    ["search_path=public,pg_catalog,pg_temp"],
    ["search_path=pg_catalog"],
    ["search_path=pg_temp,pg_catalog"],
    ["search_path=pg_catalog,pg_temp,public"],
    ["search_path=pg_catalog,pg_temp", "search_path=public"],
    ["search_path=pg_catalog, pg_temp", "search_path=pg_catalog,pg_temp"],
    ["search_path = pg_catalog,pg_temp"],
    ["other=foo"],
])
def test_pg18_search_path_still_fail_closed(config):
    assert search_path_is_restricted(config) is False


class Cursor:
    def __init__(self, record):
        self.record = record
    def fetchone(self):
        return self.record


class ReadOnlyConnection:
    def __init__(self, path):
        self.path = path
        self.queries = []
    def transaction(self):
        return nullcontext()
    def execute(self, sql, params=None):
        self.queries.append(sql)
        if sql.startswith("SET TRANSACTION READ ONLY"):
            return Cursor(None)
        if "to_regclass('public.platform_saas_promotion_revisions')" in sql:
            return Cursor((True, True))
        if "count(*) FROM public.platform_license_price_versions" in sql:
            return Cursor((2,))
        if "relrowsecurity,relforcerowsecurity" in sql:
            return Cursor((True, True))
        if "has_table_privilege(" in sql:
            return Cursor((True, False, False, False, True, False))
        if "count(*) FROM pg_catalog.pg_trigger" in sql:
            return Cursor((1,))
        if "SELECT prosecdef,proconfig" in sql:
            return Cursor((True, [f"search_path={self.path}"]))
        raise AssertionError("Unrecognized SQL: " + sql[:90])


@pytest.mark.parametrize("path", ["pg_catalog, pg_temp", "pg_catalog,pg_temp"])
def test_original_postcommit_inspection_detects_both_applied(monkeypatch, path):
    from backend.scripts import frfinance_m39067_apply_saas_prices_promotions_pg18 as m
    monkeypatch.setattr(m, "inspect_original",
                        lambda conn: "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT")
    conn = ReadOnlyConnection(path)
    result = inspect_sql112_113(conn)
    assert result == (
        "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT",
        "SQL113_APPLIED_SAFE_NO_REPEAT",
        2,
    )
    assert "SET TRANSACTION READ ONLY" in conn.queries
    assert not any(
        q.startswith(("ALTER", "CREATE", "DROP", "INSERT", "UPDATE", "DELETE"))
        for q in conn.queries
    )


def test_original_postcommit_inspection_denies_unsafe_path(monkeypatch):
    from backend.scripts import frfinance_m39067_apply_saas_prices_promotions_pg18 as m
    monkeypatch.setattr(m, "inspect_original",
                        lambda conn: "SQL112_ALREADY_APPLIED_SAFE_NO_REPEAT")
    with pytest.raises(m.Blocked, match="SQL113_RLS_PRIVILEGES_TRIGGER_OR_FUNCTION_UNSAFE"):
        inspect_sql112_113(ReadOnlyConnection("public,pg_catalog,pg_temp"))


def test_m39067_fixed_postcommit_no_sql_reapply_on_inspect():
    code = RUNNER.read_text()
    assert "SELECT prosecdef,proconfig" in code
    assert "not search_path_is_restricted(definer[1])" in code
    assert "array_to_string(proconfig" not in code
    assert "if args.inspect:" in code
    assert "M39067_MIGRATION=ALREADY_APPLIED_NO_REPEAT" in code
    assert "with conn.transaction():" in code
    assert "M39067_ORIGINAL_PG18" in code
