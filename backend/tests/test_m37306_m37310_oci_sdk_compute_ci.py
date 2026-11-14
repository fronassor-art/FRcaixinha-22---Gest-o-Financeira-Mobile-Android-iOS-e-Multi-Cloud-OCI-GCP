"""M37306-M37310: OCI Compute SDK typed read-only source, CI mocked."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import importlib.util
import json
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
TEN="ocid1.tenancy.oc1.."+"a"*20
COMP="ocid1.compartment.oc1.."+"b"*20
VM1="ocid1.instance.oc1.sa-saopaulo-1."+"c"*20
VM2="ocid1.instance.oc1.sa-saopaulo-1."+"d"*20


def load_cli():
    path=ROOT/"backend/scripts/aistudio_oci_live_inventory_readonly.py"
    spec=importlib.util.spec_from_file_location("m37306_sdk_cli",path)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def install_oci(monkeypatch, *, pages=(), config_region="sa-saopaulo-1", error=None):
    instances=[]
    calls=[]
    class NoRetry:
        pass
    class Compute:
        def __init__(self,config,**kwargs):
            assert config["region"]=="sa-saopaulo-1"
            assert kwargs["timeout"]==(5,30)
            assert isinstance(kwargs["retry_strategy"],NoRetry)
        def list_instances(self,comp,**kwargs):
            calls.append((comp,kwargs))
            if error is not None:
                raise RuntimeError("secret DO_NOT_ECHO")
            assert comp in (TEN,COMP)
            assert kwargs["limit"]==100
            assert isinstance(kwargs["retry_strategy"],NoRetry)
            i=len(calls)-1
            if i>=len(pages):
                raise RuntimeError("unexpected pagination")
            return pages[i]
    def from_file(*,file_location,profile_name):
        calls.append(("config",file_location,profile_name)) if False else None
        return {"region":config_region,"tenancy":TEN}
    sdk=SimpleNamespace(
        config=SimpleNamespace(from_file=from_file),
        core=SimpleNamespace(ComputeClient=Compute),
        retry=SimpleNamespace(NoneRetryStrategy=NoRetry),
    )
    monkeypatch.setitem(sys.modules,"oci",sdk)
    return calls


def response(status=200,data=(),next_page=None):
    return SimpleNamespace(status=status,data=list(data) if data is not None else None,
                           next_page=next_page)


def vm(iid,state):
    return SimpleNamespace(id=iid,lifecycle_state=state)


def test_empty_success_is_verified_http_200_list(monkeypatch):
    m=load_cli()
    calls=install_oci(monkeypatch,pages=(response(),))
    result=m._run(("compute","instance","list","--compartment-id",TEN,"--all"))
    assert result=={"data":[]}
    assert len(calls)==1


def test_sdk_return_running_and_provisioning_without_secrets(monkeypatch):
    m=load_cli()
    calls=install_oci(monkeypatch,pages=(response(data=(
        vm(VM1,"RUNNING"),vm(VM2,"PROVISIONING")
    )),))
    result=m._run(("compute","instance","list","--compartment-id",COMP,"--all"))
    assert result=={"data":[
        {"id":VM1,"lifecycle-state":"RUNNING"},
        {"id":VM2,"lifecycle-state":"PROVISIONING"},
    ]}
    assert len(calls)==1


def test_sdk_pagination_preserves_complete_list(monkeypatch):
    m=load_cli()
    calls=install_oci(monkeypatch,pages=(
        response(data=(),next_page="OPAQUE-PAGE-1"),
        response(data=(vm(VM1,"RUNNING"),),next_page="OPAQUE-PAGE-2"),
        response(data=(vm(VM2,"STOPPED"),)),
    ))
    result=m._sdk_compute_list(("compute","instance","list",
                                "--compartment-id",TEN,"--all"))
    assert len(result["data"])==2
    assert len(calls)==3
    assert calls[0][1].get("page") is None
    assert calls[1][1]["page"]=="OPAQUE-PAGE-1"
    assert calls[2][1]["page"]=="OPAQUE-PAGE-2"


@pytest.mark.parametrize("bad",[
    response(status=403),
    response(status=204),
    response(status=True),
    response(data=None),
    response(data=tuple(range(101))),
    response(data=(SimpleNamespace(id=VM1,lifecycle_state=None),)),
    response(data=(SimpleNamespace(id=None,lifecycle_state="RUNNING"),)),
])
def test_sdk_does_not_turn_errors_or_malformed_data_into_absence(monkeypatch,bad):
    m=load_cli()
    install_oci(monkeypatch,pages=(bad,))
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_COMPUTE_SDK_RESPONSE_INVALID"):
        m._sdk_compute_list(("compute","instance","list",
                             "--compartment-id",TEN,"--all"))


@pytest.mark.parametrize("bad",["",True,42,"x"*2049])
def test_invalid_page_token_denied(monkeypatch,bad):
    m=load_cli()
    install_oci(monkeypatch,pages=(response(next_page=bad),))
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_COMPUTE_PAGINATION_INVALID"):
        m._sdk_compute_list(("compute","instance","list",
                             "--compartment-id",COMP,"--all"))


def test_repeated_page_token_denied(monkeypatch):
    m=load_cli()
    install_oci(monkeypatch,pages=(response(next_page="REPEAT"),
                                  response(next_page="REPEAT")))
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_COMPUTE_PAGINATION_INVALID"):
        m._sdk_compute_list(("compute","instance","list","--compartment-id",TEN,"--all"))


@pytest.mark.parametrize("bad",[
    ("compute","instance","list","--compartment-id",TEN,"--limit","1"),
    ("compute","instance","launch","--compartment-id",TEN,"--all"),
    ("compute","instance","list","--compartment-id",TEN,"--all","--debug"),
    ("compute","instance","list","--compartment-id","ROOT","--all"),
])
def test_sdk_command_must_be_exactly_read_only(monkeypatch,bad):
    m=load_cli()
    install_oci(monkeypatch,pages=(response(),))
    with pytest.raises(m.OCIInventoryBlocked):
        m._sdk_compute_list(bad)


def test_sdk_region_mismatch_denied_before_api_call(monkeypatch):
    m=load_cli()
    calls=install_oci(monkeypatch,pages=(response(),),
                      config_region="us-ashburn-1")
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_TENANCY_OR_REGION_DENIED"):
        m._sdk_compute_list(("compute","instance","list",
                             "--compartment-id",TEN,"--all"))
    assert calls==[]


def test_sdk_remote_exception_is_redacted(monkeypatch):
    m=load_cli()
    install_oci(monkeypatch,pages=(response(),),error=True)
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_COMPUTE_SDK_READ_FAILED") as ex:
        m._sdk_compute_list(("compute","instance","list",
                             "--compartment-id",TEN,"--all"))
    assert "DO_NOT_ECHO" not in str(ex.value)


def test_sdk_client_source_is_not_cli_empty_stdout():
    s=(ROOT/"backend/scripts/aistudio_oci_live_inventory_readonly.py").read_text()
    assert "def _sdk_compute_list" in s
    assert "response.status!=200" in s
    assert "type(response.data) is not list" in s
    assert 'if command[:3]==("compute","instance","list"):' in s
    assert "OCI_COMPUTE_SOURCE=SDK_HTTP_200_TYPED_LIST" in s
    for forbidden in ("launch_instance(","terminate_instance(","update_instance(",
                      "create_vcn(","terraform apply","return {\"data\":[]}"+"  # assume"):
        assert forbidden not in s
