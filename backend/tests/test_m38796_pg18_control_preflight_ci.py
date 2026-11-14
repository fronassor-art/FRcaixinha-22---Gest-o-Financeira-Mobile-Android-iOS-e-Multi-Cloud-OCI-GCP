"""FR Finance M38796: synthetic pg_controldata / PID read-only safety tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/scripts/frfinance_m38796_pg18_control_preflight.py"
SCRIPTS = SRC.parent


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("m38796_test_module", SRC)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("state,expected", [
    ("shut down", "CLEAN_SHUTDOWN_REPORTED"),
    ("shut down in recovery", "RECOVERY_SHUTDOWN_REPORTED"),
    ("in production", "UNCLEAN_OR_RUNNING_STATE_REPORTED"),
    ("in archive recovery", "ARCHIVE_RECOVERY_STATE_REPORTED"),
    ("starting up", "STARTUP_STATE_REPORTED"),
    ("not a valid state", "UNKNOWN_STATE"),
])
def test_pg_control_output_allowlisted_with_no_identifiers(monkeypatch, state, expected):
    mod = load(monkeypatch)
    output = (
        "Database system identifier: 1111111111111111111\n"
        "Database cluster state: " + state + "\n"
        "Latest checkpoint location: 0/FAKE\n"
    )
    assert mod.parse_control_state(output) == expected


@pytest.mark.parametrize("text", ["", "no cluster state", "x" * 65536,
                                 "Database cluster state: shut down\n"
                                 "Database cluster state: in production\n"])
def test_malformed_pgcontrol_output_rejected(monkeypatch, text):
    mod = load(monkeypatch)
    with pytest.raises(mod.PreflightBlocked):
        mod.parse_control_state(text)


def fake_stopped():
    return {
        "M38795_PROJECT_ISOLATION": "PASS_STATIC",
        "M38795_PIDFILE": "EXPECTED_PATH_PORT_5433",
        "M38795_PID_REACHABLE": "NOT_RUNNING",
        "M38795_PG_CTL": "NOT_RUNNING_REPORTED",
        "M38795_PG_ISREADY_5433": "NO_RESPONSE",
    }


@pytest.mark.parametrize("field,value", [
    ("M38795_PROJECT_ISOLATION", "BLOCKED"),
    ("M38795_PIDFILE", "ABSENT"),
    ("M38795_PID_REACHABLE", "PID_EXISTS_PROCESS_UNVERIFIED"),
    ("M38795_PID_REACHABLE", "PERMISSION_UNKNOWN"),
    ("M38795_PG_CTL", "RUNNING_REPORTED"),
    ("M38795_PG_ISREADY_5433", "ACCEPTING"),
    ("M38795_PG_ISREADY_5433", "REJECTING"),
])
def test_no_pgcontrol_read_if_runtime_not_proven_stopped(
        monkeypatch, field, value):
    mod = load(monkeypatch)
    snapshot = fake_stopped()
    snapshot[field] = value
    monkeypatch.setattr(mod.runtime, "audit", lambda: snapshot)
    monkeypatch.setattr(mod, "pg_controldata_readonly",
                        lambda: pytest.fail("must not inspect control"))
    with pytest.raises(mod.PreflightBlocked):
        mod.local_audit()


@pytest.mark.parametrize("state,expected_next", [
    ("CLEAN_SHUTDOWN_REPORTED", "STOPPED_WITH_PIDFILE_MANUAL_REVIEW_REQUIRED"),
    ("UNCLEAN_OR_RUNNING_STATE_REPORTED",
     "UNCLEAN_CONTROL_STATE_POSSIBLE_WAL_RECOVERY_NO_ACTION"),
    ("RECOVERY_SHUTDOWN_REPORTED", "RECOVERY_STATE_MANUAL_REVIEW_REQUIRED"),
    ("ARCHIVE_RECOVERY_STATE_REPORTED",
     "RECOVERY_OR_STARTUP_STATE_MANUAL_REVIEW_REQUIRED"),
    ("STARTUP_STATE_REPORTED", "RECOVERY_OR_STARTUP_STATE_MANUAL_REVIEW_REQUIRED"),
    ("UNKNOWN_STATE", "UNKNOWN_CONTROL_STATE_BLOCKED"),
])
def test_two_stopped_snapshots_and_only_safe_recommendation(
        monkeypatch, state, expected_next):
    mod = load(monkeypatch)
    calls = []
    def audit():
        calls.append("runtime")
        return fake_stopped()
    def control():
        calls.append("control")
        return state
    monkeypatch.setattr(mod.runtime, "audit", audit)
    monkeypatch.setattr(mod, "pg_controldata_readonly", control)
    report = mod.local_audit()
    assert calls == ["runtime", "control", "runtime"]
    assert report["M38796_PG_CONTROL_STATE"] == state
    assert report["M38796_NEXT_STEP"] == expected_next
    assert report["M38796_OPERATION_ALLOWED"] == "NONE"
    assert report["M38796_LIVE_CLUSTER_IDENTITY"] == "NOT_ATTESTED"


def test_race_between_pre_and_post_probe_blocks(monkeypatch):
    mod = load(monkeypatch)
    calls = []
    def changed():
        calls.append(1)
        data = fake_stopped()
        if len(calls) == 2:
            data["M38795_PG_ISREADY_5433"] = "ACCEPTING"
        return data
    monkeypatch.setattr(mod.runtime, "audit", changed)
    monkeypatch.setattr(mod, "pg_controldata_readonly",
                        lambda: "CLEAN_SHUTDOWN_REPORTED")
    with pytest.raises(mod.PreflightBlocked):
        mod.local_audit()


def test_control_reader_no_symlink_or_missing_pg_control(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.identity, "FINANCE_PGDATA", str(tmp_path))
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **k: pytest.fail("subprocess should not run"))
    with pytest.raises(mod.PreflightBlocked, match="PG_CONTROL_MISSING_OR_LINKED"):
        mod.pg_controldata_readonly()
    control = tmp_path / "global" / "pg_control"
    control.parent.mkdir()
    actual = tmp_path / "actual_control"
    actual.write_text("fake data")
    control.symlink_to(actual)
    with pytest.raises(mod.PreflightBlocked, match="PG_CONTROL_MISSING_OR_LINKED"):
        mod.pg_controldata_readonly()


@pytest.mark.parametrize("exitcode,valid", [(0, True), (3, False)])
def test_pgcontrol_reads_only_approved_pgdata_without_echoing_raw_output(
        monkeypatch, tmp_path, exitcode, valid, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.identity, "FINANCE_PGDATA", str(tmp_path))
    control = tmp_path / "global" / "pg_control"
    control.parent.mkdir()
    control.write_text("synthetic")
    monkeypatch.setenv("PGDATA", "/foreign/cluster/fr22")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.setenv("PGPASSWORD", "DO_NOT_PRINT_FAKE")
    captured = []
    def fake_call(argv, **kwargs):
        captured.append((argv, kwargs))
        return types.SimpleNamespace(
            returncode=exitcode,
            stdout="Database system identifier: SENSITIVE\n"
                   "Database cluster state: shut down\n",
            stderr="SENSITIVE_SERVER_DATA",
        )
    monkeypatch.setattr(mod.subprocess, "run", fake_call)
    if valid:
        assert mod.pg_controldata_readonly() == "CLEAN_SHUTDOWN_REPORTED"
    else:
        with pytest.raises(mod.PreflightBlocked, match="PG_CONTROLDATA_READ_FAILED"):
            mod.pg_controldata_readonly()
    assert captured[0][0] == ["pg_controldata", "-D", str(tmp_path)]
    env = captured[0][1]["env"]
    assert "PGDATA" not in env
    assert "PGPORT" not in env
    assert "PGPASSWORD" not in env
    assert env["LC_ALL"] == "C"
    assert env["PG_COLOR"] == "never"
    assert "SENSITIVE" not in capsys.readouterr().out


def test_offline_does_not_access_termux_or_pg_control(monkeypatch, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "local_audit", lambda: pytest.fail("unexpected IO"))
    assert mod.main(["offline"]) == 0
    output = capsys.readouterr().out
    assert "M38796_PG_CONTROL_STATE=NOT_QUERIED" in output
    assert "M38796_PG_START_STOP=NONE" in output


@pytest.mark.parametrize("arguments", [
    ["local"],
    ["local", "ALLOW_MIGRATIONS"],
    ["offline", "AUTHORIZE_FRFINANCE_PG18_CONTROL_READONLY"],
])
def test_fail_closed_without_correct_explicit_mode_gate(monkeypatch, arguments):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "local_audit", lambda: pytest.fail("unexpected IO"))
    assert mod.main(arguments) == 2


def test_live_audit_synthetic_output_masks_cluster_details(monkeypatch, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "local_audit", lambda: {
        "M38796_PROJECT": "FR_FINANCE_AI_STUDIO",
        "M38796_PG_CONTROL_STATE": "UNCLEAN_OR_RUNNING_STATE_REPORTED",
        "M38796_NEXT_STEP": "UNCLEAN_CONTROL_STATE_POSSIBLE_WAL_RECOVERY_NO_ACTION",
        "M38796_OPERATION_ALLOWED": "NONE",
        "M38796_LIVE_CLUSTER_IDENTITY": "NOT_ATTESTED",
    })
    assert mod.main(["local", mod.AUTH]) == 0
    text = capsys.readouterr().out
    assert "M38796_OPERATION_ALLOWED=NONE" in text
    assert "M38796_POSTMASTER_PID_DELETE=NONE" in text
    assert "M38796_FR22_ACCESS=NONE" in text
    assert "M38796_PRODUCTION=BLOCKED" in text


def test_static_no_recovery_modification_commands():
    text = SRC.read_text(encoding="utf-8")
    for bad in (
        "pg_resetwal", "pg_ctl start", "pg_ctl stop",
        "unlink(", "rmtree(", "initdb", "psql ", "pg_dump",
        "ALTER SYSTEM", "delete from public", "UPDATE public",
    ):
        assert bad not in text
    assert '["pg_controldata", "-D", identity.FINANCE_PGDATA]' in text
    assert "pg_controldata_readonly" in text
    assert "M38796_PG_START_STOP=NONE" in text
