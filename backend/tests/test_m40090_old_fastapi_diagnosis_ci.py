"""M40090: old process, Android proc restrictions, bind and fail-closed."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from backend.scripts import frfinance_m40090_old_fastapi_diagnosis as m
from backend.app.m39700_runtime_contract import checkpoint_payload
from backend.app.m40080_loaded_source_marker import import_fingerprint_payload

ROOT = Path(__file__).resolve().parents[2]
GOOD_HEALTH = {"app": "FR Finance", "status": "ONLINE"}
BAD_ORIGIN = {"M39800_STATUS": "BLOCKED_NO_PROCESS_PROOF"}
GOOD_ORIGIN = {"M39800_STATUS": "PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED"}
LOOPBACK = "IPV4_LOOPBACK_ONLY_OBSERVED"
RESTRICTED = "ANDROID_SOCKET_VISIBILITY_PARTIAL_OR_RESTRICTED"


def responses(*, marker_code=404, marker=None, checkpoint_code=200,
              first_health=None, second_health=None):
    n = [0]
    if marker is None and marker_code == 200:
        marker = import_fingerprint_payload()
    def fetch(path):
        if path == m.HEALTH:
            n[0] += 1
            return 200, (GOOD_HEALTH if (
                (n[0] == 1 and first_health is None) or
                (n[0] == 2 and second_health is None)
            ) else (first_health if n[0] == 1 else second_health))
        if path == m.CHECKPOINT:
            return checkpoint_code, checkpoint_payload() if checkpoint_code == 200 else None
        if path == m.MARKER:
            return marker_code, marker
        pytest.fail("unexpected HTTP endpoint")
    return fetch


def test_user_observation_is_old_api_without_postgres_inference():
    report=m.report(
        fetch=responses(marker_code=404),
        process=lambda:BAD_ORIGIN,scope=lambda:RESTRICTED)
    assert report["M40090_API_IDENTITY"]=="FR_FINANCE_ONLINE_DOUBLE_CHECKED"
    assert report["M40090_M39700_CHECKPOINT"]=="M39700_RUNNING_CODE_LOADED"
    assert report["M40090_M40080_IMPORT_SNAPSHOT"]==(
        "M40080_NOT_LOADED_OR_ROUTE_ABSENT")
    assert report["M40090_PROCESS_OWNER"]=="NOT_ATTESTED_ANDROID_OR_UNKNOWN"
    assert report["M40090_POSTGRES_STATUS"]=="NOT_CHECKED"
    assert report["M40090_RESTART_AUTHORIZED"]=="FALSE"
    assert report["M40090_STATUS"]==(
        "BLOCKED_M40080_ROUTE_MISSING_IN_RUNNING_API")


def test_full_match_requires_m39800_owner_and_loopback():
    yes=m.report(fetch=responses(marker_code=200),
                 process=lambda:GOOD_ORIGIN, scope=lambda:LOOPBACK)
    assert yes["M40090_STATUS"]=="PASS_RUNTIME_COMPATIBILITY_READ_ONLY_ONLY"
    no_owner=m.report(fetch=responses(marker_code=200),
                 process=lambda:BAD_ORIGIN, scope=lambda:LOOPBACK)
    assert no_owner["M40090_STATUS"]=="BLOCKED_INCOMPLETE_RUNTIME_EVIDENCE"
    no_sockets=m.report(fetch=responses(marker_code=200),
                 process=lambda:GOOD_ORIGIN, scope=lambda:RESTRICTED)
    assert no_sockets["M40090_STATUS"]=="BLOCKED_INCOMPLETE_RUNTIME_EVIDENCE"


def test_false_claim_and_non_loopback_bind_never_authorizes():
    for marker in [
        {**import_fingerprint_payload(),"production_authorized": True},
        {**import_fingerprint_payload(),"git_commit_verified": True},
        {**import_fingerprint_payload(),"main_py_sha256_at_import": "0"*64},
    ]:
        result=m.report(
            fetch=responses(marker_code=200,marker=marker),
            process=lambda:GOOD_ORIGIN,scope=lambda:LOOPBACK)
        assert result["M40090_STATUS"]=="BLOCKED_INCOMPLETE_RUNTIME_EVIDENCE"
    result=m.report(
        fetch=responses(marker_code=200),
        process=lambda:GOOD_ORIGIN,
        scope=lambda:"NON_LOOPBACK_IPV4_BIND_REVIEW_REQUIRED")
    assert result["M40090_STATUS"]=="BLOCKED_NON_LOOPBACK_BIND_REVIEW"
    assert result["M40090_RESTART_AUTHORIZED"]=="FALSE"


def test_no_health_identity_skips_process_and_socket():
    def fetch(path):
        assert path == m.HEALTH
        return 200, {"app":"FR Caixinha 2.2","status":"ONLINE"}
    def forbidden():
        pytest.fail("unknown application must not inspect the listener")
    assert m.report(fetch=fetch,process=forbidden,scope=forbidden)[
        "M40090_STATUS"]=="BLOCKED_UNKNOWN_OR_OFFLINE_API"


def test_health_changes_during_probe_denies_claim():
    def forbidden():
        pytest.fail("no /proc before stable health identity")
    r=m.report(
        fetch=responses(marker_code=200,second_health={"app":"FR Caixinha 2.2","status":"ONLINE"}),
        process=forbidden,scope=forbidden)
    assert r["M40090_STATUS"]=="BLOCKED_API_CHANGED_DURING_PROBES"


TCP_HEADER=("sl local_address rem_address st tx_queue rx_queue tr tm->when "
            "retrnsmt uid timeout inode\n")
def row(local,st="0A"):
    return f"0: {local} 00000000:0000 {st} 00000000:00000000 00:00000000 00000000 1024 0 98765\n"


def test_tcp_scope_no_socket_inode_or_command_output(tmp_path):
    v4=tmp_path/"tcp"
    v6=tmp_path/"tcp6"
    v4.write_text(TCP_HEADER+row("0100007F:1F40")+row("0100007F:1F40","01"))
    v6.write_text(TCP_HEADER)
    assert m.inspect_socket_scope(v4,v6)==LOOPBACK
    v4.write_text(TCP_HEADER+row("00000000:1F40"))
    assert m.inspect_socket_scope(v4,v6)==(
        "NON_LOOPBACK_IPV4_BIND_REVIEW_REQUIRED")
    v4.write_text(TCP_HEADER)
    v6.write_text(TCP_HEADER+row("0"*32+":1F40"))
    assert m.inspect_socket_scope(v4,v6)=="IPV6_BIND_SCOPE_NOT_ATTESTED"
    v6.unlink()
    assert m.inspect_socket_scope(v4,v6)==RESTRICTED
    v6.write_text(TCP_HEADER)
    assert m.inspect_socket_scope(v4,v6)=="PORT_8000_LISTEN_NOT_VISIBLE"
    assert m.socket_addresses(TCP_HEADER+row("0100007F:1F40","01"),
                              ipv6=False)==()


def test_only_explicit_get_loopback_no_redirect_no_proxy(monkeypatch):
    with pytest.raises(ValueError,match="NON_ALLOWLISTED"):
        m.fetch_json("https://example.invalid/a")
    with pytest.raises(ValueError,match="NON_ALLOWLISTED"):
        m.fetch_json("/api/v1/tenants/abc/credit")


def test_native_gate_blocks_network_before_any_probe(monkeypatch,capsys):
    monkeypatch.setattr(m,"native_termux",lambda:False)
    monkeypatch.setattr(m,"report",lambda:pytest.fail("not native"))
    assert m.main([])==2
    assert "M40090_STATUS=BLOCKED_NOT_NATIVE_TERMUX" in capsys.readouterr().out
    monkeypatch.setattr(m,"local_hashes",lambda:{"a":"b","c":"d","e":"f"})
    assert m.main(["--source-only"])==0
    assert "M40090_RUNTIME=NOT_ATTESTED" in capsys.readouterr().out


def test_no_mutating_commands_and_preflight_documented():
    source=(ROOT/"backend/scripts/frfinance_m40090_old_fastapi_diagnosis.py").read_text()
    flow=(ROOT/".github/workflows/frfinance-m40090-old-runtime-ci.yml").read_text()
    doc=(ROOT/"docs/FR_FINANCE_M40090_FASTAPI_ORIGEM_PLANO_NAO_INVASIVO.md").read_text()
    ast.parse(source)
    for phrase in (
        'BASE = "http://127.0.0.1:8000"',
        'method="GET"', "ProxyHandler({})",
        "M40090_FASTAPI_RESTART=NONE","M40090_POSTGRES_STATUS",
        "M40090_RESTART_AUTHORIZED", "M40090_MIGRATIONS=NONE",
        "M40090_LOCAL_DATABASE_WRITES=NONE",
    ):
        assert phrase in source
    for forbidden in ("subprocess.", "os.kill(", "signal.", "pg_ctl",
                      "psycopg", "asyncpg.connect", "socket.create_connection(",
                      "os.environ[", "os.getenv(", "requests.post(",
                      "https://api.mercadopago"):
        assert forbidden not in source
    assert "test_m40090_old_fastapi_diagnosis_ci.py" in flow
    assert "M40090_PIX_REAL=OFF" in flow
    assert "NÃO autoriza reiniciar" in doc
    assert "FR Caixinha 2.2" in doc
