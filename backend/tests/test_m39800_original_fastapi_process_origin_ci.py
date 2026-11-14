"""M39800: original FR Finance port 8000 process provenance, read-only."""
from __future__ import annotations
import os
from pathlib import Path

import pytest

from backend.scripts import frfinance_m39800_running_process_origin_readonly as m

ROOT=Path(__file__).resolve().parents[2]

TCP_TEXT=(
    " sl local_address rem_address st tx_queue rx_queue tr tm->when retrnsmt uid timeout inode\n"
    "0: 0100007F:1F40 00000000:0000 0A 00000000:00000000 00:00000000 00000000 1024 0 98765 1\n"
    "1: 0100007F:1538 00000000:0000 0A 00000000:00000000 00:00000000 00000000 1024 0 87654 1\n"
    "2: 0100007F:1F40 00000000:0000 01 00000000:00000000 00:00000000 00000000 1024 0 76543 1\n"
)


def valid_argv():
    return ["python3","-m","uvicorn","app.main:app",
            "--host","127.0.0.1","--port","8000","--no-access-log"]


def test_local_8000_socket_is_separate_from_fr22_and_established_connections():
    assert m.listening_inodes(TCP_TEXT)=={"98765"}
    assert m.listening_inodes(TCP_TEXT.replace("1F40","1F41"))==set()


@pytest.mark.parametrize("args,cwd,expected",[
 (valid_argv(),ROOT,"ORIGINAL_FR_FINANCE_UVICORN_PROCESS"),
 (valid_argv(),Path("/tmp/frcaixinha22"),"WRONG_WORKTREE"),
 (["python3","-m","uvicorn","other.main:app","--host","127.0.0.1","--port","8000"],
  ROOT,"UNRECOGNIZED_COMMAND"),
 (["python3","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8000"],
  ROOT,"UNRECOGNIZED_COMMAND"),
 (["python3","-m","uvicorn","app.main:app","--host","127.0.0.1","--port","5432"],
  ROOT,"UNRECOGNIZED_COMMAND"),
 (valid_argv()+["--reload"],ROOT,"UNRECOGNIZED_COMMAND"),
 (valid_argv()+["--workers","3"],ROOT,"UNRECOGNIZED_COMMAND"),
 (["python3","backend/scripts/run_termux_fastapi.sh"],ROOT,"UNRECOGNIZED_COMMAND"),
 ([],ROOT,"UNRECOGNIZED_COMMAND"),
])
def test_argv_never_matches_wrong_app_or_worktree(args,cwd,expected):
    assert m.classify_argv(args,cwd)==expected


def make_proc(tmp_path,argv=valid_argv(),cwd=ROOT):
    proc=tmp_path/"proc"
    proc.mkdir()
    pid=proc/"9999"
    pid.mkdir()
    (pid/"fd").mkdir()
    (pid/"fd"/"5").symlink_to("socket:[98765]")
    (pid/"cwd").symlink_to(cwd)
    (pid/"cmdline").write_bytes(
        b"\0".join(x.encode() for x in argv)+b"\0"
    )
    return proc


def test_same_uid_owner_and_original_cwd(tmp_path):
    proc=make_proc(tmp_path)
    owners,status=m.owners_for_inodes({"98765"},proc)
    assert status=="SOCKET_OWNER_CLASSIFIED"
    assert owners==["ORIGINAL_FR_FINANCE_UVICORN_PROCESS"]
    assert m.owners_for_inodes({"77777"},proc)==(
        [],"OWNER_NOT_VISIBLE_ANDROID")


def test_rejects_wrong_process_worktree_and_ambiguous_socket(tmp_path):
    proc=make_proc(tmp_path,cwd=Path("/tmp/FR22"))
    owners,status=m.owners_for_inodes({"98765"},proc)
    assert owners==["WRONG_WORKTREE"]
    other=proc/"8888"
    other.mkdir()
    (other/"fd").mkdir()
    (other/"fd"/"5").symlink_to("socket:[98765]")
    (other/"cwd").symlink_to(ROOT)
    (other/"cmdline").write_bytes(b"\0".join(x.encode()
                               for x in valid_argv())+b"\0")
    tcp=tmp_path/"tcp"
    tcp.write_text(TCP_TEXT)
    original_owners=m.owners_for_inodes
    monkey=pytest.MonkeyPatch()
    try:
        monkey.setattr(m,"TCP",tcp)
        monkey.setattr(m,"owners_for_inodes",
                        lambda _: original_owners({"98765"},proc))
        monkey.setattr(m,"read_json_loopback",
                        lambda _: (200,{"app":"FR Finance","status":"ONLINE"}))
        result=m.review_origin()
    finally:
        monkey.undo()
    assert result["M39800_PROCESS_ORIGIN"]=="AMBIGUOUS_OR_NOT_VISIBLE"
    assert result["M39800_STATUS"]=="BLOCKED_NO_PROCESS_PROOF"


def test_wrong_health_never_reads_proc(monkeypatch):
    monkeypatch.setattr(m,"read_json_loopback",
      lambda _: (200,{"app":"FR Caixinha 2.2","status":"ONLINE"}))
    monkeypatch.setattr(m,"owners_for_inodes",
      lambda _: pytest.fail("unexpected proc scan"))
    out=m.review_origin()
    assert out["M39800_PROCESS_ORIGIN"]=="BLOCKED_UNKNOWN_APP"
    assert out["M39800_STATUS"]=="BLOCKED_NO_PROCESS_PROOF"


def test_android_proc_restrictions_are_explicit_not_success(monkeypatch,tmp_path):
    monkeypatch.setattr(m,"TCP",tmp_path/"no-proc")
    monkeypatch.setattr(m,"read_json_loopback",
      lambda _: (200,{"app":"FR Finance","status":"ONLINE"}))
    out=m.review_origin()
    assert out["M39800_PROC"]=="ANDROID_PROC_RESTRICTED"
    assert out["M39800_STATUS"]=="BLOCKED_NO_PROCESS_PROOF"


def test_original_owner_attested_only_when_unique(monkeypatch,tmp_path):
    tcp=tmp_path/"tcp"
    tcp.write_text(TCP_TEXT)
    monkeypatch.setattr(m,"TCP",tcp)
    monkeypatch.setattr(m,"owners_for_inodes",
      lambda _: (["ORIGINAL_FR_FINANCE_UVICORN_PROCESS"],
                 "SOCKET_OWNER_CLASSIFIED"))
    monkeypatch.setattr(m,"read_json_loopback",
      lambda _: (200,{"app":"FR Finance","status":"ONLINE"}))
    out=m.review_origin()
    assert out["M39800_PROCESS_ORIGIN"]=="ORIGINAL_FR_FINANCE_UVICORN_PROCESS"
    assert out["M39800_STATUS"]=="PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED"


def test_cli_native_gate_no_proc_or_http_when_wrong_environment(monkeypatch,capsys):
    monkeypatch.setattr(m,"native_termux",lambda:False)
    monkeypatch.setattr(m,"review_origin",
      lambda: pytest.fail("should not probe"))
    assert m.main()==2
    assert "M39800_STATUS=BLOCKED_NOT_NATIVE_FR_FINANCE" in (
        capsys.readouterr().out)


def test_cli_success_never_prints_pid_or_env_or_commands(monkeypatch,capsys):
    monkeypatch.setattr(m,"native_termux",lambda:True)
    monkeypatch.setattr(m,"review_origin",lambda: {
        "M39800_STATUS":"PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED",
        "M39800_PROCESS_ORIGIN":"ORIGINAL_FR_FINANCE_UVICORN_PROCESS",
    })
    assert m.main()==0
    output=capsys.readouterr().out
    assert "M39800_PIDS_EXPOSED=NONE" in output
    assert "M39800_COMMANDS_EXPOSED=NONE" in output
    assert "M39800_FASTAPI_RESTART=NONE" in output
    assert "M39800_DB_WRITES=NONE" in output
    assert "98765" not in output
    assert "9999" not in output


def test_no_mutation_or_credentials_in_new_process_inspector():
    src=(ROOT/"backend/scripts/frfinance_m39800_running_process_origin_readonly.py").read_text()
    for forbidden in (
        "os.kill(", "subprocess.run(", "subprocess.Popen(",
        "signal.SIGTERM", "signal.SIGKILL", "pg_ctl start", "pg_ctl stop",
        "psycopg", "asyncpg.connect(", "getpass", "print(argv)",
        "print(cmd)", "print(pid)", "CREATE DATABASE",
    ):
        assert forbidden not in src
    assert '"/proc/net/tcp"' in src
    assert '"0100007F:1F40"' in src
    assert '"/api/health"' in src
