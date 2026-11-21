"""M37381-M37400: localhost-only GET smoke with anonymous access denial."""
from dataclasses import replace
from pathlib import Path
import importlib.util
import json
from unittest.mock import patch
import pytest
from app.local_runtime_smoke_readonly import (
    HOST,PORT,PATHS,REQUESTS,MAX_BYTES,LocalSmokeBlocked,SmokeResult,
    local_get,check_local_smoke,format_smoke,
)
ROOT=Path(__file__).resolve().parents[2]

def good():
    return {
        "/api/health":(200,{"status":"ONLINE","app":"FR Finance","database_configured":True}),
        "/api/health/ready":(200,{"status":"READY_FOR_TEST_AUTH","scope":"LOCAL_HOMOLOGATION_ONLY"}),
        "/api/health/features/m19000":(200,{
            "workstream":"AI_STUDIO",
            "contract":"AI_STUDIO_M19000_LOCAL_IN_APP_NOTIFICATIONS_V1",
            "local_notification_flag_configured":True,
            "local_inbox_schema_verified":True,"local_in_app_ready":True,
            "external_email_active":False,"external_push_active":False,
            "external_whatsapp_active":False,"provider_events_authenticated":False,
            "real_payments_enabled":False,"bank_reconciled":False,
            "ledger_written":False,"financial_closing_authorized":False,
            "payout_authorized":False,"oci_staging_deployed":False,
        }),
        "/api/health/features":(200,{
            "product":"FR Finance","workstream":"AI_STUDIO",
            "real_payments_enabled":False,"bank_reconciled":False,
            "financial_closing_authorized":False,"master_tenant_ledger_allowed":False,
        }),
        "/api/v1/auth/status":(200,{
            "status":"TEST_MODE","configured":True,"provider":"POSTGRES_TEST",
            "requires_authentication":True,
        }),
        "/api/v1/auth/me":(401,{}),
        "/api/v1/notifications/capabilities":(401,{}),
        "/api/v1/notifications/readiness":(401,{}),
    }

def fake(rows):
    return lambda path:rows[path]

def test_baseline_local_contract_passes_without_writes():
    rows=good()
    assert set(rows)==PATHS
    r=check_local_smoke(fake(rows))
    assert r.validated_endpoints==8
    assert r.no_writes_performed
    assert r.anonymous_me_denied and r.anonymous_notifications_denied
    assert not r.payment_activation_authorized and not r.user_activation_authorized
    out="\n".join(format_smoke(r))
    assert "M37400_SMOKE=PASS" in out
    assert "M37400_REAL_LOGIN_FLOW=NOT_TESTED" in out
    assert "M37400_PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED" in out

@pytest.mark.parametrize("path",[
    "/api/health","/api/health/ready","/api/health/features/m19000",
    "/api/health/features","/api/v1/auth/status",
])
def test_required_endpoint_503_denied(path):
    rows=good();rows[path]=(503,{})
    with pytest.raises(LocalSmokeBlocked,match="REQUIRED_ENDPOINT_UNREADY"):
        check_local_smoke(fake(rows))

@pytest.mark.parametrize("path",[
    "/api/v1/auth/me","/api/v1/notifications/capabilities",
    "/api/v1/notifications/readiness",
])
@pytest.mark.parametrize("status",[200,302,500])
def test_anonymous_data_access_never_passes(path,status):
    rows=good();rows[path]=(status,{"private":"untrusted"})
    with pytest.raises(LocalSmokeBlocked,match="ANONYMOUS_ACCESS_NOT_DENIED"):
        check_local_smoke(fake(rows))

@pytest.mark.parametrize("field,value",[
    ("app","OtherApp"),("database_configured",False),("database_configured",1),
])
def test_wrong_backend_or_db_config_denied(field,value):
    rows=good();rows["/api/health"][1][field]=value
    with pytest.raises(LocalSmokeBlocked,match="WRONG_BACKEND"):
        check_local_smoke(fake(rows))

@pytest.mark.parametrize("key,value",[
    ("status","READY_FOR_PRODUCTION"),("scope","PRODUCTION"),
])
def test_prod_readiness_claim_denied(key,value):
    rows=good();rows["/api/health/ready"][1][key]=value
    with pytest.raises(LocalSmokeBlocked,match="DATABASE_NOT_READY"):
        check_local_smoke(fake(rows))

@pytest.mark.parametrize("field,value",[
    ("local_notification_flag_configured",False),
    ("local_inbox_schema_verified",False),
    ("local_in_app_ready",False),
    ("external_email_active",True),
    ("external_push_active",True),
    ("external_whatsapp_active",True),
    ("provider_events_authenticated",True),
    ("real_payments_enabled",True),
    ("bank_reconciled",True),
    ("ledger_written",True),
    ("financial_closing_authorized",True),
    ("payout_authorized",True),
    ("oci_staging_deployed",True),
])
def test_inbox_and_production_flags_fail_closed(field,value):
    rows=good();rows["/api/health/features/m19000"][1][field]=value
    with pytest.raises(LocalSmokeBlocked,match="INBOX_NOT_LOCAL_ONLY"):
        check_local_smoke(fake(rows))

@pytest.mark.parametrize("field",[
    "real_payments_enabled","bank_reconciled",
    "financial_closing_authorized","master_tenant_ledger_allowed",
])
def test_financial_feature_enabled_denied(field):
    rows=good();rows["/api/health/features"][1][field]=True
    with pytest.raises(LocalSmokeBlocked,match="FINANCIAL_GATES_UNSAFE"):
        check_local_smoke(fake(rows))

@pytest.mark.parametrize("field,value",[
    ("status","PRODUCTION_CONFIGURED_UNVERIFIED"),
    ("configured",False),("provider","PRODUCTION"),
    ("requires_authentication",False),
])
def test_auth_prod_or_unconfigured_denied(field,value):
    rows=good();rows["/api/v1/auth/status"][1][field]=value
    with pytest.raises(LocalSmokeBlocked,match="AUTH_NOT_SANDBOX"):
        check_local_smoke(fake(rows))

@pytest.mark.parametrize("payload",[
    (200,"NO_JSON"),("200",{}),(200,[]),(200,None),
])
def test_transport_schema_invalid_denied(payload):
    rows=good();rows["/api/health"]=payload
    with pytest.raises(LocalSmokeBlocked,match="RESPONSE_SCHEMA_INVALID"):
        check_local_smoke(fake(rows))

def test_remote_path_never_allowed():
    for path in ("http://evil.example/","https://localhost:8000/api/health",
                 "/api/v1/auth/login","/api/v1/notifications/self-test",
                 "//attacker.example/api/health", "/api/health?token=abc"):
        with pytest.raises(LocalSmokeBlocked,match="PATH_DENIED"):
            local_get(path)

def test_unknown_exception_cannot_leak_credentials():
    def bad(path):raise RuntimeError("PASSWORD=PRIVATE")
    with pytest.raises(LocalSmokeBlocked,match="REQUEST_FAILED") as exc:
        check_local_smoke(bad)
    assert "PASSWORD" not in str(exc.value)

def test_report_flags_cannot_be_turned_on():
    r=check_local_smoke(fake(good()))
    for patch in ({"payment_activation_authorized":True},
                  {"user_activation_authorized":True},
                  {"production_deployment_authorized":True},
                  {"no_writes_performed":False}):
        with pytest.raises(LocalSmokeBlocked,match="REPORT_INVALID"):
            format_smoke(replace(r,**patch))

def test_local_host_and_get_only():
    code=(ROOT/"backend/app/local_runtime_smoke_readonly.py").read_text()
    script=(ROOT/"backend/scripts/aistudio_local_runtime_smoke_readonly.py").read_text()
    assert HOST=="127.0.0.1" and PORT==8000 and MAX_BYTES==8192
    assert 'connection.request(' in code and '"GET",path' in code
    for banned in ('"POST",','"PUT",','"DELETE",',"getpass.getpass",
                   "psycopg.connect(","asyncpg.connect(","DATABASE_URL",
                   "terraform apply","requests.post("):
        assert banned not in code+script

def test_script_pass_and_output_do_not_include_http_data(capsys,monkeypatch):
    path=ROOT/"backend/scripts/aistudio_local_runtime_smoke_readonly.py"
    spec=importlib.util.spec_from_file_location("m37400_smoke",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod,"local_get",fake(good()))
    assert mod.main()==0
    out=capsys.readouterr().out
    assert "M37400_SMOKE=PASS" in out
    assert "FRCAIXINHA_AI_STUDIO_MOBILE" not in out
    assert "127.0.0.1:8000" not in out
