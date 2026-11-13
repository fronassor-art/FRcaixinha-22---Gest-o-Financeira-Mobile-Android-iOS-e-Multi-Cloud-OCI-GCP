"""M39062: processos sintéticos do mesmo UID, nunca /proc do aparelho."""
from pathlib import Path

import pytest

from backend.scripts import frfinance_m39062_same_uid_launcher_inventory as m


def encoded(*args):
    return bytes((0,)).join(a.encode() for a in args) + bytes((0,))


@pytest.mark.parametrize("args,expected", [
    (("python3", "-m",
      "backend.scripts.frfinance_m39051_local_apk_api", "--serve"), "M39051_VISUAL_APK"),
    (("python3", "-m", "uvicorn", "app.main:app", "--port", "8000"),
     "UVICORN_DIRECT_OR_LAUNCHER"),
    (("python3", "-m", "backend.scripts.frfinance_m39051_local_apk_api", "--check"),
     None),
    (("python3", "some-other-service.py", "--secret=my_secret"), None),
])
def test_commands_classified_without_exposure(args, expected):
    assert m.classify_raw_command(encoded(*args)) == expected


def test_proc_dir_same_uid_scanned_without_probing_tcp(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    visual = proc / "900001"
    visual.mkdir()
    (visual / "cmdline").write_bytes(encoded(
        "python3", "-m", "backend.scripts.frfinance_m39051_local_apk_api", "--serve"
    ))
    other = proc / "900002"
    other.mkdir()
    (other / "cmdline").write_bytes(encoded("python3", "irrelevant.py"))
    labels, status = m.scan_same_uid_candidates(proc)
    assert labels == ["M39051_VISUAL_APK"]
    assert status == "SAME_UID_COMMANDS_SCANNED"


def test_no_proc_access_stays_unconfirmed(tmp_path):
    classes, status = m.scan_same_uid_candidates(tmp_path / "not-present")
    assert classes == []
    assert status == "ANDROID_PROC_LIST_RESTRICTED"


@pytest.mark.parametrize("classes,label,confidence", [
    (["M39051_VISUAL_APK"], "M39051_VISUAL_APK",
     "UNIQUE_MATCHED_PROCESS_NOT_SOCKET_ATTESTED"),
    (["UVICORN_DIRECT_OR_LAUNCHER"], "UVICORN_DIRECT_OR_LAUNCHER",
     "UNIQUE_MATCHED_PROCESS_NOT_SOCKET_ATTESTED"),
    ([], "NONE_IDENTIFIED", "REQUIRES_MANUAL_SUPERVISOR_REVIEW"),
    (["M39051_VISUAL_APK", "UVICORN_DIRECT_OR_LAUNCHER"],
     "MULTIPLE_LAUNCHER_CANDIDATES", "REQUIRES_MANUAL_SUPERVISOR_REVIEW"),
])
def test_explicit_no_socket_ownership_claim(classes, label, confidence):
    assert m.summarize_candidates(classes) == (label, confidence)


def test_probe_only_public_local_health(monkeypatch):
    calls = []
    def fake_health(path):
        calls.append(path)
        return 200, {"app": "FR Finance", "status": "ONLINE"}
    monkeypatch.setattr(m, "request_local", fake_health)
    monkeypatch.setattr(m, "scan_same_uid_candidates",
                        lambda: (["M39051_VISUAL_APK"], "SAME_UID_COMMANDS_SCANNED"))
    result = m.probe()
    assert calls == ["/api/health"]
    assert result["M39062_CANDIDATE_CLASS"] == "M39051_VISUAL_APK"
    assert result["M39062_SOCKET_OWNER_ATTESTED"] == "NO_ANDROID_PROC_RESTRICTION"
    assert result["M39062_HANDOFF"] == "NO_AUTOMATIC_STOP_OR_RESTART"


def test_different_api_does_not_scan_proc(monkeypatch):
    monkeypatch.setattr(m, "request_local", lambda _: (
        200, {"app": "FR Caixinha 2.2", "status": "ONLINE"}
    ))
    monkeypatch.setattr(m, "scan_same_uid_candidates",
                        lambda: pytest.fail("Must not scan wrong project"))
    assert m.probe()["M39062_STATUS"] == "BLOCKED_ACTIVE_API_NOT_FR_FINANCE"


def test_main_never_shows_pid_or_arguments(monkeypatch, capsys):
    monkeypatch.setattr(m, "verify_original", lambda: None)
    monkeypatch.setattr(m, "probe", lambda: {
        "M39062_STATUS": "PASS_READ_ONLY_INVENTORY",
        "M39062_CANDIDATE_CLASS": "M39051_VISUAL_APK",
    })
    assert m.main() == 0
    out = capsys.readouterr().out
    assert "M39062_PROCESS_START_STOP=NONE" in out
    assert "M39062_PROC_ENV=NOT_READ" in out
    assert "M39062_PRODUCTION=BLOCKED" in out


def test_no_mutating_operations():
    code = (Path(__file__).resolve().parents[1] /
            "scripts/frfinance_m39062_same_uid_launcher_inventory.py").read_text()
    assert "verify_original()" in code
    assert "os.scandir(root)" in code
    assert "directory / \"cmdline\"" in code
    assert 'request_local("/api/health")' in code
    for forbidden in ("kill(", "pg_ctl start", "pg_ctl stop", "uvicorn.run(",
                      "subprocess.Popen(", "CREATE DATABASE", "ALTER ROLE ",
                      "print(argv)", "print(raw)", "print(uid)", "print(name)"):
        assert forbidden not in code
