"""M39501: no false green when FastAPI or expected GET routes are absent."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/frfinance_m39091_api_route_probe_readonly.py"
spec=importlib.util.spec_from_file_location("m39501_probe",SCRIPT)
assert spec and spec.loader
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize("http_state,route_set,health,success,expected",[
 ("LOOPBACK_NOT_REACHABLE",set(),"NO_HEALTH",False,"BACKEND_NOT_REACHABLE"),
 ("OPENAPI_HTTP_404",set(),"NO_HEALTH",False,"INCONCLUSIVE_DO_NOT_CHANGE_DB"),
 ("INVALID_OPENAPI",set(),"NO_HEALTH",False,"INCONCLUSIVE_DO_NOT_CHANGE_DB"),
 ("OPENAPI_READY",set(),"NO_HEALTH",False,"STALE_OR_DIFFERENT_APP"),
 ("OPENAPI_READY",probe.EXPECTED-{
    "/api/v1/tenants/{tenant_id}/special-credit/capabilities"
 },"NO_HEALTH",False,"STALE_OR_DIFFERENT_APP"),
 ("OPENAPI_READY",probe.EXPECTED,"HEALTH_DIFFERENT_APP_OR_VERSION",
  False,"APP_IDENTITY_UNVERIFIED"),
 ("OPENAPI_READY",probe.EXPECTED,"FR_FINANCE_API_CONFIRMED",
  True,"ROUTES_PRESENT"),
])
def test_main_status_fail_closed(monkeypatch,capsys,http_state,route_set,
                                 health,success,expected):
    monkeypatch.setattr(probe,"source_route_presence",lambda:True)
    monkeypatch.setattr(probe,"inspect_local_openapi",
                        lambda:(http_state,route_set))
    monkeypatch.setattr(probe,"inspect_local_health",lambda:health)
    code=probe.main()
    out=capsys.readouterr().out
    assert code==(0 if success else 2)
    assert "M39091_SERVER_ROUTE_STATE="+expected in out
    assert "M39091_STATUS="+(
        "PASS_READ_ONLY" if success else "BLOCKED_READ_ONLY") in out
    assert "M39091_DATABASE_WRITES=NONE" in out
    assert "M39091_MIGRATIONS=NONE" in out


def test_api_health_identity_anonymous_read_only(monkeypatch):
    class Reply:
        status=200
        def __enter__(self):return self
        def __exit__(self,*_):return None
        def read(self,n):
            assert n==4097
            return json.dumps({"app":"FR Finance","status":"ONLINE"}).encode()
    def safe_get(request,timeout):
        assert timeout==3
        assert request.full_url=="http://127.0.0.1:8000/api/health"
        assert request.get_method()=="GET"
        assert request.get_header("Authorization") is None
        return Reply()
    monkeypatch.setattr(probe,"urlopen",safe_get)
    assert probe.inspect_local_health()=="FR_FINANCE_API_CONFIRMED"


@pytest.mark.parametrize("response",[
 {"app":"FR Caixinha 2.2","status":"ONLINE"},
 {"app":"FR Finance","status":"STOPPED"},
 {},
 ["FR Finance","ONLINE"],
])
def test_rejects_misidentified_health(monkeypatch,response):
    class Reply:
        status=200
        def __enter__(self):return self
        def __exit__(self,*_):return None
        def read(self,n):return json.dumps(response).encode()
    monkeypatch.setattr(probe,"urlopen",lambda *args,**kwargs:Reply())
    assert probe.inspect_local_health()=="HEALTH_DIFFERENT_APP_OR_VERSION"


def test_openapi_routes_must_be_get_not_just_same_path(monkeypatch):
    class Reply:
        status=200
        def __enter__(self):return self
        def __exit__(self,*_):return None
        def read(self,n):
            paths={p:{"get":{}} for p in probe.EXPECTED}
            paths["/api/v1/master/exclusive-cashbox"]={"post":{}}
            return json.dumps({"paths":paths}).encode()
    monkeypatch.setattr(probe,"urlopen",lambda *args,**kwargs:Reply())
    status,methods=probe.inspect_local_openapi()
    assert status=="OPENAPI_READY"
    assert "/api/v1/master/exclusive-cashbox" not in methods
    assert len(methods)==len(probe.EXPECTED)-1


def test_probe_reads_only_two_hardcoded_loopback_paths():
    source=SCRIPT.read_text()
    assert 'http://127.0.0.1:8000/api/health' in source
    assert 'http://127.0.0.1:8000/openapi.json' in source
    assert "M39091_STATUS=" in source
    assert "return 0 if verified else 2" in source
    assert 'method="GET"' in source
    assert "getpass" not in source
    assert "psycopg" not in source
    assert "subprocess" not in source
