"""M37311: OCI Vault list uses typed SDK with strict pagination, CI mocked."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
COMP="ocid1.compartment.oc1.."+"f"*20
COMMAND=("kms","management","vault","list","--compartment-id",COMP,"--all")


def load():
    spec=importlib.util.spec_from_file_location(
        "frfinance_m37311",ROOT/"backend/scripts/aistudio_oci_live_inventory_readonly.py")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def mock_sdk(monkeypatch,pages,*,region="sa-saopaulo-1",crash=False):
    calls=[]
    class NoneRetryStrategy: pass
    class VaultClient:
        def __init__(self,cfg,**kwargs):
            assert cfg["region"]=="sa-saopaulo-1"
            assert kwargs["timeout"]==(5,30)
            assert isinstance(kwargs["retry_strategy"],NoneRetryStrategy)
        def list_vaults(self,compartment,**kwargs):
            assert compartment==COMP
            assert kwargs["limit"]==100
            assert isinstance(kwargs["retry_strategy"],NoneRetryStrategy)
            if crash:
                raise RuntimeError("private provider details")
            idx=len(calls)
            calls.append(kwargs)
            return pages[idx]
    def from_file(**kwargs):
        assert kwargs["profile_name"]=="DEFAULT"
        return {"region":region}
    sdk=SimpleNamespace(
        config=SimpleNamespace(from_file=from_file),
        key_management=SimpleNamespace(KmsVaultClient=VaultClient),
        retry=SimpleNamespace(NoneRetryStrategy=NoneRetryStrategy),
    )
    monkeypatch.setitem(sys.modules,"oci",sdk)
    return calls


def response(*,status=200,items=(),next_page=None):
    return SimpleNamespace(status=status,data=list(items) if items is not None else None,
                           next_page=next_page)


def test_empty_vault_response_must_be_http_200(monkeypatch):
    m=load()
    calls=mock_sdk(monkeypatch,(response(),))
    assert m._run(COMMAND)=={"data":[]}
    assert len(calls)==1


def test_active_vault_is_only_lifecycle_state(monkeypatch):
    m=load()
    mock_sdk(monkeypatch,(response(items=(
        SimpleNamespace(lifecycle_state="ACTIVE",id="SENSITIVE_UNPRINTED"),
        SimpleNamespace(lifecycle_state="CREATING",id="PRIVATE_UNPRINTED"),
    )),))
    result=m._sdk_vault_list(COMMAND)
    assert result=={"data":[{"lifecycle-state":"ACTIVE"},
                             {"lifecycle-state":"CREATING"}]}
    assert "SENSITIVE" not in str(result)


def test_two_pages_with_initial_empty_page(monkeypatch):
    m=load()
    calls=mock_sdk(monkeypatch,(
        response(next_page="NEXT-1"),
        response(items=(SimpleNamespace(lifecycle_state="ACTIVE"),)),
    ))
    result=m._sdk_vault_list(COMMAND)
    assert len(result["data"])==1
    assert calls[1]["page"]=="NEXT-1"


@pytest.mark.parametrize("bad",[
    response(status=404),
    response(status=500),
    response(status=True),
    response(items=None),
    response(items=tuple(range(101))),
    response(items=(SimpleNamespace(lifecycle_state=None),)),
])
def test_bad_http_or_data_not_falsely_empty(monkeypatch,bad):
    m=load()
    mock_sdk(monkeypatch,(bad,))
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_VAULT_SDK_RESPONSE_INVALID"):
        m._sdk_vault_list(COMMAND)


@pytest.mark.parametrize("bad",[True,"",100,"x"*2049])
def test_invalid_pagination_denied(monkeypatch,bad):
    m=load()
    mock_sdk(monkeypatch,(response(next_page=bad),))
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_VAULT_PAGINATION_INVALID"):
        m._sdk_vault_list(COMMAND)


def test_duplicate_page_denied(monkeypatch):
    m=load()
    mock_sdk(monkeypatch,(response(next_page="R"),response(next_page="R")))
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_VAULT_PAGINATION_INVALID"):
        m._sdk_vault_list(COMMAND)


def test_sdk_error_redacts_private_service_message(monkeypatch):
    m=load()
    mock_sdk(monkeypatch,(response(),),crash=True)
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_VAULT_SDK_READ_FAILED") as exc:
        m._sdk_vault_list(COMMAND)
    assert "private provider" not in str(exc.value)


def test_wrong_region_denied_before_vault_call(monkeypatch):
    m=load()
    calls=mock_sdk(monkeypatch,(response(),),region="us-phoenix-1")
    with pytest.raises(m.OCIInventoryBlocked,match="OCI_TENANCY_OR_REGION_DENIED"):
        m._sdk_vault_list(COMMAND)
    assert calls==[]


@pytest.mark.parametrize("bad",[
    ("kms","management","vault","create","--compartment-id",COMP,"--all"),
    ("kms","management","vault","list","--compartment-id",COMP,"--limit","1"),
    ("kms","management","vault","list","--compartment-id","other","--all"),
    ("kms","management","vault","list","--compartment-id",COMP),
])
def test_only_exact_vault_read_call_allowed(monkeypatch,bad):
    m=load()
    mock_sdk(monkeypatch,(response(),))
    with pytest.raises(m.OCIInventoryBlocked):
        m._sdk_vault_list(bad)


def test_no_financial_or_vault_write_operations():
    s=(ROOT/"backend/scripts/aistudio_oci_live_inventory_readonly.py").read_text()
    assert 'oci.key_management.KmsVaultClient' in s
    assert "client.list_vaults(" in s
    assert "OCI_VAULT_SOURCE=SDK_HTTP_200_TYPED_LIST" in s
    for forbidden in ("client.create_vault(","client.delete_vault(",
                      "client.schedule_vault_deletion(","client.update_vault(",
                      "client.create_key(","client.create_secret(","client.launch_instance("):
        assert forbidden not in s
