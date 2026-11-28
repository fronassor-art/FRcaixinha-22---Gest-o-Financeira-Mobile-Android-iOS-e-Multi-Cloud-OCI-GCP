"""M40080: import-time FastAPI marker, local-only read-only probe."""
from __future__ import annotations

from pathlib import Path
import ast
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.m40080_loaded_source_marker import import_fingerprint_payload
from backend.scripts import frfinance_m40080_loaded_source_readonly as probe

ROOT = Path(__file__).resolve().parents[2]
PATH = "/api/health/features/m40080"


def test_import_time_marker_is_private_data_free_and_no_db():
    with TestClient(app) as client:
        response = client.get(PATH)
        openapi = client.get("/openapi.json").json()
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert response.json() == import_fingerprint_payload()
    assert PATH not in openapi["paths"]
    assert probe.classify_marker(200,response.json(),probe.local_hashes()) == (
        "M40080_IMPORT_SNAPSHOT_MATCHES_LOCAL_FILES"
    )
    data = response.json()
    assert data["git_commit_verified"] is False
    assert data["executable_bytecode_attested"] is False
    assert data["process_owner_verified"] is False
    assert all(data[k] is False for k in probe._FALSE)
    assert "password" not in str(data).lower()
    assert "token" not in str(data).lower()


@pytest.mark.parametrize("patch",[
    {"product":"FR Caixinha 2.2"},
    {"workstream":"FR_CAIXINHA_2_2"},
    {"contract":"M40070"},
    {"source_fingerprints_captured_on_import":1},
    {"git_commit_verified":True},
    {"review_policy_ratified":True},
    {"pix_real_enabled":True},
    {"main_py_sha256_at_import":"fake"},
    {"main_py_sha256_at_import":"A"*64},
    {"main_py_sha256_at_import":123},
    {"debug":"secrets"},
])
def test_marker_fails_closed_on_client_forgery(patch):
    data=import_fingerprint_payload()
    data.update(patch)
    assert probe.classify_marker(200,data,probe.local_hashes()) == (
        "M40080_MARKER_INVALID" if patch.keys() & (
            set(probe._FALSE) | {
                "product","workstream","contract",
                "source_fingerprints_captured_on_import",
                "debug","main_py_sha256_at_import"
            }) else "M40080_LOADED_SOURCE_DIFFERS_FROM_CHECKOUT"
    )


def test_valid_but_different_fingerprint_is_stale():
    data=import_fingerprint_payload()
    data["main_py_sha256_at_import"] = "0"*64 if (
        data["main_py_sha256_at_import"] != "0"*64) else "1"*64
    assert probe.classify_marker(200,data,probe.local_hashes()) == (
        "M40080_LOADED_SOURCE_DIFFERS_FROM_CHECKOUT"
    )


def test_404_or_unknown_process_never_claims_loaded_version():
    marker=import_fingerprint_payload()
    fetch=lambda p:(200,{"app":"FR Finance","status":"ONLINE"}) if (
        p == probe.HEALTH) else (404,None)
    good=lambda:{"M39800_STATUS":"PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED"}
    r=probe.report(fetch,good)
    assert r["M40080_LOADED_SNAPSHOT"]=="M40080_NOT_LOADED_OR_ROUTE_ABSENT"
    assert r["M40080_STATUS"]=="BLOCKED_NO_COMPLETE_RUNTIME_ATTESTATION"
    fetch2=lambda p:(200,{"app":"FR Finance","status":"ONLINE"}) if (
        p == probe.HEALTH) else (200,marker)
    bad=lambda:{"M39800_STATUS":"BLOCKED_NO_PROCESS_PROOF"}
    assert probe.report(fetch2,bad)["M40080_STATUS"]==(
        "BLOCKED_NO_COMPLETE_RUNTIME_ATTESTATION"
    )
    assert probe.report(fetch2,good)["M40080_STATUS"]==(
        "PASS_OWNER_AND_IMPORT_SNAPSHOT_MATCH"
    )


def test_no_health_skips_process_and_marker():
    def only_health(p):
        assert p == probe.HEALTH
        return 200,{"app":"FR Caixinha 2.2","status":"ONLINE"}
    def fail():
        pytest.fail("must skip unknown listener")
    assert probe.report(only_health,fail)["M40080_STATUS"] == (
        "BLOCKED_WRONG_OR_UNAVAILABLE_FASTAPI"
    )


def test_source_probe_is_not_runtime_attestation(monkeypatch,capsys):
    assert probe.main(["--source-only"])==0
    printed=capsys.readouterr().out
    assert "M40080_LOADED_CODE=NOT_ATTESTED" in printed
    monkeypatch.setattr(probe,"native_termux",lambda:False)
    monkeypatch.setattr(probe,"report",lambda:pytest.fail("unexpected loopback"))
    assert probe.main([])==2


def test_no_mutating_or_external_paths():
    source=(ROOT/"backend/scripts/frfinance_m40080_loaded_source_readonly.py").read_text()
    module=(ROOT/"backend/app/m40080_loaded_source_marker.py").read_text()
    main=(ROOT/"backend/app/main.py").read_text()
    assert 'BASE = "http://127.0.0.1:8000"' in source
    assert "ProxyHandler({})" in source
    assert 'method="GET"' in source
    assert "M40080_DATABASE_WRITES=NONE" in source
    assert "@app.get(\"/api/health/features/m40080\"" in main
    for forbidden in ("getpass","psycopg.connect(", "asyncpg.connect(",
                      "subprocess.run(", "os.kill(", "killall", "pg_ctl",
                      "post(", "delete(", "requests.post(", "0.0.0.0:8000"):
        assert forbidden not in source and forbidden not in module
    ast.parse(source)
    ast.parse(module)
