"""Offline synthetic CI for M40170 WAL metadata and recovery decision."""
import os
from pathlib import Path
import pytest

from backend.scripts import frfinance_m40170_post_android_wal_readonly as m


def setup_tree(root):
    root.mkdir()
    (root / "000000010000000000000001").write_bytes(b"segment-synthetic")
    (root / "archive_status").mkdir()


def test_wal_metadata_only(tmp_path):
    wal = tmp_path / "pg_wal"
    setup_tree(wal)
    assert m.wal_layout(wal) == "SEGMENT_FILES_PRESENT_CONTENT_NOT_VERIFIED"
    (wal / "000000010000000000000001").unlink()
    assert m.wal_layout(wal) == "NO_WAL_SEGMENT_OBSERVED"
    link = tmp_path / "linked"
    link.symlink_to(wal, target_is_directory=True)
    assert m.wal_layout(link) == "BLOCKED_WAL_DIRECTORY_OR_SYMLINK"


def test_wal_invalid_regular_file(tmp_path):
    wal = tmp_path / "pg_wal"
    wal.mkdir()
    (wal / "000000010000000000000001").symlink_to(tmp_path / "no")
    assert m.wal_layout(wal) == "BLOCKED_WAL_SEGMENT_NOT_REGULAR"


def test_tablespace_scope(tmp_path):
    sp = tmp_path / "pg_tblspc"
    sp.mkdir()
    assert m.tablespace_layout(sp) == "NO_EXTERNAL_TABLESPACE_POINTERS"
    (sp / "12345").symlink_to(tmp_path, target_is_directory=True)
    assert m.tablespace_layout(sp) == (
        "EXTERNAL_TABLESPACES_PRESENT_BACKUP_SCOPE_UNKNOWN"
    )
    (sp / "12345").unlink()
    (sp / "unexpected").write_text("x")
    assert m.tablespace_layout(sp) == "TABLESPACE_LAYOUT_REQUIRES_REVIEW"


@pytest.mark.parametrize("gib,bucket", [
    (0.5, "BELOW_1_GIB"),
    (2, "FROM_1_TO_4_GIB"),
    (10, "FROM_4_TO_16_GIB"),
    (20, "AT_LEAST_16_GIB"),
])
def test_space_bucket(gib, bucket):
    class FakeFS:
        f_frsize = 1024
        f_bavail = int(gib * m.GIB / f_frsize)
    assert m.free_space(path="/synthetic", statvfs=lambda _: FakeFS()) == bucket


def defaults(**changed):
    inputs = {
        "project": lambda: "PASS_STATIC_ORIGINAL_FR_FINANCE_PG18",
        "status": lambda: "ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED",
        "ready": lambda: "PORT_5433_NO_RESPONSE",
        "structure": lambda: "PASS_SHALLOW_ORIGINAL_FILES_PRESENT_NOT_INTEGRITY",
        "control": lambda: "NON_CLEAN_OR_RUNNING_STATE_REPORTED",
        "wal": lambda: "SEGMENT_FILES_PRESENT_CONTENT_NOT_VERIFIED",
        "tablespaces": lambda: "NO_EXTERNAL_TABLESPACE_POINTERS",
        "space": lambda: "FROM_4_TO_16_GIB",
    }
    inputs.update(changed)
    return m.report(**inputs)


def test_nominal_cannot_start():
    r = defaults()
    assert r["M40170_STATUS"] == (
        "BLOCKED_BACKUP_AND_CONTROLLED_RECOVERY_APPROVAL_PENDING"
    )
    assert r["M40170_PG_START_AUTHORIZED"] == "FALSE"
    assert r["M40170_FASTAPI_START_AUTHORIZED"] == "FALSE"
    assert r["M40170_WAL_INTEGRITY"] == "NOT_ATTESTED"
    assert r["M40170_POST_MIGRATION_BACKUP"] == "NOT_ATTESTED"
    assert r["M40170_BACKUP_CAPACITY"] == "NOT_ATTESTED"


@pytest.mark.parametrize("changes,status", [
    ({"project": lambda: "BLOCKED_ORIGINAL"}, "BLOCKED_WRONG_PROJECT"),
    ({"status": lambda: "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING"},
     "BLOCKED_PG_MUST_BE_OFFLINE"),
    ({"structure": lambda: "BLOCKED_ORIGINAL"}, "BLOCKED_ORIGINAL_LAYOUT"),
    ({"control": lambda: "CLEAN_SHUTDOWN_STATE_REPORTED"},
     "BLOCKED_CONTROL_STATE_CHANGED"),
    ({"wal": lambda: "NO_WAL_SEGMENT_OBSERVED"}, "BLOCKED_WAL_LAYOUT_NOT_ATTESTED"),
    ({"tablespaces": lambda: "EXTERNAL_TABLESPACES_PRESENT_BACKUP_SCOPE_UNKNOWN"},
     "BLOCKED_TABLESPACE_BACKUP_SCOPE_REVIEW"),
    ({"space": lambda: "BELOW_1_GIB"}, "BLOCKED_DISK_SPACE"),
])
def test_fail_closed(changes, status):
    assert defaults(**changes)["M40170_STATUS"] == status


def test_project_gate_prevents_probes():
    def must_not_be_called():
        pytest.fail("No original PG probe without project isolation")
    r = defaults(project=lambda: "BLOCKED_ORIGINAL",
                 status=must_not_be_called, ready=must_not_be_called,
                 wal=must_not_be_called, tablespaces=must_not_be_called)
    assert r["M40170_STATUS"] == "BLOCKED_WRONG_PROJECT"


def test_changed_cluster_fails_closed():
    statuses = iter(("ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED",
                     "ORIGINAL_PGDATA_PROCESS_REPORTED_RUNNING"))
    r = defaults(status=lambda: next(statuses))
    assert r["M40170_STATUS"] == "BLOCKED_CLUSTER_CHANGED_DURING_CHECK"


def test_source_only_and_native_gate(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40170_LIVE_CLUSTER=NOT_QUERIED" in capsys.readouterr().out
    assert m.main([]) == 2


def test_source_does_not_contain_mutating_calls():
    source=(Path(__file__).resolve().parents[2] /
        "backend/scripts/frfinance_m40170_post_android_wal_readonly.py"
    ).read_text(encoding="utf-8")
    for required in ("M40170_DATABASE_WRITES=NONE",
                     "M40170_PG_START_STOP=NONE",
                     "M40170_FASTAPI_START_STOP=NONE",
                     "M40170_PRODUCTION=BLOCKED"):
        assert required in source
    for forbidden in ("os.kill(", "subprocess.Popen(", "psycopg.connect(",
                      "asyncpg.connect(", "pg_resetwal", "pg_ctl start",
                      "pg_ctl restart", "shutil.copy", "os.remove(",
                      ".unlink(", "mkdir(", "shell=True"):
        assert forbidden not in source
