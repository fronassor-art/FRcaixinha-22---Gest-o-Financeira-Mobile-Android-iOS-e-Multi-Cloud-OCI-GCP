"""FR Finance M40160 offline original control-state review (synthetic only)."""
import os
from pathlib import Path
import subprocess

import pytest

from backend.scripts import frfinance_m40160_original_pg_control_offline_readonly as m


def test_control_state_parser_no_raw_output():
    assert m.parse_control_state(b"Database cluster state: shut down\n") == (
        "CLEAN_SHUTDOWN_STATE_REPORTED"
    )
    assert m.parse_control_state(b"Database cluster state: shut down in recovery\n") == (
        "CLEAN_SHUTDOWN_STATE_REPORTED"
    )
    assert m.parse_control_state(b"Database cluster state: in production\n") == (
        "NON_CLEAN_OR_RUNNING_STATE_REPORTED"
    )
    assert m.parse_control_state(b"Database cluster state: in crash recovery\n") == (
        "NON_CLEAN_OR_RUNNING_STATE_REPORTED"
    )
    assert m.parse_control_state(b"Database cluster state: unknown-new-value\n") == (
        "CONTROL_STATE_NOT_RECOGNIZED"
    )
    assert m.parse_control_state(
        b"Database cluster state: shut down\nDatabase cluster state: in production\n"
    ) == "CONTROL_DATA_UNVERIFIED"
    assert m.parse_control_state(b"not a control output") == "CONTROL_DATA_UNVERIFIED"
    assert m.parse_control_state(b"\xff") == "CONTROL_DATA_UNVERIFIED"
    assert m.parse_control_state(b"x" * (m.MAX_CONTROL_BYTES+1)) == "CONTROL_DATA_UNVERIFIED"


def make_cluster(root):
    (root / "base").mkdir(parents=True)
    (root / "global").mkdir()
    (root / "pg_wal").mkdir()
    (root / "global" / "pg_control").write_bytes(b"synthetic")
    (root / "PG_VERSION").write_text("18\n", encoding="ascii")
    root.chmod(0o700)


def test_shallow_layout_presence_and_symlink_fail_closed(tmp_path):
    root = tmp_path / "original"
    make_cluster(root)
    assert m.original_structure(root) == "PASS_SHALLOW_ORIGINAL_FILES_PRESENT_NOT_INTEGRITY"
    (root / "PG_VERSION").write_text("17\n")
    assert m.original_structure(root) == "BLOCKED_PG_VERSION"
    (root / "PG_VERSION").write_text("18\n")
    (root / "pg_wal").rename(root / "elsewhere")
    (root / "pg_wal").symlink_to(root / "elsewhere", target_is_directory=True)
    assert m.original_structure(root) == "BLOCKED_CLUSTER_DIRECTORY_LAYOUT"


def test_pg_controldata_invoked_only_on_exact_directory(tmp_path):
    tool = tmp_path / "pg_controldata"
    tool.write_text("synthetic")
    def fake_run(args, **options):
        assert args == [str(tool), "-D", m.FINANCE_PGDATA]
        assert options["check"] is False
        assert options["timeout"] == 6
        assert options["env"]["LC_ALL"] == "C"
        assert "PGPASSWORD" not in options["env"]
        return subprocess.CompletedProcess(args, 0,
            b"Database cluster state: shut down\n", b"")
    assert m.pg_control_snapshot(run=fake_run, program=tool) == (
        "CLEAN_SHUTDOWN_STATE_REPORTED"
    )
    link = tmp_path / "link"
    link.symlink_to(tool)
    assert m.pg_control_snapshot(run=fake_run, program=link) == (
        "CONTROL_TOOL_MISSING_OR_LINKED"
    )


def test_failed_control_tool_fails_closed(tmp_path):
    tool = tmp_path / "pg_controldata"
    tool.write_text("x")
    def failed(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, b"private", b"private")
    assert m.pg_control_snapshot(run=failed, program=tool) == "CONTROL_DATA_UNVERIFIED"


def fake_report(**changes):
    state = {
        "project": lambda: "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18",
        "pgstatus": lambda: "ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED",
        "readiness": lambda: "PORT_5433_NO_RESPONSE",
        "layout": lambda: "PASS_SHALLOW_ORIGINAL_FILES_PRESENT_NOT_INTEGRITY",
        "control": lambda: "CLEAN_SHUTDOWN_STATE_REPORTED",
    }
    state.update(changes)
    return m.report(**state)


def test_clean_is_not_start_authorization():
    r = fake_report()
    assert r["M40160_STATUS"] == "BLOCKED_OFFLINE_CLEAN_REPORTED_START_NOT_AUTHORIZED"
    assert r["M40160_FULL_DATA_INTEGRITY"] == "NOT_ATTESTED"
    assert r["M40160_PG_START_AUTHORIZED"] == "FALSE"
    assert r["M40160_FASTAPI_START_AUTHORIZED"] == "FALSE"


def test_nonclean_state_requires_recovery_review():
    r = fake_report(control=lambda: "NON_CLEAN_OR_RUNNING_STATE_REPORTED")
    assert r["M40160_STATUS"] == "BLOCKED_RECOVERY_REVIEW_REQUIRED_NO_START"


def test_unknown_control_must_fail_closed():
    r = fake_report(control=lambda: "CONTROL_DATA_UNVERIFIED")
    assert r["M40160_STATUS"] == "BLOCKED_CONTROL_DATA_UNVERIFIED_NO_START"


def test_isolation_denial_skips_all_probes():
    def forbidden():
        pytest.fail("No status and no disk probe before identity")
    r = fake_report(project=lambda: "BLOCKED_ORIGINAL_CLUSTER_IDENTITY",
                    pgstatus=forbidden, readiness=forbidden,
                    layout=forbidden, control=forbidden)
    assert r["M40160_STATUS"] == "BLOCKED_ORIGINAL_CLUSTER_IDENTITY"
    assert r["M40160_PG_STATUS_BEFORE"] == "SKIPPED"


def test_running_server_denies_control_data_snapshot():
    def forbidden():
        pytest.fail("No pg_controldata while running")
    r = fake_report(pgstatus=lambda: "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING",
                    layout=forbidden, control=forbidden)
    assert r["M40160_STATUS"] == "BLOCKED_NOT_VERIFIED_OFFLINE"


def test_changed_state_after_probe_never_allows_start():
    states = iter(("ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED",
                   "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING"))
    r = fake_report(pgstatus=lambda: next(states))
    assert r["M40160_STATUS"] == "BLOCKED_CLUSTER_STATUS_CHANGED_DURING_INSPECTION"
    assert r["M40160_PG_START_AUTHORIZED"] == "FALSE"


def test_source_only_and_termux_guard(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40160_LOCAL_CLUSTER=NOT_INSPECTED" in capsys.readouterr().out
    assert m.main([]) == 2


def test_source_never_controls_services():
    code = (Path(__file__).resolve().parents[2] /
       "backend/scripts/frfinance_m40160_original_pg_control_offline_readonly.py"
    ).read_text(encoding="utf-8")
    for mark in (
        "M40160_PG_START_STOP=NONE", "M40160_FASTAPI_START_STOP=NONE",
        "M40160_DATABASE_WRITES=NONE", "M40160_MIGRATIONS=NONE",
        "M40160_PIX_REAL=OFF", "M40160_PRODUCTION=BLOCKED",
    ):
        assert mark in code
    for forbidden in (
        "os.kill(", "subprocess.Popen(", "psycopg.connect(", "asyncpg.connect(",
        "shell=True", "pg_ctl start", "pg_ctl stop", "pg_resetwal", "pg_rewind",
        "initdb", "uvicorn.run(", "read_text(ENV_FILE)",
    ):
        assert forbidden not in code
