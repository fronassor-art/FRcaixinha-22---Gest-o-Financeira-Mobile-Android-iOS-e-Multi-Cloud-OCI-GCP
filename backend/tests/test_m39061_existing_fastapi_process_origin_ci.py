"""M39061: testes sem acesso ao /proc real, sem rede nem processo real."""
from pathlib import Path

import pytest

from backend.scripts import frfinance_m39061_existing_fastapi_process_origin as m


TCP_LINES = (
    "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
    "  0: 0100007F:1F40 00000000:0000 0A 00000000:00000000 00:00000000 00000000 1024 0 98765 1\n"
    "  1: 0100007F:1538 00000000:0000 0A 00000000:00000000 00:00000000 00000000 1024 0 88888 1\n"
    "  2: 0100007F:1F40 00000000:0000 01 00000000:00000000 00:00000000 00000000 1024 0 66666 1\n"
)


def test_8000_listener_only_and_no_other_port():
    assert m.listening_inodes(TCP_LINES) == {"98765"}
    assert not m.listening_inodes(TCP_LINES.replace("1F40", "1538"))


@pytest.mark.parametrize("argv,expected", [
    (["python3", "-B", "-m",
      "backend.scripts.frfinance_m39051_local_apk_api", "--serve"], "M39051_VISUAL_APK"),
    (["python3", "-m", "backend.scripts.frfinance_m39051_local_apk_api",
      "--check"], "M39051_OTHER_MODE"),
    (["python3", "-m", "uvicorn", "app.main:app", "--port", "8000"],
      "UVICORN_DIRECT_OR_LAUNCHER"),
    (["python3", "-m", "uvicorn", "backend.app.main:app", "--port", "8000"],
      "UVICORN_DIRECT_OR_LAUNCHER"),
    (["python3", "other.py", "secret=not_printed"], "OTHER_PROCESS"),
])
def test_private_process_command_classified_only(argv, expected):
    assert m.process_class(argv) == expected


def test_ambiguous_processes_never_identified():
    assert m.classify_listener([]) == "NOT_UNIQUELY_IDENTIFIED"
    assert m.classify_listener(["M39051_VISUAL_APK", "OTHER_PROCESS"]) == "NOT_UNIQUELY_IDENTIFIED"


def test_visual_process_never_trigger_restart(monkeypatch, tmp_path):
    tcp = tmp_path / "tcp"
    tcp.write_text(TCP_LINES)
    monkeypatch.setattr(m, "TCP_PATH", tcp)
    monkeypatch.setattr(m, "request_local", lambda path: (
        200, {"app": "FR Finance", "status": "ONLINE"}
    ))
    monkeypatch.setattr(m, "matching_owners", lambda inodes: (
        ["M39051_VISUAL_APK"], "FOUND_SAME_UID_OWNERS"
    ))
    result = m.probe_process_origin()
    assert result["M39061_PROCESS_ORIGIN"] == "M39051_VISUAL_APK"
    assert result["M39061_NEXT_STEP"] == "REVIEW_CONTROLLED_VISUAL_TO_AUTH_HANDOFF"


def test_unrelated_api_stops_before_any_proc(monkeypatch):
    monkeypatch.setattr(m, "request_local", lambda path: (
        200, {"app": "FR Caixinha 2.2", "status": "ONLINE"}
    ))
    monkeypatch.setattr(m, "matching_owners", lambda *_: pytest.fail("No proc scan"))
    assert m.probe_process_origin()["M39061_STATUS"] == "BLOCKED_EXISTING_FASTAPI_NOT_IDENTIFIED"


def test_android_proc_restricted_no_fabricated_identity(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "TCP_PATH", tmp_path / "not-available")
    monkeypatch.setattr(m, "request_local", lambda path: (
        200, {"app": "FR Finance", "status": "ONLINE"}
    ))
    out = m.probe_process_origin()
    assert out["M39061_TCP_SOCKET_INSPECTION"] == "ANDROID_PROC_TCP_RESTRICTED"
    assert out["M39061_PROCESS_ORIGIN"] == "NOT_UNIQUELY_IDENTIFIED"


def test_main_no_changes(monkeypatch, capsys):
    monkeypatch.setattr(m, "verify_original", lambda: None)
    monkeypatch.setattr(m, "probe_process_origin", lambda: {
        "M39061_PROCESS_ORIGIN": "NOT_UNIQUELY_IDENTIFIED",
        "M39061_STATUS": "PASS_READ_ONLY_PROCESS_CLASSIFICATION",
    })
    assert m.main() == 0
    out = capsys.readouterr().out
    assert "M39061_PROCESS_START_STOP=NONE" in out
    assert "M39061_PROC_ENV_READ=NONE" in out


def test_source_cannot_change_services():
    src = (Path(__file__).resolve().parents[1] /
           "scripts/frfinance_m39061_existing_fastapi_process_origin.py").read_text()
    assert "verify_original()" in src
    assert 'request_local("/api/health")' in src
    assert "M39051_VISUAL_APK" in src
    assert "socket:[" in src
    for forbidden in ("os.kill(", "kill -", "pg_ctl start", "pg_ctl stop",
                      "uvicorn.run(", "Popen(", "subprocess.run(",
                      'open("/proc/', "CREATE DATABASE", "ALTER ROLE",
                      "print(argv)", "print(raw)", "print(pid)"):
        assert forbidden not in src
