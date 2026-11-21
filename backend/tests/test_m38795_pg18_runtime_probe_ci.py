"""M38795: no-write diagnostics of FR Finance PG18 PID / 5433 only (mock CI)."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "backend/scripts"
SRC = SCRIPTS / "frfinance_m38795_pg18_runtime_probe.py"


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location("m38795_runtime_test", SRC)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _synthetic_inspection():
    return {"M38794_PGDATA_IDENTITY": "FR_FINANCE_AI_STUDIO_PG18"}


def test_offline_does_not_touch_pg_process_or_network(monkeypatch, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.identity, "inspect_local",
                        lambda *args: pytest.fail("unexpected live inspect"))
    monkeypatch.setattr(mod, "_run_readonly_probe",
                        lambda *args: pytest.fail("unexpected live probe"))
    monkeypatch.setattr(mod, "_pid_info",
                        lambda: pytest.fail("unexpected PID file"))
    assert mod.main(["offline"]) == 0
    output = capsys.readouterr().out
    assert "M38795_AUDIT=OFFLINE_REFERENCE" in output
    assert "M38795_CLUSTER_IDENTITY=NOT_ATTESTED" in output
    assert "M38795_PG_SERVER_START_STOP=NONE" in output


@pytest.mark.parametrize("params", [
    ["local"],
    ["local", "APPROVE_START_POSTGRES"],
    ["offline", "AUTHORIZE_FRFINANCE_PG18_5433_READONLY_PROBE"],
])
def test_explicit_local_authorization_gate(monkeypatch, params):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "audit", lambda: pytest.fail("live probe not allowed"))
    assert mod.main(params) == 2


def test_manifest_or_git_mismatch_blocks_before_probes(monkeypatch, capsys):
    mod = load(monkeypatch)
    def blocked(*_):
        raise mod.identity.IsolationBlocked("M38794_REMOTE_MISMATCH")
    monkeypatch.setattr(mod.identity, "inspect_local", blocked)
    monkeypatch.setattr(mod, "_pid_info", lambda: pytest.fail("PID must not be read"))
    monkeypatch.setattr(mod, "_run_readonly_probe",
                        lambda *_: pytest.fail("no probing foreign project"))
    assert mod.main(["local", mod.AUTH]) == 2
    output = capsys.readouterr().out
    assert "M38795_AUDIT=BLOCKED" in output
    assert "M38795_PG_2_2_ACCESS=NONE" in output
    assert "M38795_CLUSTER_IDENTITY=NOT_ATTESTED" in output


def test_good_static_identity_and_live_pid_still_do_not_attest_cluster(monkeypatch):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.identity, "inspect_local",
                        lambda _: _synthetic_inspection())
    monkeypatch.setattr(mod, "_pid_info",
                        lambda: (1111, "EXPECTED_PATH_PORT_5433"))
    monkeypatch.setattr(mod, "_pid_reachable",
                        lambda pid: "PID_EXISTS_PROCESS_UNVERIFIED")
    seen = []
    def fake_probe(name):
        seen.append(name)
        return "RUNNING_REPORTED" if name == "pg_ctl" else "ACCEPTING"
    monkeypatch.setattr(mod, "_run_readonly_probe", fake_probe)
    report = mod.audit()
    assert seen == ["pg_ctl", "pg_isready"]
    assert report["M38795_PROJECT_ISOLATION"] == "PASS_STATIC"
    assert report["M38795_CLUSTER_IDENTITY"] == "NOT_ATTESTED"
    assert report["M38795_DIAGNOSIS"] == (
        "PG_PROTOCOL_5433_ACCEPTED_CLUSTER_STILL_UNATTESTED")


@pytest.mark.parametrize("pid_state,ctl,port,expected", [
    ("NOT_RUNNING", "NOT_RUNNING_REPORTED", "NO_RESPONSE",
     "POSSIBLY_STALE_PIDFILE_DO_NOT_DELETE"),
    ("PID_EXISTS_PROCESS_UNVERIFIED", "RUNNING_REPORTED", "NO_RESPONSE",
     "PG_CTL_RUNNING_BUT_PORT_5433_NO_RESPONSE"),
    ("PID_EXISTS_PROCESS_UNVERIFIED", "UNKNOWN", "REJECTING",
     "PG_5433_NOT_READY_DO_NOT_START"),
    ("NO_PIDFILE", "NOT_RUNNING_REPORTED", "NO_RESPONSE",
     "PG_5433_NOT_READY_DO_NOT_START"),
    ("PERMISSION_UNKNOWN", "UNAVAILABLE", "UNAVAILABLE",
     "PG_5433_NOT_READY_DO_NOT_START"),
])
def test_not_ready_classifications_never_start_or_delete(
        monkeypatch, pid_state, ctl, port, expected):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.identity, "inspect_local",
                        lambda _: _synthetic_inspection())
    monkeypatch.setattr(mod, "_pid_info",
                        lambda: (None if pid_state == "NO_PIDFILE" else 123,
                                 "EXPECTED_PATH_PORT_5433"))
    monkeypatch.setattr(mod, "_pid_reachable", lambda _: pid_state)
    monkeypatch.setattr(mod, "_run_readonly_probe",
                        lambda tool: ctl if tool == "pg_ctl" else port)
    assert mod.audit()["M38795_DIAGNOSIS"] == expected


def _pid_lines(data_path, port="5433", pid="1234"):
    return f"{pid}\n{data_path}\n1\n{port}\n/tmp\n127.0.0.1\n"


def test_missing_pidfile_reads_no_process(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "PGDATA", str(tmp_path))
    assert mod._pid_info() == (None, "ABSENT")


def test_expected_pidfile_reads_only_metadata(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "PGDATA", str(tmp_path))
    (tmp_path / "postmaster.pid").write_text(_pid_lines(str(tmp_path)))
    assert mod._pid_info() == (1234, "EXPECTED_PATH_PORT_5433")


@pytest.mark.parametrize("pid,port,path_override", [
    ("", "5433", None),
    ("-1", "5433", None),
    ("1", "5432", None),
    ("123", "5433", "/tmp/foreign_cluster"),
])
def test_wrong_pidfile_identity_is_blocked(
        monkeypatch, tmp_path, pid, port, path_override):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "PGDATA", str(tmp_path))
    (tmp_path / "postmaster.pid").write_text(
        _pid_lines(path_override or str(tmp_path), port=port, pid=pid))
    with pytest.raises(mod.ProbeBlocked, match="PIDFILE_IDENTITY_MISMATCH"):
        mod._pid_info()


def test_pidfile_symlink_rejected(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "PGDATA", str(tmp_path))
    target = tmp_path / "untrusted.txt"
    target.write_text(_pid_lines(str(tmp_path)))
    (tmp_path / "postmaster.pid").symlink_to(target)
    with pytest.raises(mod.ProbeBlocked, match="PIDFILE_SYMLINK_BLOCKED"):
        mod._pid_info()


@pytest.mark.parametrize("error,expected", [
    (None, "PID_EXISTS_PROCESS_UNVERIFIED"),
    (ProcessLookupError(), "NOT_RUNNING"),
    (PermissionError(), "PERMISSION_UNKNOWN"),
    (OSError(), "UNKNOWN"),
])
def test_pid_check_uses_signal_zero_only(monkeypatch, error, expected):
    mod = load(monkeypatch)
    captured = []
    def fake_kill(pid, signal):
        captured.append((pid, signal))
        if error is not None:
            raise error
    monkeypatch.setattr(mod.os, "kill", fake_kill)
    assert mod._pid_reachable(4567) == expected
    assert captured == [(4567, 0)]


def test_no_pidfile_does_not_signal_os(monkeypatch):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.os, "kill", lambda *_: pytest.fail("kill not allowed"))
    assert mod._pid_reachable(None) == "NO_PIDFILE"


@pytest.mark.parametrize("tool,ret,expected", [
    ("pg_ctl", 0, "RUNNING_REPORTED"),
    ("pg_ctl", 3, "NOT_RUNNING_REPORTED"),
    ("pg_ctl", 1, "UNKNOWN"),
    ("pg_isready", 0, "ACCEPTING"),
    ("pg_isready", 1, "REJECTING"),
    ("pg_isready", 2, "NO_RESPONSE"),
    ("pg_isready", 3, "UNKNOWN"),
])
def test_only_expected_readonly_commands(monkeypatch, tool, ret, expected):
    mod = load(monkeypatch)
    monkeypatch.setenv("PGHOST", "foreign-server")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.setenv("PGDATABASE", "frcaixinha_2_2_dev")
    monkeypatch.setenv("PGOPTIONS", "-c default_transaction_read_only=off")
    calls = []
    def fake_run(argv, **kwargs):
        calls.append((argv, {**kwargs, "env": dict(kwargs["env"])}))
        return types.SimpleNamespace(returncode=ret, stderr="PRIVATE", stdout="PRIVATE")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    assert mod._run_readonly_probe(tool) == expected
    assert len(calls) == 1
    argv, opts = calls[0]
    if tool == "pg_ctl":
        assert argv == ["pg_ctl", "-D", mod.PGDATA, "status"]
    else:
        assert argv == [
            "pg_isready", "-q", "-t", "3",
            "-h", "127.0.0.1", "-p", "5433",
            "-U", "frc_ai_owner", "-d", "frcaixinha_aistudio_dev",
        ]
    assert "5432" not in argv
    assert "frcaixinha_2_2_dev" not in argv
    assert all(not key.startswith("PG") for key in opts["env"])
    assert opts["capture_output"] is True
    assert opts["timeout"] <= 8


def test_readonly_tool_missing_fails_without_start(monkeypatch):
    mod = load(monkeypatch)
    def unavailable(*_, **__):
        raise FileNotFoundError("private")
    monkeypatch.setattr(mod.subprocess, "run", unavailable)
    assert mod._run_readonly_probe("pg_ctl") == "UNAVAILABLE"


def test_local_output_only_allowlisted_results(monkeypatch, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "audit", lambda: {
        "M38795_PROJECT_ISOLATION": "PASS_STATIC",
        "M38795_PIDFILE": "EXPECTED_PATH_PORT_5433",
        "M38795_PID_REACHABLE": "NOT_RUNNING",
        "M38795_PG_CTL": "NOT_RUNNING_REPORTED",
        "M38795_PG_ISREADY_5433": "NO_RESPONSE",
        "M38795_DIAGNOSIS": "POSSIBLY_STALE_PIDFILE_DO_NOT_DELETE",
        "M38795_CLUSTER_IDENTITY": "NOT_ATTESTED",
    })
    assert mod.main(["local", mod.AUTH]) == 0
    out = capsys.readouterr().out
    assert "M38795_AUDIT=READONLY_PROCESS_PROBE" in out
    assert "M38795_DIAGNOSIS=POSSIBLY_STALE_PIDFILE_DO_NOT_DELETE" in out
    assert "M38795_PG_PIDFILE_REMOVAL=NONE" in out
    assert "M38795_PG_2_2_ACCESS=NONE" in out


def test_script_does_not_modify_pgdata_or_start_stop_process():
    source = SRC.read_text()
    assert '"pg_ctl", "-D", PGDATA, "status"' in source
    assert '"pg_isready", "-q", "-t", "3"' in source
    for forbidden in (
        '"pg_ctl", "-D", PGDATA, "start"',
        '"pg_ctl", "-D", PGDATA, "stop"',
        'unlink(', 'shutil.rmtree(', 'initdb', 'psql ', 'pg_dump',
        'pg_restore', 'DROP DATABASE', 'ALTER SYSTEM',
    ):
        assert forbidden not in source
    assert "os.kill(pid, 0)" in source
    assert "M38795_CLUSTER_IDENTITY" in source
