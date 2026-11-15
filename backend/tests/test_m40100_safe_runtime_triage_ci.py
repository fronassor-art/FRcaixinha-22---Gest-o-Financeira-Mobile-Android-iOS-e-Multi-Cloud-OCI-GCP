"""M40100 regression tests: status codes and same-UID candidate uncertainty."""
from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from backend.scripts import frfinance_m40100_safe_runtime_triage as m
from backend.app.m39700_runtime_contract import checkpoint_payload
from backend.app.m40080_loaded_source_marker import import_fingerprint_payload

GOOD = {"app": "FR Finance", "status": "ONLINE"}


def fetch_pair(checkpoint=404, marker=404, health=GOOD, second=GOOD):
    count = 0
    def fetch(path):
        nonlocal count
        if path == m.HEALTH:
            count += 1
            return 200, health if count == 1 else second
        if path == m.CHECKPOINT:
            return checkpoint, checkpoint_payload() if checkpoint == 200 else None
        if path == m.MARKER:
            return marker, import_fingerprint_payload() if marker == 200 else None
        raise AssertionError("unexpected path")
    return fetch


def review(fetch):
    return m.report(fetch, lambda:"ONE_SAME_UID_COMMAND_CANDIDATE_NOT_SOCKET_OWNER",
                    lambda:"ANDROID_SOCKET_VISIBILITY_PARTIAL_OR_RESTRICTED")


def test_actual_user_case_two_missing_checkpoints():
    x = review(fetch_pair())
    assert x["M40100_HEALTH_STATUS"] == "FR_FINANCE_ONLINE_DOUBLE_CHECKED"
    assert x["M40100_M39700_HTTP"] == "HTTP_404"
    assert x["M40100_M40080_HTTP"] == "HTTP_404"
    assert x["M40100_STATUS"] == "BLOCKED_PRE_M39700_RUNTIME_LIKELY_NOT_PROVEN"
    assert x["M40100_PORT_OWNER_VERIFIED"] == "FALSE"
    assert x["M40100_RESTART_AUTHORIZED"] == "FALSE"
    assert x["M40100_POSTGRESQL_CHECK"] == "NOT_PERFORMED"


@pytest.mark.parametrize("checkpoint,marker,expected", [
    (503,404,"BLOCKED_M40080_MARKER_ABSENT"),
    (404,503,"BLOCKED_M39700_CHECKPOINT_NOT_ATTESTED"),
    (200,404,"BLOCKED_M40080_MARKER_ABSENT"),
    (404,200,"BLOCKED_M39700_CHECKPOINT_NOT_ATTESTED"),
    (200,200,"BLOCKED_RUNTIME_OWNER_NOT_ATTESTED"),
])
def test_statuses_are_not_collapsed_to_postgres_errors(checkpoint, marker, expected):
    x = review(fetch_pair(checkpoint,marker))
    assert x["M40100_STATUS"] == expected
    assert x["M40100_M39700_HTTP"] == m.status_class(checkpoint)
    assert x["M40100_M40080_HTTP"] == m.status_class(marker)


def test_foreign_api_or_identity_swap_never_reads_ps():
    def not_called():
        pytest.fail("should not enumerate processes")
    x=m.report(fetch_pair(health={"app":"FR Caixinha 2.2","status":"ONLINE"}),
               not_called,not_called)
    assert x["M40100_STATUS"] == "BLOCKED_WRONG_OR_UNKNOWN_API"
    x=m.report(fetch_pair(second={"app":"FR Caixinha 2.2","status":"ONLINE"}),
               not_called,not_called)
    assert x["M40100_STATUS"] == "BLOCKED_API_IDENTITY_CHANGED"


VALID = (
    "/data/data/com.termux/files/usr/bin/python3 -m uvicorn app.main:app "
    "--host 127.0.0.1 --port 8000 --no-access-log"
)


@pytest.mark.parametrize("line, expected", [
    (VALID,"SAME_UID_UVICORN_COMMAND_CANDIDATE"),
    ("python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000",
     "SAME_UID_UVICORN_COMMAND_CANDIDATE"),
    ("python3 -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000",
     "OTHER_COMMAND"),
    ("python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000",
     "OTHER_COMMAND"),
    ("python3 -m uvicorn app.main:app --host 127.0.0.1 --port 5433",
     "OTHER_COMMAND"),
    ("python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload",
     "OTHER_COMMAND"),
    ("sh -c 'python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000'",
     "OTHER_COMMAND"),
    ("python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2",
     "OTHER_COMMAND"),
    ("ps -u 10234 -o args=","OTHER_COMMAND"),
    ("python3 -m uvicorn app.main:app --host", "OTHER_COMMAND"),
    ("python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 secret=abc",
     "SAME_UID_UVICORN_COMMAND_CANDIDATE"),
])
def test_candidates_never_prove_socket_ownership(line,expected):
    assert m.candidate_type(line) == expected


def sample_ps(lines, returncode=0):
    def execute(argv,**kwargs):
        assert argv==list(m.PS_ARGS)
        assert kwargs["capture_output"] is True
        assert kwargs["timeout"] == m.PS_TIMEOUT_SECONDS
        assert kwargs["check"] is False
        return subprocess.CompletedProcess(argv, returncode,
                 ("\\n".join(lines)).encode(),b"")
    return execute


def test_ps_same_uid_only_and_no_raw_args_reported():
    assert m.PS_ARGS[:2] == ("ps","-u")
    assert m.candidate_snapshot(sample_ps([VALID])) == (
        "ONE_SAME_UID_COMMAND_CANDIDATE_NOT_SOCKET_OWNER")
    assert m.candidate_snapshot(sample_ps([VALID,VALID])) == (
        "MULTIPLE_SAME_UID_CANDIDATES_AMBIGUOUS")
    assert m.candidate_snapshot(sample_ps(["bash","python3 whatever"])) == (
        "NO_MATCHING_COMMAND_VISIBLE_NOT_PROOF_OF_ABSENCE")
    assert m.candidate_snapshot(sample_ps([VALID],returncode=1)) == (
        "PS_SAME_UID_UNAVAILABLE_OR_RESTRICTED")
    assert m.candidate_snapshot(lambda *a,**k: (_ for _ in ()).throw(
        subprocess.TimeoutExpired("ps",3))) == (
            "PS_SAME_UID_UNAVAILABLE_OR_RESTRICTED")


def test_source_only_does_not_touch_ps_or_http(monkeypatch,capsys):
    monkeypatch.setattr(m, "local_hashes",lambda:{"a":"a","b":"b","c":"c"})
    monkeypatch.setattr(m, "native_termux",lambda:False)
    assert m.main(["--source-only"]) == 0
    assert "M40100_RUNTIME=NOT_ATTESTED" in capsys.readouterr().out
    monkeypatch.setattr(m, "report",lambda:pytest.fail("network must be blocked"))
    assert m.main([]) == 2


def test_status_class_safe_enumeration():
    assert m.status_class(404) == "HTTP_404"
    assert m.status_class(503) == "HTTP_503"
    assert m.status_class(0) == "HTTP_NO_RESPONSE"
    assert m.status_class(200) == "HTTP_200"


def test_no_start_stop_or_sensitive_output_source_contract():
    root=Path(__file__).resolve().parents[2]
    s=(root/"backend/scripts/frfinance_m40100_safe_runtime_triage.py").read_text()
    w=(root/".github/workflows/frfinance-m40100-safe-runtime-ci.yml").read_text()
    for marker in (
        "M40100_PORT_OWNER_VERIFIED", "M40100_RESTART_AUTHORIZED",
        "M40100_FASTAPI_START_STOP_RESTART=NONE",
        "M40100_POSTGRESQL_CONNECTIONS=NONE",
        "M40100_DATABASE_WRITES=NONE",
        "M40100_MIGRATIONS=NONE",
        "M40100_PIX_REAL=OFF",
    ):
        assert marker in s
    for forbidden in (
        "os.kill(", "signal.SIG", "pg_ctl", "asyncpg.connect(",
        "psycopg.connect(", "killall", "nohup ",
        "subprocess.Popen(", "shell=True", "print(cp.stdout)",
        "print(line)", "print(args)", "print(os.environ)",
    ):
        assert forbidden not in s
    assert "test_m40100_safe_runtime_triage_ci.py" in w
    assert "M40100_PRODUCTION=BLOCKED" in w
