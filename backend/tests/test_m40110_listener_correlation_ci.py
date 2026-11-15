"""M40110 guards: no remote service access or PID disclosure."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import pytest

from backend.scripts import frfinance_m40110_listener_correlation_readonly as m

VALID=("/data/data/com.termux/files/usr/bin/python3 -m uvicorn app.main:app "
       "--host 127.0.0.1 --port 8000 --no-access-log")
HEALTH={"app":"FR Finance","status":"ONLINE"}


def test_ps_exact_uid_command_and_ambiguous_candidates():
    def ps(lines,rc=0):
        def run(cmd,**kwargs):
            assert cmd==["ps","-u",str(os.getuid()),"-o","pid=,args="]
            assert kwargs["timeout"]==m.TIMEOUT
            return subprocess.CompletedProcess(cmd,rc,
                       ("\n".join(lines)).encode(),b"")
        return run
    assert m.own_uid_candidates(ps(["123 "+VALID]))==({123},"PS_ONE_CANDIDATE")
    assert m.own_uid_candidates(ps(["123 "+VALID,"456 "+VALID]))[1]==(
        "PS_AMBIGUOUS_OR_NOT_VISIBLE")
    assert m.own_uid_candidates(ps(["123 python3 another.py"]))[0]==set()
    assert m.own_uid_candidates(ps(["123 "+VALID],rc=1))[1]=="PS_NOT_ATTESTED"


@pytest.mark.parametrize("payload,status",[
    (b"p123\nf4u\nn127.0.0.1:8000\n","LSOF_SINGLE_LOOPBACK_LISTENER"),
    (b"p123\nn0.0.0.0:8000\n","LSOF_NON_LOOPBACK_OR_IPV6_REVIEW"),
    (b"p123\nn[::1]:8000\n","LSOF_NON_LOOPBACK_OR_IPV6_REVIEW"),
    (b"p123\nn127.0.0.1:8000\np456\nn127.0.0.1:8000\n","LSOF_AMBIGUOUS"),
    (b"p123\n","LSOF_NO_LISTENER_ATTESTED"),
    (b"n127.0.0.1:8000\n","LSOF_UNVERIFIED"),
    (b"pBAD\nn127.0.0.1:8000\n","LSOF_UNVERIFIED"),
])
def test_strict_lsof_parse(payload,status):
    ids,out=m.parse_lsof(payload)
    assert out==status
    assert bool(ids)==(status=="LSOF_SINGLE_LOOPBACK_LISTENER")


def test_missing_lsof_or_os_restriction_fails_closed():
    assert m.lsof_listeners(which=lambda _:None)==(
        set(),"LSOF_NOT_INSTALLED_NO_INSTALL")
    def fake(cmd,**kwargs):
        assert cmd[1:]==["-nP","-a","-iTCP:8000","-sTCP:LISTEN","-Fpn"]
        return subprocess.CompletedProcess(cmd,0,
                  b"p123\nf4u\nn127.0.0.1:8000\n",b"")
    assert m.lsof_listeners(which=lambda _:"/usr/bin/lsof",run=fake)==(
        {123},"LSOF_SINGLE_LOOPBACK_LISTENER")
    def blocked(*args,**kwargs):
        raise subprocess.TimeoutExpired("lsof",4)
    assert m.lsof_listeners(which=lambda _:"/usr/bin/lsof",run=blocked)[1]==(
        "LSOF_UNAVAILABLE_OR_ANDROID_RESTRICTED")


def test_prove_only_matched_ps_socket_and_worktree():
    calls=[]
    def work(pid):
        calls.append(pid)
        return "EXACT_FR_FINANCE_WORKTREE"
    x=m.correlate(lambda:({123},"PS_ONE_CANDIDATE"),
                  lambda:({123},"LSOF_SINGLE_LOOPBACK_LISTENER"),work)
    assert x["M40110_MATCH"]=="SAME_UID_COMMAND_AND_LOOPBACK_LISTENER_CORRELATED"
    assert calls==[123]
    assert x["M40110_WORKTREE"]=="EXACT_FR_FINANCE_WORKTREE"
    bad=m.correlate(lambda:({123},"PS_ONE_CANDIDATE"),
                    lambda:({456},"LSOF_SINGLE_LOOPBACK_LISTENER"),
                    lambda _:pytest.fail("must not access cwd"))
    assert bad["M40110_MATCH"]=="NOT_ATTESTED"
    assert m.correlate(lambda:({123,456},"PS_AMBIGUOUS_OR_NOT_VISIBLE"),
                       lambda:pytest.fail("skip lsof"))["M40110_MATCH"]=="NOT_ATTESTED"


def test_readlink_worktree_restrictions_and_other_project():
    def no(_):
        raise PermissionError()
    assert m.exact_worktree(123,readlink=no)=="WORKTREE_ANDROID_RESTRICTED"
    assert m.exact_worktree(123,readlink=lambda _:str(m.ROOT))==(
        "EXACT_FR_FINANCE_WORKTREE")
    assert m.exact_worktree(123,readlink=lambda _:"/root/frcaixinha22")==(
        "WORKTREE_DIFFERENT_OR_UNVERIFIED")


def test_404_rejected_as_service_upgrade_permission():
    def fetch(path):
        return (200,HEALTH) if path==m.HEALTH else (404,None)
    r=m.report(fetch,lambda:{
        "M40110_PS":"PS_ONE_CANDIDATE",
        "M40110_LSOF":"LSOF_SINGLE_LOOPBACK_LISTENER",
        "M40110_MATCH":"SAME_UID_COMMAND_AND_LOOPBACK_LISTENER_CORRELATED",
        "M40110_WORKTREE":"EXACT_FR_FINANCE_WORKTREE"})
    assert r["M40110_CHECKPOINT"]=="HTTP_404"
    assert r["M40110_MARKER"]=="HTTP_404"
    assert r["M40110_RESTART_AUTHORIZED"]=="FALSE"
    assert r["M40110_STATUS"]=="PASS_READONLY_CORRELATION_NO_RESTART_PERMISSION"


def test_foreign_api_never_scans_processes():
    def fetch(path):
        assert path==m.HEALTH
        return 200,{"app":"FR Caixinha 2.2","status":"ONLINE"}
    assert m.report(fetch,lambda:pytest.fail("must not inspect"))[
        "M40110_STATUS"]=="BLOCKED_UNKNOWN_API"


def test_cli_native_gate_and_source_only(monkeypatch,capsys):
    monkeypatch.setattr(m,"native_termux",lambda:False)
    assert m.main(["--source-only"])==0
    assert "M40110_RUNTIME=NOT_ATTESTED" in capsys.readouterr().out
    assert m.main([])==2


def test_no_process_control_in_source():
    source=(Path(__file__).resolve().parents[2]/
            "backend/scripts/frfinance_m40110_listener_correlation_readonly.py"
           ).read_text()
    for mark in (
        "M40110_RESTART_AUTHORIZED",
        "M40110_SERVICE_START_STOP=NONE",
        "M40110_FASTAPI_RESTART=NONE",
        "M40110_LOCAL_DB_WRITES=NONE",
        "M40110_MIGRATIONS=NONE","M40110_PIX_REAL=OFF",
    ):
        assert mark in source
    for forbidden in (
        "os.kill(", "signal.SIG", "pg_ctl", "psycopg.connect(",
        "asyncpg.connect(", "subprocess.Popen(", "shell=True",
        "print(cp.stdout)","print(cp.stderr)","print(pid)",
        "killall","uvicorn.run(",
    ):
        assert forbidden not in source
