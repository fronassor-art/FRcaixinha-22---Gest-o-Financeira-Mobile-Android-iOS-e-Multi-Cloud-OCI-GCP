"""M38797: strictly synthetic filesystem WAL/storage preflight for FR Finance."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/frfinance_m38797_wal_storage_preflight.py"


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("m38797_wal_test", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stopped():
    return {
        "M38796_PROJECT": "FR_FINANCE_AI_STUDIO",
        "M38796_PROCESS": "NOT_RUNNING_REPORTED",
        "M38796_PORT_5433": "NO_RESPONSE",
        "M38796_POSTMASTER_PID": "PRESENT_UNVERIFIED_STALE",
        "M38796_PG_CONTROL_STATE": "UNCLEAN_OR_RUNNING_STATE_REPORTED",
        "M38796_OPERATION_ALLOWED": "NONE",
    }


def test_offline_runs_no_filesystem_or_pg_probe(monkeypatch, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "local_audit", lambda: pytest.fail("must be offline"))
    assert mod.main(["offline"]) == 0
    report = capsys.readouterr().out
    assert "M38797_AUDIT=OFFLINE_REFERENCE" in report
    assert "M38797_WAL_INTEGRITY=NOT_ATTESTED" in report
    assert "M38797_PG_START_STOP=NONE" in report


@pytest.mark.parametrize("args", [
    ["local"], ["local", "START_DATABASE_NOW"],
    ["offline", "AUTHORIZE_FRFINANCE_PG18_WAL_STORAGE_READONLY"],
])
def test_requires_explicit_permission_only_for_readonly(monkeypatch, args):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "local_audit", lambda: pytest.fail("not authorized"))
    assert mod.main(args) == 2


def test_only_wallet_of_FR_finance_is_scanned(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    pgdata = tmp_path / "frfinance"
    wal = pgdata / "pg_wal"
    wal.mkdir(parents=True)
    (wal / ("A" * 24)).write_bytes(b"synthetic-wal-not-real")
    (wal / "archive_status").mkdir()
    assert mod.wal_directory_state(pgdata) == "SEGMENT_FILES_OBSERVED_UNVERIFIED"


def test_empty_or_nonwal_directory_never_claims_integrity(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    wal = tmp_path / "pg_wal"
    wal.mkdir()
    (wal / "archive_status").mkdir()
    assert mod.wal_directory_state(tmp_path) == "NO_SEGMENT_FILES_OBSERVED_REVIEW"


def test_missing_wal_folder_blocks(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    with pytest.raises(mod.StoragePreflightBlocked, match="PG_WAL_DIRECTORY_MISSING"):
        mod.wal_directory_state(tmp_path)


def test_wal_folder_symlink_blocks(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    target = tmp_path / "another"
    target.mkdir()
    (tmp_path / "pg_wal").symlink_to(target, target_is_directory=True)
    with pytest.raises(mod.StoragePreflightBlocked, match="PG_WAL_LINK_REQUIRES_MANUAL_REVIEW"):
        mod.wal_directory_state(tmp_path)


def test_wal_file_symlink_not_counted_as_segment(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    wal = tmp_path / "pg_wal"
    wal.mkdir()
    linked = tmp_path / "file"
    linked.write_bytes(b"simulated")
    (wal / ("B" * 24)).symlink_to(linked)
    assert mod.wal_directory_state(tmp_path) == "NO_SEGMENT_FILES_OBSERVED_REVIEW"


def test_wal_scan_limited(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    wal = tmp_path / "pg_wal"
    wal.mkdir()
    (wal / "one").touch()
    (wal / "two").touch()
    monkeypatch.setattr(mod, "MAX_WAL_ENTRIES", 1)
    with pytest.raises(mod.StoragePreflightBlocked, match="PG_WAL_SCAN_LIMIT_REACHED"):
        mod.wal_directory_state(tmp_path)


def test_tablespace_symlink_is_reported_not_followed(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    tbl = tmp_path / "pg_tblspc"
    tbl.mkdir()
    target = tmp_path / "outside"
    target.mkdir()
    (tbl / "12345").symlink_to(target, target_is_directory=True)
    assert mod.tablespace_pointer_state(tmp_path) == (
        "EXTERNAL_POINTERS_PRESENT_MANUAL_BACKUP_REVIEW")


def test_no_tablespace_symlink_observed(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    (tmp_path / "pg_tblspc").mkdir()
    assert mod.tablespace_pointer_state(tmp_path) == "NO_EXTERNAL_POINTERS_OBSERVED"


def test_tablespace_root_symlink_blocks(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    target = tmp_path / "outside"
    target.mkdir()
    (tmp_path / "pg_tblspc").symlink_to(target, target_is_directory=True)
    with pytest.raises(mod.StoragePreflightBlocked, match="TABLESPACE_DIRECTORY_UNAVAILABLE"):
        mod.tablespace_pointer_state(tmp_path)


@pytest.mark.parametrize("bytes_available,expected", [
    (500 * 1024 ** 2, "LESS_THAN_1_GIB"),
    (2 * 1024 ** 3, "FROM_1_TO_4_GIB"),
    (7 * 1024 ** 3, "FROM_4_TO_16_GIB"),
    (30 * 1024 ** 3, "AT_LEAST_16_GIB"),
])
def test_free_space_is_only_coarse_bucket(monkeypatch, tmp_path, bytes_available, expected):
    mod = load(monkeypatch)
    def fake_statvfs(_):
        return types.SimpleNamespace(f_frsize=4096, f_bavail=bytes_available // 4096)
    monkeypatch.setattr(mod.os, "statvfs", fake_statvfs)
    assert mod.storage_space_bucket(tmp_path) == expected


def test_invalid_statvfs_blocks(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.os, "statvfs",
                        lambda _: types.SimpleNamespace(f_frsize=0, f_bavail=0))
    with pytest.raises(mod.StoragePreflightBlocked, match="STORAGE_SPACE_INVALID"):
        mod.storage_space_bucket(tmp_path)


@pytest.mark.parametrize("field,value", [
    ("M38796_PROJECT", "FR_CAIXINHA_2_2"),
    ("M38796_PG_CONTROL_STATE", "CLEAN_SHUTDOWN_REPORTED"),
    ("M38796_OPERATION_ALLOWED", "START_ALLOWED"),
])
def test_unapproved_state_never_inspects_wal(monkeypatch, field, value):
    mod = load(monkeypatch)
    result = stopped()
    result[field] = value
    monkeypatch.setattr(mod.control, "local_audit", lambda: result)
    monkeypatch.setattr(mod, "wal_directory_state",
                        lambda _: pytest.fail("no WAL read allowed"))
    with pytest.raises(mod.StoragePreflightBlocked):
        mod.local_audit()


def test_safe_report_still_requires_preservation_and_backup(monkeypatch):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.control, "local_audit", stopped)
    monkeypatch.setattr(mod, "wal_directory_state",
                        lambda _: "SEGMENT_FILES_OBSERVED_UNVERIFIED")
    monkeypatch.setattr(mod, "tablespace_pointer_state",
                        lambda _: "NO_EXTERNAL_POINTERS_OBSERVED")
    monkeypatch.setattr(mod, "storage_space_bucket",
                        lambda _: "AT_LEAST_16_GIB")
    evidence = mod.local_audit()
    assert evidence["M38797_WAL_DIRECTORY"] == "SEGMENT_FILES_OBSERVED_UNVERIFIED"
    assert evidence["M38797_WAL_INTEGRITY"] == "NOT_ATTESTED"
    assert evidence["M38797_RESTORABLE_BACKUP"] == "NOT_ATTESTED"
    assert evidence["M38797_RECOVERY_PERMISSION"] == "NOT_GRANTED"
    assert evidence["M38797_NEXT_STEP"] == "PRESERVATION_AND_BACKUP_PLAN_REQUIRED"


def test_state_race_is_blocked(monkeypatch):
    mod = load(monkeypatch)
    count = []
    def transient():
        count.append(1)
        s = stopped()
        if len(count) == 2:
            s["M38796_PORT_5433"] = "ACCEPTING"
        return s
    monkeypatch.setattr(mod.control, "local_audit", transient)
    monkeypatch.setattr(mod, "wal_directory_state",
                        lambda _: "SEGMENT_FILES_OBSERVED_UNVERIFIED")
    monkeypatch.setattr(mod, "tablespace_pointer_state",
                        lambda _: "NO_EXTERNAL_POINTERS_OBSERVED")
    monkeypatch.setattr(mod, "storage_space_bucket",
                        lambda _: "AT_LEAST_16_GIB")
    with pytest.raises(mod.StoragePreflightBlocked, match="STATE_CHANGED_DURING_INSPECTION"):
        mod.local_audit()


def test_no_real_db_commands_in_script():
    source = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "pg_ctl start", "pg_ctl stop", "pg_resetwal", "pg_restore",
        "pg_dump", "psql -", "unlink(", "rmtree(", "initdb",
        "tar -", "shutil.copytree(", "os.remove(", "os.rename(",
        "sqlalchemy", "psycopg", "INSERT INTO", "DELETE FROM",
    ):
        assert forbidden not in source
    assert "M38797_RECOVERY_PERMISSION" in source
    assert "M38797_POSTMASTER_PID_DELETE=NONE" in source
