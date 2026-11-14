"""M37420 — negative local authentication GET probes, no DB or user records."""
from dataclasses import replace
from pathlib import Path
import importlib.util
import pytest

from app.local_session_boundary_readonly import (
    HOST,PORT,MAX_BODY,MODES,CONTROL_PATHS,PROTECTED_PATHS,ALLOWED,
    SYNTHETIC_UNRECOGNIZED_TOKEN,SessionBoundaryBlocked,local_request,
    assess_session_boundaries,format_session_boundary,
)
ROOT=Path(__file__).resolve().parents[2]


def prepared():
    a = {
        "/api/health":(200,{
            "app":"FR Finance","status":"ONLINE","database_configured":True,
        }),
        "/api/health/ready":(200,{
            "status":"READY_FOR_TEST_AUTH","scope":"LOCAL_HOMOLOGATION_ONLY",
        }),
        "/api/v1/auth/status":(200,{
            "status":"TEST_MODE","configured":True,
            "provider":"POSTGRES_TEST","requires_authentication":True,
        }),
    }
    for mode in MODES:
        for path in PROTECTED_PATHS:
            a[(path,mode)] = (401,{})
    return a


def fake(values):
    def request(path,mode):
        if mode=="CONTROL":
            return values[path]
        return values[(path,mode)]
    return request


def test_synthetic_negative_session_boundaries_pass():
    r=assess_session_boundaries(fake(prepared()))
    assert r.controls==3
    assert r.protected_routes==6
    assert r.negative_checks==12
    assert not r.real_login_tested
    assert not r.synthetic_account_created
    assert not r.sql_writes_requested
    assert not r.real_users_authorized
    assert not r.real_pix_authorized
    output="\n".join(format_session_boundary(r))
    for marker in ("M37420_STATUS=READ_ONLY_PASS",
                   "M37420_INVALID_BEARER=DENIED",
                   "M37420_ROLE_HEADER_SPOOF=DENIED",
                   "M37420_REAL_LOGIN_FLOW=NOT_TESTED",
                   "M37420_PIX_REAL=OFF"):
        assert marker in output
    for secret in ("Bearer ","password","token_hash","0.0.0.0","00000000-0000-4000"):
        assert secret not in output


@pytest.mark.parametrize("path",CONTROL_PATHS)
@pytest.mark.parametrize("status",[401,403,503,302])
def test_control_endpoint_not_200_blocks(path,status):
    a=prepared();a[path]=(status,{})
    with pytest.raises(SessionBoundaryBlocked,match="CONTROL_NOT_READY"):
        assess_session_boundaries(fake(a))


@pytest.mark.parametrize("path,mode",[
    (path,mode) for mode in MODES for path in PROTECTED_PATHS
])
@pytest.mark.parametrize("status",[200,201,302,403,500,503])
def test_any_non_401_for_negative_auth_is_fail_closed(path,mode,status):
    a=prepared();a[(path,mode)]=(status,{})
    with pytest.raises(SessionBoundaryBlocked,match="UNAUTHORIZED_ACCESS_NOT_DENIED"):
        assess_session_boundaries(fake(a))


@pytest.mark.parametrize("field,value",[
    ("app","OtherApp"),("database_configured",False),
    ("database_configured",1),("status","UNKNOWN"),
])
def test_backend_identity_denied(field,value):
    a=prepared();a["/api/health"][1][field]=value
    with pytest.raises(SessionBoundaryBlocked,match="WRONG_LOCAL_BACKEND"):
        assess_session_boundaries(fake(a))


@pytest.mark.parametrize("key,value",[
    ("status","READY_FOR_PRODUCTION"),("scope","PRODUCTION"),
])
def test_production_pretence_denied(key,value):
    a=prepared();a["/api/health/ready"][1][key]=value
    with pytest.raises(SessionBoundaryBlocked,match="LOCAL_DB_AUTH_NOT_READY"):
        assess_session_boundaries(fake(a))


@pytest.mark.parametrize("key,value",[
    ("status","PRODUCTION_CONFIGURED_UNVERIFIED"),
    ("configured",False),("provider","POSTGRES_PROD"),
    ("requires_authentication",False),
])
def test_auth_not_test_mode_denied(key,value):
    a=prepared();a["/api/v1/auth/status"][1][key]=value
    with pytest.raises(SessionBoundaryBlocked,match="NOT_SANDBOX_AUTH"):
        assess_session_boundaries(fake(a))


@pytest.mark.parametrize("payload",[
    (401,{"private":"accidental_user_info"}),
    ("401",{}),(401,[]),(401,None),
])
def test_protected_payload_exposure_or_wrong_schema_denied(payload):
    a=prepared();a[(PROTECTED_PATHS[0],MODES[0])]=payload
    with pytest.raises(SessionBoundaryBlocked,match="UNAUTHORIZED_ACCESS_NOT_DENIED"):
        assess_session_boundaries(fake(a))


def test_url_and_mode_whitelist():
    assert HOST=="127.0.0.1" and PORT==8000 and MAX_BODY==4096
    assert set(CONTROL_PATHS+PROTECTED_PATHS)==ALLOWED
    assert len(SYNTHETIC_UNRECOGNIZED_TOKEN)>40
    for invalid in ("https://example.com", "http://127.0.0.1:8000/api/v1/auth/me",
                    "//example.com/api/health","/api/v1/auth/login",
                    "/api/v1/notifications/self-test","/api/v1/auth/me?token=unsafe"):
        with pytest.raises(SessionBoundaryBlocked,match="PATH_DENIED"):
            local_request(invalid,"CONTROL")
    for wrong in (
        (PROTECTED_PATHS[0],"CONTROL"),
        (CONTROL_PATHS[0],"INVALID_BEARER"),
        (CONTROL_PATHS[0],"UNSAFE"),
    ):
        with pytest.raises(SessionBoundaryBlocked,match="METHOD_SCOPE_DENIED"):
            local_request(*wrong)


def test_credentials_exception_redacted():
    def leak(path,mode):
        raise RuntimeError("dsn=postgres://password@localhost")
    with pytest.raises(SessionBoundaryBlocked,match="CONTROL_READ_FAILED") as exc:
        assess_session_boundaries(leak)
    assert "password" not in str(exc.value)


def test_untruthful_report_rejected():
    r=assess_session_boundaries(fake(prepared()))
    for patch in ({"real_login_tested":True},{"synthetic_account_created":True},
                  {"sql_writes_requested":True},{"production_deployment_authorized":True},
                  {"real_pix_authorized":True},{"real_users_authorized":True},
                  {"negative_checks":11},{"controls_verified":False}):
        with pytest.raises(SessionBoundaryBlocked,match="REPORT_INVALID"):
            format_session_boundary(replace(r,**patch))


def test_only_read_get_and_no_external_request_or_persistent_io():
    source=(ROOT/"backend/app/local_session_boundary_readonly.py").read_text()
    script=(ROOT/"backend/scripts/aistudio_local_session_boundary_readonly.py").read_text()
    assert 'conn.request("GET", path, headers=headers)' in source
    for denied in ("psycopg.connect(","asyncpg.connect(","requests.post(",
                   'conn.request("POST"', 'conn.request("PUT"',
                   'conn.request("DELETE"', "getpass.getpass",
                   "os.environ[","terraform apply","https://api.mercadopago",
                   "open(", "INSERT INTO public."):
        assert denied not in source+script


def test_script_output_no_auth_token(capsys,monkeypatch):
    path=ROOT/"backend/scripts/aistudio_local_session_boundary_readonly.py"
    spec=importlib.util.spec_from_file_location("m37420_script",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod,"local_request",fake(prepared()))
    assert mod.main()==0
    out=capsys.readouterr().out
    assert SYNTHETIC_UNRECOGNIZED_TOKEN not in out
    assert "M37420_STATUS=READ_ONLY_PASS" in out
