"""M39046 — execução real dos SELECTs de API só quando READ ONLY e RLS.

O CI usa PostgreSQL simulado, sem banco Termux.
"""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from backend.scripts import frfinance_m39046_execute_selects_readonly as m

ROUTER = Path(__file__).resolve().parents[1] / "app" / "routers" / "special_credit.py"


def test_inventory_differentiates_readonly_queries_from_row_locks():
    queries = m.read_queries(ROUTER.read_text(encoding="utf-8"))
    assert len(queries) == m.EXPECTED_QUERIES == 18
    locking = [sql for _, _, sql in queries if m.is_locking(sql)]
    assert len(locking) == m.EXPECTED_LOCKING == 2
    assert any("FOR SHARE" in sql for sql in locking)
    assert any("FOR UPDATE" in sql for sql in locking)
    for _, _, sql in queries:
        if m.is_locking(sql):
            with pytest.raises(RuntimeError, match="LOCKING_SELECT_REQUIRES_WRITE_TXN"):
                m.executable_sql(sql)
        else:
            value = m.executable_sql(sql)
            assert value.startswith("SELECT ")
            assert "$" not in value
            assert "EXPLAIN" not in value


def test_cycle_readiness_query_is_tenant_scoped_scalar_and_date_gated():
    queries = m.read_queries(ROUTER.read_text(encoding="utf-8"))
    matches = [
        sql for _, _, sql in queries
        if sql.startswith("SELECT EXISTS (SELECT 1 FROM public.cycles ")
    ]
    assert len(matches) == 1
    sql = matches[0]
    for condition in (
        "tenant_id=$1", "status='ABERTO'",
        "start_date<=CURRENT_DATE", "end_date>=CURRENT_DATE"
    ):
        assert condition in sql
    assert m._scalar_zero(sql)
    assert not m.is_locking(sql)
    assert m.executable_sql(sql).startswith("SELECT EXISTS (")



class FakeResponse:
    def __init__(self, single=None, all_rows=None):
        self.single = single
        self.all_rows = all_rows if all_rows is not None else []

    def fetchone(self):
        return self.single

    def fetchall(self):
        return self.all_rows


class FakeReadOnlyPg:
    def __init__(self, *, leak=False):
        self.queries = []
        self.leak = leak

    def transaction(self):
        return nullcontext()

    def execute(self, query, args=None):
        self.queries.append((query, args))
        if query == "SET TRANSACTION READ ONLY":
            return FakeResponse()
        if query.startswith("SELECT current_database(),session_user"):
            return FakeResponse((m.DB, m.OWNER, "127.0.0.1", 5433,
                                 m.DATA_DIRECTORY, 180006, "on"))
        if query.startswith("SELECT EXISTS(SELECT 1 FROM public.tenants"):
            return FakeResponse((False, False))
        if query == "SET LOCAL ROLE frc_ai_app":
            return FakeResponse()
        if query == "SELECT current_user,session_user":
            return FakeResponse(("frc_ai_app", m.OWNER))
        if query == "SELECT current_setting('transaction_read_only')":
            return FakeResponse(("on",))
        if query.startswith("SELECT row_security_active"):
            return FakeResponse((True,))
        if query.startswith("SELECT set_config"):
            return FakeResponse()
        assert query.startswith("SELECT "), f"Unexpected SQL statement: {query[:40]}"
        assert "FOR SHARE" not in query and "FOR UPDATE" not in query
        assert "$" not in query
        if m._scalar_zero(query):
            return FakeResponse(all_rows=[(1 if self.leak else 0,)])
        return FakeResponse(all_rows=[("leaked",)] if self.leak else [])


def test_all_safe_reads_execute_under_rls_without_exposing_rows(capsys):
    queries = m.read_queries(ROUTER.read_text(encoding="utf-8"))
    fake = FakeReadOnlyPg()
    m.audit_actual_selects(fake, queries)
    output = capsys.readouterr().out
    assert "M39046_STATUS=PASS" not in output  # main imprime após a auditoria
    assert "M39046_RLS_ACTIVE=6_OF_6" in output
    assert "M39046_SELECTS_EXECUTED=32" in output
    assert "M39046_LOCKING_SELECTS_SKIPPED=2" in output
    assert "M39046_DATABASE_WRITES=NONE" in output
    assert len([q for q,_ in fake.queries if q.startswith("SELECT ") and
                not q.startswith(("SELECT current_", "SELECT EXISTS(SELECT 1 FROM public.tenants",
                                  "SELECT row_security_active", "SELECT set_config"))]) == 32


def test_leak_or_wrong_baseline_never_returns_pass():
    queries = m.read_queries(ROUTER.read_text(encoding="utf-8"))
    with pytest.raises(RuntimeError, match="M39046_QUERY_FAILED"):
        m.audit_actual_selects(FakeReadOnlyPg(leak=True), queries)
    with pytest.raises(RuntimeError, match="READ_QUERY_COVERAGE_DRIFT"):
        m.audit_actual_selects(FakeReadOnlyPg(), queries[:-1])


def test_synthetic_cycle_readiness_true_is_rejected_as_leak():
    class FakeUnscopedCycle(FakeReadOnlyPg):
        def execute(self, query, args=None):
            if query.startswith("SELECT EXISTS (SELECT 1 FROM public.cycles "):
                self.queries.append((query, args))
                return FakeResponse(all_rows=[(True,)])
            return super().execute(query, args)

    queries = m.read_queries(ROUTER.read_text(encoding="utf-8"))
    with pytest.raises(RuntimeError, match="M39046_QUERY_FAILED"):
        m.audit_actual_selects(FakeUnscopedCycle(), queries)


def test_main_rejects_noncanonical_environment(monkeypatch, capsys):
    monkeypatch.setenv("HOME", "/not-termux")
    assert m.main() == 2
    assert "M39046_PREFLIGHT=BLOCKED" in capsys.readouterr().out


def test_read_only_no_new_cluster_or_transport():
    src = (Path(__file__).resolve().parents[1] / "scripts" /
           "frfinance_m39046_execute_selects_readonly.py").read_text()
    for approved in ("verify_repo()", "SET TRANSACTION READ ONLY",
                     "SET LOCAL ROLE frc_ai_app", "default_transaction_read_only=on",
                     "SYNTHETIC_IDENTIFIERS_ALREADY_PRESENT"):
        assert approved in src
    for banned in ("git clone", "/root/fr-finance", "DROP TABLE", "CREATE TABLE",
                   "pg_dump", "pg_restore", "ANALYZE true", "EXECUTE FUNCTION",
                   "requests.post(", "subprocess.run(", "UPDATE public."):
        assert banned not in src
