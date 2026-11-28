"""FR Finance M39091 — purely synthetic route-drift diagnostics.

Imports the standard-library-only probe; no socket, Postgres or subprocess.
"""
import importlib.util
import json
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[1]/"scripts/frfinance_m39091_api_route_probe_readonly.py"
spec=importlib.util.spec_from_file_location("frfinance_m39091_probe",SCRIPT)
assert spec and spec.loader
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_git_route_contract_includes_cashboxes_and_special_credit():
    assert module.source_route_presence() is True
    assert "/api/v1/tenants/{tenant_id}/special-credit/capabilities" in module.EXPECTED
    assert "/api/v1/master/exclusive-cashbox" in module.EXPECTED
    assert "/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox" in module.EXPECTED


def test_local_openapi_valid_returns_routes_without_secrets(monkeypatch):
    class FakeReply:
        status=200
        def __enter__(self): return self
        def __exit__(self,*_): return None
        def read(self,n): return json.dumps({"paths":{p:{"get":{}} for p in module.EXPECTED}}).encode()
    def fake_urlopen(request,timeout):
        assert request.full_url=="http://127.0.0.1:8000/openapi.json"
        assert request.get_method()=="GET"
        assert timeout==3
        assert request.get_header("Authorization") is None
        return FakeReply()
    monkeypatch.setattr(module,"urlopen",fake_urlopen)
    status,paths=module.inspect_local_openapi()
    assert status=="OPENAPI_READY"
    assert paths==module.EXPECTED


def test_bad_openapi_never_causes_write_or_guess(monkeypatch):
    class FakeBad:
        status=200
        def __enter__(self): return self
        def __exit__(self,*_): return None
        def read(self,_):return b'{"no_paths": true}'
    monkeypatch.setattr(module,"urlopen",lambda *a,**k:FakeBad())
    status,paths=module.inspect_local_openapi()
    assert status=="INVALID_OPENAPI"
    assert paths==set()


def test_read_only_probe_has_no_other_network_or_db_capabilities():
    source=SCRIPT.read_text()
    assert 'http://127.0.0.1:8000/openapi.json' in source
    assert 'method="GET"' in source
    assert "import asyncpg" not in source
    assert "psycopg" not in source
    assert "subprocess" not in source
    assert "DATABASE_URL" not in source
    assert "Bearer" not in source
    assert "M39091_DATABASE_WRITES=NONE" in source
