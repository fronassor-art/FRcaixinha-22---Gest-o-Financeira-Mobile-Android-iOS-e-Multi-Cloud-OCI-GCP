"""M39045: contrato de análise SQL PG18 com transação read-only e parâmetros falsos.

CI não possui acesso ao banco original, nem credenciais. Somente conexão fake.
"""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from backend.scripts import frfinance_m39045_query_plans_readonly as m

ROUTER = Path(__file__).resolve().parents[1] / "app/routers/special_credit.py"


def test_query_inventory_is_real_and_has_no_dynamic_read_sql():
    queries = m.read_queries(ROUTER.read_text(encoding="utf-8"))
    assert len(queries) >= 12
    assert len({line for line, _, _ in queries}) == len(queries)
    assert all(sql.startswith("SELECT ") for _, _, sql in queries)
    assert any("public.special_credit_campaigns" in sql for _, _, sql in queries)
    assert any("public.special_credit_recipients" in sql for _, _, sql in queries)
    assert any("public.special_credit_preferences" in sql for _, _, sql in queries)
    assert any("public.policies" in sql for _, _, sql in queries)
    assert any("ANY($3::uuid[])" in sql for _, _, sql in queries)
    for _, _, sql in queries:
        plan = m.explain_query(sql)
        assert plan.startswith("EXPLAIN (COSTS OFF) SELECT ")
        assert "$" not in plan
        assert "ANALYZE" not in plan.upper()
        assert "ARRAY[" in plan if "ANY($3::uuid[])" in sql else True


@pytest.mark.parametrize("sql", [
    "UPDATE public.special_credit_grants SET status='ACTIVE'",
    "SELECT 1; DELETE FROM public.tenants",
    "SELECT 1 -- invalid",
    "SELECT * FROM public.tenants WHERE id=$2",
    "SELECT * FROM public.tenants WHERE id=$1 AND flag=$3",
])
def test_planner_rejects_unsafe_sql(sql):
    with pytest.raises(RuntimeError):
        m.explain_query(sql)


class FakeResult:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row

    def fetchall(self):
        return [("synthetic_query_plan",)]


class FakeReadOnlyPg:
    def __init__(self):
        self.queries = []

    def transaction(self):
        return nullcontext()

    def execute(self, sql, args=None):
        self.queries.append((sql, args))
        assert sql.startswith((
            "SET TRANSACTION READ ONLY", "SET LOCAL ROLE frc_ai_app",
            "SELECT current_database()", "SELECT current_user,session_user",
            "SELECT set_config(", "EXPLAIN (COSTS OFF) SELECT "
        )), f"Non-readonly instruction: {sql[:32]}"
        if "SELECT current_database()" in sql:
            return FakeResult((m.DB, m.OWNER, "127.0.0.1", 5433,
                               m.DATA_DIRECTORY, 180006, "on"))
        if sql == "SELECT current_user,session_user":
            return FakeResult(("frc_ai_app", m.OWNER))
        return FakeResult()


def test_readonly_pg_plan_proofs_two_synthetic_roles(capsys):
    queries = m.read_queries(ROUTER.read_text(encoding="utf-8"))
    conn = FakeReadOnlyPg()
    m.run_audit(conn, queries)
    out = capsys.readouterr().out
    assert "M39045_PG18_ORIGINAL=PASS" in out
    assert "M39045_DATABASE_WRITES=NONE" in out
    assert f"M39045_PLANS={len(queries)*2}" in out
    planned = [q for q, _ in conn.queries if q.startswith("EXPLAIN")]
    assert len(planned) == 2 * len(queries)
    assert "EXPLAIN (ANALYZE" not in " ".join(planned)
    assert all("dddddddd-dddd-4ddd-8ddd-dddddddddddd" not in q
               for q in planned)  # uses dummy tenant UUID only


def test_main_requires_termux_original_and_checks_sha(monkeypatch, capsys):
    monkeypatch.setenv("HOME", "/not-canonical-home")
    assert m.main() == 2
    assert "M39045_PREFLIGHT=BLOCKED" in capsys.readouterr().out


def test_script_never_targets_duplicate_or_external_network():
    src = (Path(__file__).resolve().parents[1] / "scripts" /
           "frfinance_m39045_query_plans_readonly.py").read_text()
    assert "verify_repo()" in src
    assert "default_transaction_read_only=on" in src
    assert "SET LOCAL ROLE frc_ai_app" in src
    assert "EXPLAIN (COSTS OFF)" in src
    for forbidden in ("git clone", "/root/fr-finance", "ANALYZE true",
                      "CREATE TABLE", "INSERT INTO public.", "DROP TABLE",
                      "requests.post", "pg_dump", "subprocess.run", "pg_restore"):
        assert forbidden not in src
