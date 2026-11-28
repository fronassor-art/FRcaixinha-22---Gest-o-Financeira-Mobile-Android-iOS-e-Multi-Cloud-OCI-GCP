"""M40150: offline synthetic tests protect exact PG18 paths and no service control."""
from pathlib import Path
import subprocess
import pytest

from backend.scripts import frfinance_m40150_original_pg18_status_readonly as m


def test_sanitized_process_environment():
    env = m.safe_subprocess_env({
        "PATH": "/termux/bin", "HOME": "/termux/home", "PREFIX": "/termux",
        "PGHOST": "different-host", "PGPORT": "5432",
        "PGPASSWORD": "never-display", "PGSERVICE": "other-project",
        "DATABASE_URL": "never-print", "AUTH_DATABASE_URL": "never-print",
    })
    assert env == {
        "PATH": "/termux/bin", "HOME": "/termux/home", "PREFIX": "/termux"
    }


def test_binaries_presence_and_symlink_fails_closed(tmp_path):
    ctl = tmp_path / "pg_ctl"
    ready = tmp_path / "pg_isready"
    assert m.allowed_executables(ctl, ready) == "PG_TOOLS_NOT_ATTESTED"
    ctl.write_text("x")
    ready.write_text("x")
    assert m.allowed_executables(ctl, ready) == (
        "TERMUX_POSTGRES_BINARIES_PRESENT_NOT_EXECUTED"
    )
    link = tmp_path / "link"
    link.symlink_to(ctl)
    assert m.allowed_executables(link, ready) == "PG_TOOLS_NOT_ATTESTED"


@pytest.mark.parametrize("rc,expected", [
    (0, "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING"),
    (3, "ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED"),
    (1, "ORIGINAL_PGDATA_PROCESS_NOT_ATTESTED"),
])
def test_pg_ctl_explicit_original_cluster_status(rc, expected):
    def run(cmd, **opts):
        assert cmd == [str(m.PG_CTL), "-D", m.FINANCE_PGDATA, "status"]
        assert opts["timeout"] == m.TIMEOUT_SECONDS
        assert "PGPORT" not in opts["env"]
        assert opts["check"] is False
        return subprocess.CompletedProcess(cmd, rc, b"", b"")
    assert m.pg_ctl_status(run) == expected


@pytest.mark.parametrize("rc,expected", [
    (0, "PORT_5433_ACCEPTING_UNAUTHENTICATED"),
    (1, "PORT_5433_REJECTING_CONNECTIONS"),
    (2, "PORT_5433_NO_RESPONSE"),
    (3, "PORT_5433_PROBE_NOT_ATTEMPTED"),
])
def test_pg_isready_exact_port_without_credentials(rc, expected):
    def run(cmd, **opts):
        assert cmd == [str(m.PG_ISREADY), "-q", "-t", "2",
                       "-h", "127.0.0.1", "-p", "5433",
                       "-U", "frc_ai_owner", "-d", "frcaixinha_aistudio_dev"]
        assert "PGPASSWORD" not in opts["env"]
        return subprocess.CompletedProcess(cmd, rc, b"", b"")
    assert m.pg_isready_status(run) == expected


def test_subprocess_failure_no_raw_output():
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("pg_ctl", 6)
    assert m.pg_ctl_status(timeout) == "ORIGINAL_PGDATA_PROCESS_NOT_ATTESTED"
    assert m.pg_isready_status(timeout) == "PORT_5433_NOT_ATTESTED"


def test_static_original_identity():
    good = {
        "M38794_GIT_IDENTITY": "FR_FINANCE_AI_STUDIO",
        "M38794_PGDATA_IDENTITY": "FR_FINANCE_AI_STUDIO_PG18",
        "M38794_PGDATA_VERSION": "18",
    }
    assert m.identity(lambda _: good) == "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18"
    assert m.identity(lambda _: {**good, "M38794_PGDATA_VERSION": "17"}) == (
        "BLOCKED_ORIGINAL_FR_FINANCE_PGDATA"
    )


def flags(**changes):
    kwargs = {
        "project": lambda: "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18",
        "launcher": lambda: "PASS_M38801_ORIGINAL_STATIC_CONTRACT",
        "tools": lambda: "TERMUX_POSTGRES_BINARIES_PRESENT_NOT_EXECUTED",
        "status": lambda: "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING",
        "ready": lambda: "PORT_5433_ACCEPTING_UNAUTHENTICATED",
        "tcp": lambda: "TCP_CONNECTION_REFUSED",
    }
    kwargs.update(changes)
    return m.report(**kwargs)


def test_ready_probe_still_never_authorizes_fastapi_start():
    r = flags()
    assert r["M40150_STATUS"] == (
        "BLOCKED_DB_IDENTITY_AND_FASTAPI_LAUNCH_NOT_AUTHORIZED"
    )
    assert r["M40150_LAUNCH_AUTHORIZED"] == "FALSE"
    assert r["M40150_RESTART_AUTHORIZED"] == "FALSE"
    assert r["M40150_AUTHENTICATED_PG_IDENTITY"] == "NOT_ATTESTED"
    assert r["M40150_DB_SQL_SESSIONS"] == "NONE"


@pytest.mark.parametrize("overrides,expected", [
    ({"project": lambda: "BLOCKED_ORIGINAL_FR_FINANCE_PGDATA"},
     "BLOCKED_PROJECT_ISOLATION"),
    ({"launcher": lambda: "BLOCKED_LAUNCHER_CONTRACT_DRIFT"},
     "BLOCKED_LAUNCHER_DRIFT"),
    ({"tools": lambda: "PG_TOOLS_NOT_ATTESTED"},
     "BLOCKED_POSTGRES_BINARIES"),
    ({"tcp": lambda: "TCP_HANDSHAKE_ACCEPTED"},
     "BLOCKED_FASTAPI_PORT_OCCUPIED"),
    ({"status": lambda: "ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED"},
     "BLOCKED_ORIGINAL_PG_NOT_RUNNING_DO_NOT_START"),
    ({"status": lambda: "ORIGINAL_PGDATA_PROCESS_NOT_ATTESTED"},
     "BLOCKED_ORIGINAL_PG_PROCESS_UNVERIFIED"),
    ({"ready": lambda: "PORT_5433_NO_RESPONSE"},
     "BLOCKED_ORIGINAL_PG_5433_NOT_ACCEPTING"),
    ({"tcp": lambda: "TCP_CONNECT_TIMEOUT"},
     "BLOCKED_TCP_8000_UNVERIFIED"),
])
def test_fail_closed_paths(overrides, expected):
    assert flags(**overrides)["M40150_STATUS"] == expected


def test_gate_skips_probe_if_worktree_wrong():
    def fail_if_called():
        pytest.fail("should not probe any service when isolation fails")
    r = flags(project=lambda: "BLOCKED_ORIGINAL_FR_FINANCE_PGDATA",
              status=fail_if_called, ready=fail_if_called, tcp=fail_if_called)
    assert r["M40150_PG_ISREADY_5433"] == "SKIPPED_PRECHECK"
    assert r["M40150_TCP_8000"] == "SKIPPED_PRECHECK"


def test_termux_gate_source_only(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40150_LIVE_SERVER=NOT_ATTESTED" in capsys.readouterr().out
    assert m.main([]) == 2


def test_no_unsafe_service_or_database_actions():
    src = (Path(__file__).resolve().parents[2] /
           "backend/scripts/frfinance_m40150_original_pg18_status_readonly.py"
          ).read_text(encoding="utf-8")
    for marker in ("M40150_DATABASE_WRITES=NONE", "M40150_SQL_QUERIES=NONE",
                   "M40150_PG_START_STOP=NONE",
                   "M40150_FASTAPI_START_STOP_RESTART=NONE",
                   "M40150_PRODUCTION=BLOCKED", "M40150_LAUNCH_AUTHORIZED"):
        assert marker in src
    for unsafe in ("os.kill(", "subprocess.Popen(", "uvicorn.run(",
                   "psycopg.connect(", "asyncpg.connect(", "shell=True",
                   "pg_ctl start", "pg_ctl restart", "pg_ctl stop",
                   "read_text(ENV_FILE)", "ENV_FILE.read_text("):
        assert unsafe not in src
