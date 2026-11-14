"""M39700: loaded FastAPI version, credit 404 and ready gate are distinct.

Pure mocks/CI local FastAPI only. No original PG18, no browser, no writes.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from urllib.error import HTTPError

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.m39700_runtime_contract import (
    CONTRACT, EXPECTED_GET, checkpoint_payload, classify_checkpoint,
    classify_health, classify_readiness, classify_routes,
)

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/frfinance_m39700_termux_runtime_check.py"
spec = importlib.util.spec_from_file_location("m39700_probe", SCRIPT)
assert spec and spec.loader
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_real_fastapi_checkpoint_no_secrets_no_database():
    with TestClient(app) as client:
        response = client.get("/api/health/checkpoint")
        openapi = client.get("/openapi.json").json()
    assert response.status_code == 200
    assert "no-store" in response.headers["cache-control"]
    assert response.json() == checkpoint_payload()
    assert classify_checkpoint(response.json()) == "M39700_RUNNING_CODE_LOADED"
    assert "/api/health/checkpoint" not in openapi["paths"]
    assert response.json()["production_authorized"] is False
    assert response.json()["database_catalog_attested"] is False
    assert response.json()["repository_head_verified"] is False
    assert response.json()["real_pix_enabled"] is False
    assert response.json()["real_payments_enabled"] is False
    assert CONTRACT == "FR_FINANCE_M39700_RUNTIME_V1"


@pytest.mark.parametrize("tamper", [
    {"product": "FR Caixinha 2.2"},
    {"workstream": "FRCAIXINHA_2_2"},
    {"contract": "FR_FINANCE_M39000_RUNTIME_V1"},
    {"runtime_contract_loaded": 1},
    {"repository_head_verified": True},
    {"database_catalog_attested": True},
    {"bank_reconciled": True},
    {"real_pix_enabled": True},
    {"real_payments_enabled": True},
    {"production_authorized": True},
    {"injected_secret": "must_not_be_accepted"},
])
def test_checkpoint_fail_closed_on_wrong_product_or_fake_evidence(tamper):
    body = checkpoint_payload()
    body.update(tamper)
    assert classify_checkpoint(body) == "RUNTIME_CONTRACT_INVALID"


@pytest.mark.parametrize("bad", [None, True, [], "FR Finance", {}, {"app":"FR Finance","status":"STOPPED"}])
def test_health_fail_closed(bad):
    assert classify_health(bad) == "WRONG_APP_OR_HEALTH"


def test_get_routes_must_be_present_in_runtime_openapi():
    document = {"paths": {p:{"get":{"summary":"GET"}} for p in EXPECTED_GET}}
    assert classify_routes(document) == ("GET_ROUTES_PRESENT", ())
    document["paths"]["/api/v1/tenants/{tenant_id}/special-credit/capabilities"] = {
        "post": {}}
    state,missing = classify_routes(document)
    assert state == "GET_ROUTES_MISSING"
    assert missing == (
        "/api/v1/tenants/{tenant_id}/special-credit/capabilities",)
    assert classify_routes({"paths": []}) == ("OPENAPI_INVALID", ())
    assert classify_routes({"paths": {"x": {"get": True}}})[0] == "GET_ROUTES_MISSING"


@pytest.mark.parametrize("http_state,payload,expected", [
    (200, {"status":"READY_FOR_TEST_AUTH","scope":"LOCAL_HOMOLOGATION_ONLY"}, "LOCAL_TEST_AUTH_READY"),
    (200, {"status":"READY_FOR_TEST_AUTH","scope":"PRODUCTION"}, "BLOCKED_READINESS_NOT_ATTESTED"),
    (200, {"status":"ONLINE"}, "BLOCKED_READINESS_NOT_ATTESTED"),
    (503, None, "BLOCKED_READINESS_503_AUTH_OR_PG18_REVIEW"),
    (0, None, "BLOCKED_READINESS_NOT_ATTESTED"),
    (404, {}, "BLOCKED_READINESS_NOT_ATTESTED"),
])
def test_ready_only_attests_existing_local_test_auth(http_state,payload,expected):
    assert classify_readiness(http_state,payload) == expected


def valid_responses():
    return {
        "/api/health": (200, {"app":"FR Finance","status":"ONLINE"}),
        "/api/health/checkpoint": (200, checkpoint_payload()),
        "/openapi.json": (200, {"paths": {r:{"get":{}} for r in EXPECTED_GET}}),
        "/api/health/ready": (
            200, {"status":"READY_FOR_TEST_AUTH","scope":"LOCAL_HOMOLOGATION_ONLY"}),
    }


@pytest.mark.parametrize("path,response,expected", [
    ("/api/health", (0,None), "BLOCKED_RUNNING_API_OR_VERSION"),
    ("/api/health", (200,{"app":"FR Caixinha 2.2","status":"ONLINE"}), "BLOCKED_RUNNING_API_OR_VERSION"),
    ("/api/health/checkpoint", (404,None), "BLOCKED_RUNNING_API_OR_VERSION"),
    ("/api/health/checkpoint", (200,{"contract":"OLD"}), "BLOCKED_RUNNING_API_OR_VERSION"),
    ("/openapi.json", (404,None), "BLOCKED_RUNNING_API_OR_VERSION"),
    ("/openapi.json", (200,{"paths":{}}), "BLOCKED_RUNNING_API_OR_VERSION"),
    ("/api/health/ready", (503,None), "BLOCKED_AUTH_OR_DB_READINESS"),
    ("/api/health/ready", (200,{"status":"READY_FOR_TEST_AUTH","scope":"PRODUCTION"}), "BLOCKED_AUTH_OR_DB_READINESS"),
])
def test_combined_runtime_blocks_partial_or_fake_pass(path,response,expected):
    cases = valid_responses()
    cases[path] = response
    assert probe.review_runtime(lambda name: cases[name])["M39700_STATUS"] == expected


def test_combined_runtime_pass_only_when_all_four_checks_pass():
    report = probe.review_runtime(lambda name: valid_responses()[name])
    assert report["M39700_STATUS"] == "PASS_READ_ONLY_RUNTIME_AND_TEST_AUTH"
    assert report["M39700_MISSING_GET_ROUTES_COUNT"] == "0"
    assert report["M39700_AUTH_READINESS"] == "LOCAL_TEST_AUTH_READY"


def test_only_four_fixed_loopback_get_requests_are_allowed(monkeypatch):
    seen = []
    class Reply:
        status = 200
        def __enter__(self): return self
        def __exit__(self,*args):return None
        def read(self,n):
            assert n <= 2_000_001
            return b'{"app":"FR Finance","status":"ONLINE"}'
    def simulate(request,timeout):
        assert request.get_method() == "GET"
        assert timeout == 4
        assert request.full_url.startswith("http://127.0.0.1:8000/")
        assert request.get_header("Authorization") is None
        seen.append(request.full_url)
        return Reply()
    monkeypatch.setattr(probe,"urlopen",simulate)
    for path in probe.PATHS:
        code, _ = probe.read_json_loopback(path)
        assert code == 200
    assert len(seen) == 4
    with pytest.raises(ValueError,match="NON_ALLOWLISTED_READ"):
        probe.read_json_loopback("/api/v1/tenants/something")


def test_http_404_is_not_parsed_as_error_body(monkeypatch):
    def error(request,timeout):
        raise HTTPError(request.full_url,404,"Not Found",{},None)
    monkeypatch.setattr(probe,"urlopen",error)
    assert probe.read_json_loopback("/api/health/checkpoint") == (404,None)


def test_offline_source_mode_cannot_claim_runtime_ready():
    result = subprocess.run(
        [sys.executable,"-B",str(SCRIPT),"--source-only"],
        capture_output=True,text=True,cwd=ROOT,check=True)
    assert "M39700_STATUS=PASS_SOURCE_ONLY_NO_RUNTIME_ATTESTATION" in result.stdout
    assert "M39700_DIRECT_DB_CONNECTIONS=NONE" in result.stdout
    assert "M39700_FASTAPI_RESTART=NONE" in result.stdout
    assert "M39700_PRODUCTION=BLOCKED" in result.stdout


def test_cli_refuses_wrong_environment_without_network(monkeypatch,capsys):
    monkeypatch.setattr(probe,"native_termux",lambda:False)
    monkeypatch.setattr(probe,"source_loaded",lambda:True)
    monkeypatch.setattr(probe,"read_json_loopback",lambda _:pytest.fail("unexpected http"))
    assert probe.main([]) == 2
    assert "M39700_STATUS=BLOCKED_NOT_NATIVE_TERMUX_PROJECT" in capsys.readouterr().out


def test_no_sensitive_or_mutating_operations_in_implementation():
    source = SCRIPT.read_text()
    assert 'BASE = "http://127.0.0.1:8000"' in source
    assert 'method="GET"' in source
    assert "getpass" not in source
    assert "psycopg" not in source
    assert "subprocess" not in source
    assert "os.kill(" not in source
    assert "pg_ctl" not in source
    assert "M39700_MIGRATIONS=NONE" in source
    assert "M39700_PRODUCTION=BLOCKED" in source
