"""FR Finance M38798: local metadata-only preservation sizing, synthetic tests."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import stat
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "backend/scripts/frfinance_m38798_cold_snapshot_capacity_readonly.py"


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(SRC.parent))
    spec = importlib.util.spec_from_file_location("m38798_snapshot_ci", SRC)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def previous_evidence():
    return {
        "M38797_PROJECT": "FR_FINANCE_AI_STUDIO",
        "M38797_PGDATA_IDENTITY": "FR_FINANCE_PG18_ONLY",
        "M38797_CONTROL": "UNCLEAN_OR_RUNNING_STATE_REPORTED",
        "M38797_WAL_DIRECTORY": "SEGMENT_FILES_OBSERVED_UNVERIFIED",
        "M38797_TABLESPACE_POINTERS": "NO_EXTERNAL_POINTERS_OBSERVED",
        "M38797_WAL_INTEGRITY": "NOT_ATTESTED",
        "M38797_RECOVERY_PERMISSION": "NOT_GRANTED",
    }


def test_offline_never_inspects_local_pgdata(monkeypatch, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "local_audit", lambda: pytest.fail("unexpected local"))
    assert mod.main(["offline"]) == 0
    out = capsys.readouterr().out
    assert "M38798_AUDIT=OFFLINE_REFERENCE_NO_FILESYSTEM_SCAN" in out
    assert "M38798_RECOVERY_PERMISSION=NOT_GRANTED" in out
    assert "M38798_BACKUP_CREATION=NONE" in out


@pytest.mark.parametrize("argv", [
    ["local"], ["local", "AUTHORIZE_BACKUP"],
    ["offline", "AUTHORIZE_FRFINANCE_PG18_SNAPSHOT_CAPACITY_READONLY"],
])
def test_explicit_authorization_before_filesystem_access(monkeypatch, argv):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "local_audit", lambda: pytest.fail("unexpected scan"))
    assert mod.main(argv) == 2


def test_recursive_metadata_counts_only_regular_files(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    root = tmp_path / "finance18"
    (root / "base" / "1").mkdir(parents=True)
    (root / "base" / "1" / "one").write_bytes(b"a" * 81)
    (root / "base" / "1" / "two").write_bytes(b"b" * 120)
    (root / "PG_VERSION").write_text("18")
    total, files, symlinks = mod.snapshot_manifest(root)
    assert (total, files, symlinks) == (203, 3, 0)


def test_internal_symlink_is_counted_but_not_followed(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    data = tmp_path / "cluster"
    data.mkdir()
    (data / "good").write_bytes(b"ok")
    secret = tmp_path / "fr22_secret"
    secret.write_bytes(b"blocked")
    (data / "foreign").symlink_to(secret)
    assert mod.snapshot_manifest(data) == (2, 1, 1)


def test_pgdata_root_symlink_blocked(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    root = tmp_path / "root"
    root.mkdir()
    (tmp_path / "link").symlink_to(root, target_is_directory=True)
    with pytest.raises(mod.SnapshotBlocked, match="PGDATA_INVALID_OR_LINKED"):
        mod.snapshot_manifest(tmp_path / "link")


def test_empty_pgdata_root_blocked(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    with pytest.raises(mod.SnapshotBlocked, match="PGDATA_INVALID_OR_LINKED"):
        mod.snapshot_manifest(tmp_path / "unknown")


def test_max_file_count_limit_blocks_without_copying(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    (tmp_path / "a").touch()
    (tmp_path / "b").touch()
    monkeypatch.setattr(mod, "MAX_ENTRIES", 1)
    with pytest.raises(mod.SnapshotBlocked, match="FILE_COUNT_LIMIT"):
        mod.snapshot_manifest(tmp_path)


def test_special_file_blocks_no_backup_approval(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    fifo = tmp_path / "socket_or_fifo"
    mod.os.mkfifo(fifo)
    with pytest.raises(mod.SnapshotBlocked, match="SPECIAL_FILE_REQUIRES_REVIEW"):
        mod.snapshot_manifest(tmp_path)


@pytest.mark.parametrize("bytes_free,expected", [
    (0, 0), (4096, 4096), (2*1024*1024, 2*1024*1024),
])
def test_free_space_computation_from_fstat(monkeypatch, tmp_path, bytes_free, expected):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.os, "statvfs",
                        lambda _: types.SimpleNamespace(f_frsize=4096,
                                                        f_bavail=bytes_free // 4096))
    assert mod._free_bytes(tmp_path) == expected


def setup_snapshot(monkeypatch, tmp_path, *, size=20*1024*1024,
                   free=8*1024**3, symlinks=0, state=None):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.wal, "local_audit",
                        lambda: previous_evidence() if state is None else state)
    monkeypatch.setattr(mod.identity, "FINANCE_PGDATA", str(tmp_path))
    monkeypatch.setattr(mod, "snapshot_manifest",
                        lambda _: (size, 450, symlinks))
    monkeypatch.setattr(mod, "_free_bytes", lambda _: free)
    return mod


def test_candidate_space_is_not_recovery_authorization(monkeypatch, tmp_path):
    mod = setup_snapshot(monkeypatch, tmp_path)
    result = mod.local_audit()
    assert result["M38798_CAPACITY_DECISION"] == (
        "ON_DEVICE_SPACE_CANDIDATE_ONLY_NO_BACKUP_APPROVAL")
    assert result["M38798_BACKUP_CREATED"] == "NO"
    assert result["M38798_BACKUP_RESTORABILITY"] == "NOT_ATTESTED"
    assert result["M38798_RECOVERY_PERMISSION"] == "NOT_GRANTED"
    assert result["M38798_PHYSICAL_MEDIA_DESTINATION"] == "NOT_SELECTED"


def test_insufficient_space_rejected_even_if_current_free_is_positive(
        monkeypatch, tmp_path):
    mod = setup_snapshot(monkeypatch, tmp_path, size=8*1024**3, free=5*1024**3)
    result = mod.local_audit()
    assert result["M38798_CAPACITY_DECISION"] == (
        "ON_DEVICE_UNCOMPRESSED_CAPACITY_INSUFFICIENT")


def test_any_symlink_flags_manual_review(monkeypatch, tmp_path):
    mod = setup_snapshot(monkeypatch, tmp_path, symlinks=2)
    result = mod.local_audit()
    assert result["M38798_CAPACITY_DECISION"] == "SYMLINKS_PRESENT_REVIEW_REQUIRED"


@pytest.mark.parametrize("change", [
    ("M38797_PROJECT", "FR_CAIXINHA_2_2"),
    ("M38797_CONTROL", "CLEAN_SHUTDOWN_REPORTED"),
    ("M38797_RECOVERY_PERMISSION", "GRANTED"),
])
def test_wrong_project_control_or_permission_blocks_before_any_scan(
        monkeypatch, tmp_path, change):
    evidence = previous_evidence()
    evidence[change[0]] = change[1]
    mod = setup_snapshot(monkeypatch, tmp_path, state=evidence)
    monkeypatch.setattr(mod, "snapshot_manifest",
                        lambda _: pytest.fail("filesystem must not be read"))
    with pytest.raises(mod.SnapshotBlocked):
        mod.local_audit()


def test_midscan_change_blocks(monkeypatch, tmp_path):
    mod = load(monkeypatch)
    count = []
    def readings():
        count.append(1)
        d = previous_evidence()
        if len(count) == 2:
            d["M38797_WAL_DIRECTORY"] = "NO_SEGMENT_FILES_OBSERVED_REVIEW"
        return d
    monkeypatch.setattr(mod.wal, "local_audit", readings)
    monkeypatch.setattr(mod.identity, "FINANCE_PGDATA", str(tmp_path))
    monkeypatch.setattr(mod, "snapshot_manifest", lambda _: (10000000, 1, 0))
    monkeypatch.setattr(mod, "_free_bytes", lambda _: 50 * 1024**3)
    with pytest.raises(mod.SnapshotBlocked, match="PREFLIGHT_CHANGED_DURING_SCAN"):
        mod.local_audit()


def test_safe_local_report_prints_no_path_or_real_contents(monkeypatch, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "local_audit", lambda: {
        "M38798_PROJECT": "FR_FINANCE_AI_STUDIO",
        "M38798_PGDATA_LOGICAL_MIB": "150",
        "M38798_CAPACITY_DECISION": "ON_DEVICE_SPACE_CANDIDATE_ONLY_NO_BACKUP_APPROVAL",
        "M38798_BACKUP_CREATED": "NO",
        "M38798_RECOVERY_PERMISSION": "NOT_GRANTED",
    })
    assert mod.main(["local", mod.AUTH]) == 0
    stdout = capsys.readouterr().out
    assert "M38798_AUDIT=LOCAL_READONLY_METADATA_CAPACITY" in stdout
    assert "M38798_BACKUP_CREATION=NONE" in stdout
    assert "M38798_FR22_ACCESS=NONE" in stdout
    assert "M38798_PRODUCTION=BLOCKED" in stdout


def test_source_contains_no_copy_or_migration_operations():
    source = SRC.read_text()
    for forbidden in (
        "pg_ctl start", "pg_resetwal", "pg_restore", "pg_dump",
        "shutil.copy", "os.remove(", "os.rename(", "unlink(",
        "tarfile.open(", "open('wb'", "open(\"wb\"",
        "rsync", "initdb", "psql ", "DROP TABLE",
    ):
        assert forbidden not in source
    assert "os.scandir" in source
    assert "os.statvfs" in source
    assert "M38798_BACKUP_CREATION=NONE" in source
