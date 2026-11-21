"""M39054 read-only inventory contract; fake PG connection only in CI."""
from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pytest

from backend.scripts import frfinance_m39054_auth_pg18_preflight as m


class FakeRows:
    def __init__(self, one=None, many=None):
        self.one = one
        self.many = [] if many is None else many

    def fetchone(self):
        return self.one

    def fetchall(self):
        return self.many


class FakeReadonlyPG:
    def __init__(self, *, functions=None, roles=None):
        self.statements = []
        self.functions = (m.REQUIRED_FUNCTIONS if functions is None else functions)
        self.roles = ([
            ("frc_ai_app", True, False, False),
            ("frc_ai_auth", True, False, False),
            ("frc_ai_verifier", True, False, False),
        ] if roles is None else roles)

    def transaction(self):
        return nullcontext()

    def execute(self, sql, args=None):
        self.statements.append((sql, args))
        if sql == "SET TRANSACTION READ ONLY":
            return FakeRows()
        if "SELECT current_database(),session_user" in sql:
            return FakeRows(one=(
                m.DB, m.OWNER, "127.0.0.1", 5433, m.DATA_DIRECTORY, 180006, "on",
            ))
        if "FROM pg_roles" in sql:
            return FakeRows(many=self.roles)
        if "FROM pg_class" in sql:
            return FakeRows(many=[(name,) for name in m.REQUIRED_RELATIONS])
        if "FROM pg_proc" in sql:
            return FakeRows(many=[(name,) for name in self.functions])
        raise AssertionError("UNEXPECTED_SQL_IN_M39054")


def test_auth_inventory_checks_auth_functions_and_roles(capsys):
    connection = FakeReadonlyPG()
    m.audit_original_database(connection)
    output = capsys.readouterr().out
    for marker in (
        "M39054_PG18_ORIGINAL=PASS",
        "M39054_APP_AND_AUTH_ROLES=PASS",
        "M39054_AUTH_RELATIONS=4_OF_4",
        "M39054_AUTH_FUNCTIONS=7_OF_7",
        "M39054_VERIFIER_CANDIDATE_ROLES=frc_ai_verifier",
        "M39054_AUTH_LOGIN_PERFORMED=NO",
        "M39054_SESSIONS_CREATED=NONE",
        "M39054_DATABASE_WRITES=NONE",
    ):
        assert marker in output
    assert connection.statements[0][0] == "SET TRANSACTION READ ONLY"
    assert all(statement.startswith("SELECT ") or statement == "SET TRANSACTION READ ONLY"
               for statement, _ in connection.statements)


def test_missing_auth_function_refuses_pass():
    conn = FakeReadonlyPG(functions=("auth_login_rate_check",))
    with pytest.raises(RuntimeError, match="AUTH_FUNCTIONS_INCOMPLETE"):
        m.audit_original_database(conn)


def test_auth_role_cannot_have_superuser_or_rls_bypass():
    conn = FakeReadonlyPG(roles=[
        ("frc_ai_app", True, False, False),
        ("frc_ai_auth", True, False, True),
    ])
    with pytest.raises(RuntimeError, match="APPLICATION_AUTH_ROLE_PRIVILEGE_UNSAFE"):
        m.audit_original_database(conn)


def test_termux_original_guard_rejects_ci(monkeypatch):
    monkeypatch.setenv("HOME", "/home/runner")
    with pytest.raises(RuntimeError, match="ONLY_ORIGINAL_TERMUX_WORKTREE"):
        m.verify_original()


def test_source_cannot_mutate_original_database():
    text = (Path(__file__).resolve().parents[1] /
            "scripts/frfinance_m39054_auth_pg18_preflight.py").read_text()
    assert "SET TRANSACTION READ ONLY" in text
    assert "default_transaction_read_only=on" in text
    assert "getpass.getpass" in text
    assert "AI_STUDIO_APPROVED_SHA" in text
    for forbidden in (
        "CREATE DATABASE", "DROP DATABASE", "DROP TABLE", "ALTER ROLE",
        "INSERT INTO ", "UPDATE public.", "DELETE FROM public.",
        "asyncpg.connect(", "os.system(", "subprocess.Popen(",
        "git clone", "/root/fr-finance",
    ):
        assert forbidden not in text
