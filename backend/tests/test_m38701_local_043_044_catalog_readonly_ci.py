"""M38701-M38790: synthetic catalog audit without connecting to any database."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "backend/scripts/aistudio_m38701_local_043_044_catalog_readonly.py"
DUMMY = "DUMMY_SYNTHETIC_PASSWORD_NOT_REAL_987"
SENSITIVE = "SENSITIVE_DATABASE_DIAGNOSTIC"


def _load():
    spec = importlib.util.spec_from_file_location("m38790_catalog", CLI)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _report(mod, **changes):
    values = dict.fromkeys(mod.FIELDS, True)
    values.update(changes)
    return "\n".join(f"{key}={'TRUE' if values[key] else 'FALSE'}"
                     for key in mod.FIELDS) + "\n"


def test_offline_does_not_prompt_or_connect(monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_password",
                        lambda: pytest.fail("prompted offline"))
    monkeypatch.setattr(mod, "fetch_catalog",
                        lambda _: pytest.fail("accessed DB offline"))
    assert mod.main(["offline"]) == 0
    out = capsys.readouterr().out
    assert "M38790_MODE=OFFLINE_NO_DB_NO_CREDENTIALS" in out
    assert "M38790_MIGRATION_PROVENANCE=NOT_ATTESTED" in out
    assert "M38790_DATABASE_MUTATIONS=NONE" in out


@pytest.mark.parametrize("args", [
    ["local"],
    ["local", "AUTHORIZE_ANY_MIGRATION"],
    ["offline", "AUTHORIZE_PG18_043_044_CATALOG_READ_ONLY"],
])
def test_explicit_authorization_required_before_password_or_connection(
        args, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_password",
                        lambda: pytest.fail("prompted without consent"))
    monkeypatch.setattr(mod, "fetch_catalog",
                        lambda _: pytest.fail("network without consent"))
    assert mod.main(args) == 2


@pytest.mark.parametrize("raw", ["", "malformed", "SENSITIVE=a",
                                  "DB_TARGET_OK=MAYBE", "DB_TARGET_OK=TRUE\n"*200])
def test_unexpected_provider_output_is_rejected(raw):
    mod = _load()
    with pytest.raises(mod.CatalogAuditBlocked):
        mod.parse_report(raw)


def test_complete_report_in_wrong_cluster_must_be_blocked():
    mod = _load()
    with pytest.raises(mod.CatalogAuditBlocked, match="WRONG_POSTGRES_CLUSTER"):
        mod.parse_report(_report(mod, DB_TARGET_OK=False))


def test_duplicate_or_missing_output_line_must_be_blocked():
    mod = _load()
    with pytest.raises(mod.CatalogAuditBlocked, match="REPORT_INVALID"):
        mod.parse_report(_report(mod) + "M044_AUDIT_RLS=TRUE\n")
    raw = _report(mod).replace("M044_AUDIT_RLS=TRUE\n", "")
    with pytest.raises(mod.CatalogAuditBlocked, match="REPORT_INCOMPLETE"):
        mod.parse_report(raw)


def test_synthetic_positive_catalog_evidence_is_not_migration_provenance(
        monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_password", lambda: DUMMY)
    monkeypatch.setattr(mod, "fetch_catalog",
                        lambda secret: mod.parse_report(_report(mod))
                        if secret == DUMMY else pytest.fail("bad secret"))
    assert mod.main(["local", mod.AUTHORIZE]) == 0
    out = capsys.readouterr().out
    assert "M38790_DB_TARGET=VERIFIED_LOCAL_PG18" in out
    assert "M38790_LOCAL_043_SCHEMA=COMPATIBLE_OBSERVED" in out
    assert "M38790_LOCAL_044_SCHEMA=COMPATIBLE_OBSERVED" in out
    assert "M38790_MIGRATION_PROVENANCE=NOT_ATTESTED" in out
    assert "M38790_PRODUCTION=BLOCKED" in out
    assert DUMMY not in out


@pytest.mark.parametrize("missing", [
    "M043_POLICY_FLOOR", "M043_QUOTA_FLOOR", "M043_NO_DEFAULTS",
    "M043_WRAPPER_FLOOR", "M043_LEGACY_RESTRICTED",
])
def test_partial_043_never_claims_compatible(missing, monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_password", lambda: DUMMY)
    monkeypatch.setattr(mod, "fetch_catalog",
                        lambda _: mod.parse_report(_report(mod, **{missing: False})))
    assert mod.main(["local", mod.AUTHORIZE]) == 0
    out = capsys.readouterr().out
    assert "M38790_LOCAL_043_SCHEMA=INCOMPLETE_OR_MISSING" in out
    assert "M38790_LOCAL_044_SCHEMA=COMPATIBLE_OBSERVED" in out
    assert "M38790_PRODUCTION=BLOCKED" in out


@pytest.mark.parametrize("missing", [
    "M044_AUDIT_RLS", "M044_IMMUTABLE_TRIGGERS",
    "M044_CREATE_FLOOR", "M044_ROLE_BOUNDARY", "M044_UNIQUE_REPLAY",
])
def test_partial_044_never_claims_compatible(missing, monkeypatch, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_password", lambda: DUMMY)
    monkeypatch.setattr(mod, "fetch_catalog",
                        lambda _: mod.parse_report(_report(mod, **{missing: False})))
    assert mod.main(["local", mod.AUTHORIZE]) == 0
    out = capsys.readouterr().out
    assert "M38790_LOCAL_043_SCHEMA=COMPATIBLE_OBSERVED" in out
    assert "M38790_LOCAL_044_SCHEMA=INCOMPLETE_OR_MISSING" in out
    assert "M38790_PRODUCTION=BLOCKED" in out


def test_command_uses_loopback_and_readonly_transaction(monkeypatch):
    mod = _load()
    called = []
    def fake_run(argv, **kwargs):
        # subprocess.run consumes env at invocation; production code later
        # clears its temporary PGPASSWORD reference from that dictionary.
        called.append((list(argv), {**kwargs, "env": dict(kwargs["env"])}))
        return types.SimpleNamespace(
            returncode=0, stdout=_report(mod), stderr=SENSITIVE)
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    monkeypatch.setenv("PGHOST", "untrusted.example.invalid")
    monkeypatch.setenv("PGDATABASE", "other")
    monkeypatch.setenv("PGOPTIONS", "-c default_transaction_read_only=off")
    report = mod.fetch_catalog(DUMMY)
    assert report["M044_AUDIT_RLS"]
    assert len(called) == 1
    argv, opts = called[0]
    assert argv == ["psql", "-X", "-w", "-q", "-A", "-t",
                    "-v", "ON_ERROR_STOP=1",
                    "-v", "VERBOSITY=sqlstate",
                    "-h", "127.0.0.1", "-p", "5433",
                    "-U", "frc_ai_owner", "-d", "frcaixinha_aistudio_dev"]
    assert opts["input"] == mod.QUERY
    assert opts["env"]["PGPASSWORD"] == DUMMY
    assert opts["env"]["PGOPTIONS"] == "-c default_transaction_read_only=on"
    assert "PGHOST" not in opts["env"]
    assert opts["capture_output"] is True
    assert opts["timeout"] <= 20
    assert "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in opts["input"]
    assert "SET LOCAL statement_timeout" in opts["input"]


@pytest.mark.parametrize("returned", [
    types.SimpleNamespace(returncode=2, stdout="", stderr=SENSITIVE),
    types.SimpleNamespace(returncode=0, stdout=SENSITIVE, stderr=""),
])
def test_query_errors_never_echo_sensitive_error_details(monkeypatch, returned, capsys):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_password", lambda: DUMMY)
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: returned)
    assert mod.main(["local", mod.AUTHORIZE]) == 2
    out = capsys.readouterr().out
    assert "M38790_AUDIT=BLOCKED" in out
    assert SENSITIVE not in out
    assert DUMMY not in out
    assert "M38790_PRODUCTION=BLOCKED" in out


@pytest.mark.parametrize("stderr,returncode,expected", [
    ("psql:<stdin>:14: ERROR:  42601", 3, "SQL_SYNTAX_ERROR"),
    ("psql:<stdin>:19: ERROR:  42883", 3, "SQL_FUNCTION_UNAVAILABLE"),
    ("psql:<stdin>:19: ERROR:  42P01", 3, "SQL_RELATION_UNAVAILABLE"),
    ("psql:<stdin>:21: ERROR:  42501", 3, "PERMISSION_DENIED"),
    ("psql: error: connection to server at 127.0.0.1:5433 failed: "
     "FATAL: password authentication failed for user frc_ai_owner",
     2, "AUTH_REJECTED"),
    ("psql: error: connection to server refused; is the server running?",
     2, "CONNECTION_REFUSED"),
    ("psql: error: connection timed out", 2, "CONNECTION_TIMEOUT"),
    ("psql: unknown failure SECRET=DO_NOT_PRINT", 3, "QUERY_EXECUTION_ERROR"),
])
def test_safe_psql_failure_categories_without_raw_diagnostics(
        monkeypatch, capsys, stderr, returncode, expected):
    mod = _load()
    monkeypatch.setattr(mod, "_prompt_password", lambda: DUMMY)
    def fake_psql(*args, **kwargs):
        return types.SimpleNamespace(returncode=returncode,
                                     stdout="", stderr=stderr)
    monkeypatch.setattr(mod.subprocess, "run", fake_psql)
    assert mod.main(["local", mod.AUTHORIZE]) == 2
    out = capsys.readouterr().out
    assert "M38790_CAUSE=M38790_LOCAL_PG_QUERY_FAILED" in out
    assert "M38792_FAILURE_CLASS=" + expected in out
    assert stderr not in out
    assert DUMMY not in out
    assert "M38790_PRODUCTION=BLOCKED" in out


def test_timeout_and_client_missing_fail_closed(monkeypatch):
    mod = _load()
    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="psql", timeout=20)
    monkeypatch.setattr(mod.subprocess, "run", fail)
    with pytest.raises(mod.CatalogAuditBlocked, match="LOCAL_PSQL_UNAVAILABLE"):
        mod.fetch_catalog(DUMMY)


@pytest.mark.parametrize("secret", [
    "", None, "x\nBAD_LINE", "abc\rxyz", "x\tTAB",
    "x\x00NUL", "x\x1bESC", "x" * 513,
])
def test_malformed_password_blocked_before_process(monkeypatch, secret):
    mod = _load()
    monkeypatch.setattr(mod.subprocess, "run", lambda *a, **k: pytest.fail("psql"))
    with pytest.raises(mod.CatalogAuditBlocked):
        mod.fetch_catalog(secret)


@pytest.mark.parametrize("secret", [
    "Senha com espaço e çãõ",
    "  espaços preservados  ",
    "🔐Senha-UTF8#2026",
    "pão de açúcar",
])
def test_printable_unicode_password_is_passed_verbatim_without_echo(
        monkeypatch, secret, capsys):
    mod = _load()
    calls = []
    def fake_psql(argv, **kwargs):
        calls.append(kwargs["env"]["PGPASSWORD"])
        return types.SimpleNamespace(
            returncode=0, stdout=_report(mod), stderr="")
    monkeypatch.setattr(mod.subprocess, "run", fake_psql)
    assert mod.fetch_catalog(secret)["DB_TARGET_OK"] is True
    assert calls == [secret]
    assert secret not in capsys.readouterr().out


def test_no_tty_cannot_prompt(monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod.sys, "stdin",
                        types.SimpleNamespace(isatty=lambda: False))
    monkeypatch.setattr(mod.getpass, "getpass",
                        lambda *_: pytest.fail("must not request password"))
    with pytest.raises(mod.CatalogAuditBlocked, match="TTY_REQUIRED"):
        mod._prompt_password()


def test_static_query_never_reads_business_rows_or_writes_or_executes_functions():
    mod = _load()
    source = CLI.read_text()
    q = mod.QUERY.lower()
    assert "pg_catalog.pg_constraint" in q
    assert "pg_catalog.pg_proc" in q
    assert "pg_catalog.pg_class" in q
    assert "pg_catalog.pg_trigger" in q
    assert "begin transaction isolation level repeatable read read only" in q
    for disallowed in (
        "insert into ", "update public.", "delete from ", "truncate ",
        "drop table ", "alter table ", "create table ", "grant ",
        "copy ", "pg_dump", "pg_restore", "from public.contributions",
        "from public.memberships", "from public.policies",
        "from public.quotas", "from public.cycles",
        "from public.ledger", "from public.users", "from public.sessions",
    ):
        assert disallowed not in q
    assert "subprocess.run(" in source
    assert "getpass.getpass(" in source
    assert "M38790_PRODUCTION=BLOCKED" in source
    assert "M38790_MIGRATION_PROVENANCE=NOT_ATTESTED" in source
