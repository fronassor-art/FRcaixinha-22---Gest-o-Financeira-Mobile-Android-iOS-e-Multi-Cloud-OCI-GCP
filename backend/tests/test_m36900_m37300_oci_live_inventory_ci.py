"""M36900-M37300: actual OCI CLI read-only audit, mocked API in CI."""
from __future__ import annotations
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.oci_staging_live_inventory import (
    TARGET_REGION,OCIInventoryBlocked,inspect_live_oci_inventory,
)

ROOT=Path(__file__).resolve().parents[2]
TEN="ocid1.tenancy.oc1.."+"a"*20
COMP="ocid1.compartment.oc1.."+"b"*20
VCN="ocid1.vcn.oc1.sa-saopaulo-1."+"c"*20
VM="ocid1.instance.oc1.sa-saopaulo-1."+"d"*20

def inputs(*,machines=(),rootmachines=(),vaults=(),vcn=True,subnet=True,comp=True,region=True):
    """Each command is an OCI CLI read-only list; no real network in CI."""
    calls=[]
    data={
        ("iam","region-subscription","list"): [
            {"region-name":TARGET_REGION,"is-home-region":True,"status":"READY"}
        ] if region else [],
        ("iam","compartment","list"): [
            {"id":COMP,"display-name":"fr-finance-staging","lifecycle-state":"ACTIVE"}
        ] if comp else [],
        ("network","vcn","list"): [
            {"id":VCN,"display-name":"FR Finance","lifecycle-state":"AVAILABLE"}
        ] if vcn else [],
        ("network","subnet","list"): [
            {"id":"ocid1.subnet.oc1.sa-saopaulo-1."+"e"*20,
             "display-name":"FR Finance","lifecycle-state":"AVAILABLE","vcn-id":VCN}
        ] if subnet else [],
        ("compute","instance","list"):list(machines),
        ("kms","management","vault","list"):list(vaults),
    }
    def run(command):
        calls.append(command)
        assert command[-1]=="--all"
        assert all(danger not in command for danger in (
            "create","launch","update","delete","stop","start","terminate","apply"))
        if command[:3]==("iam","region-subscription","list"):
            assert command==("iam","region-subscription","list","--all")
        elif command[:3]==("iam","compartment","list"):
            assert command==("iam","compartment","list","--compartment-id",TEN,"--all")
        elif command[:3]==("network","vcn","list"):
            assert command==("network","vcn","list","--compartment-id",TEN,"--all")
        elif command[:3]==("network","subnet","list"):
            assert command==("network","subnet","list","--compartment-id",TEN,
                             "--vcn-id",VCN,"--all")
        elif command[:3]==("compute","instance","list"):
            assert command in (("compute","instance","list","--compartment-id",TEN,"--all"),
                               ("compute","instance","list","--compartment-id",COMP,"--all"))
        else:
            assert command==("kms","management","vault","list","--compartment-id",COMP,"--all")
        if command[:3]==("compute","instance","list"):
            return {"data":list(rootmachines if command[-2]==TEN else machines)}
        return {"data":data[command[:4] if command[0]=="kms" else command[:3]]}
    return run,calls,data

def check(**kwargs):
    run,calls,_=inputs(**kwargs)
    return inspect_live_oci_inventory(tenancy_id=TEN,region=TARGET_REGION,query=run),calls

def test_live_root_network_and_staging_compartment_but_no_machine():
    r,calls=check()
    assert len(calls)==7
    assert r.home_region_observed and r.staging_compartment=="ACTIVE"
    assert r.root_vcn=="AVAILABLE" and r.root_subnet=="AVAILABLE"
    assert r.root_instances_running==0
    assert r.staging_instances_running==0
    assert r.staging_vaults_active==0
    assert r.observations_from_live_api is True
    for key in ("deployment_authorized","api_public_https_verified",
        "database_tls_rls_verified","backups_restored_verified",
        "paid_upgrade_authorized","real_users_authorized","real_pix_authorized"):
        assert getattr(r,key) is False

def test_running_vm_is_observed_but_never_authorizes_deployment():
    r,_=check(machines=(
        {"id":VM,"lifecycle-state":"RUNNING","shape":"VM.Standard.A1.Flex"},
        {"id":"ocid1.instance.oc1.sa-saopaulo-1."+"f"*20,
         "lifecycle-state":"PROVISIONING"},
    ),vaults=({"lifecycle-state":"ACTIVE","id":"ocid1.vault.oc1..abcd1234"},))
    assert r.staging_instances_running==1 and r.staging_instances_provisioning==1
    assert r.staging_vm_present is True and r.staging_vaults_active==1
    assert not r.deployment_authorized and not r.api_public_https_verified

@pytest.mark.parametrize("kwargs,expected",[
    ({"vcn":False},"MISSING"),
    ({"subnet":False},"MISSING"),
])
def test_missing_network_reports_absence_not_success(kwargs,expected):
    result,_=check(**kwargs)
    assert expected in (result.root_vcn,result.root_subnet)
    assert result.deployment_authorized is False

def test_root_running_instance_is_reported_separately():
    r,calls=check(rootmachines=({"id":VM,"lifecycle-state":"RUNNING"},))
    assert r.root_instances_running==1
    assert r.staging_instances_running==0
    assert not r.staging_vm_present
    assert not r.deployment_authorized
    assert len(calls)==7

def test_missing_compartment_fails_closed():
    with pytest.raises(OCIInventoryBlocked,match="OCI_STAGING_COMPARTMENT_NOT_FOUND"):
        check(comp=False)

def test_missing_home_region_fails_closed():
    with pytest.raises(OCIInventoryBlocked,match="OCI_HOME_REGION_NOT_VERIFIED"):
        check(region=False)

@pytest.mark.parametrize("tenant,region",[
    ("not-ocid",TARGET_REGION),
    (TEN,"us-ashburn-1"),
    (TEN,True),
    ("ocid1.tenancy.oc1..short",TARGET_REGION),
])
def test_wrong_account_or_region_rejected_before_query(tenant,region):
    run,calls,_=inputs()
    with pytest.raises(OCIInventoryBlocked,match="OCI_TENANCY_OR_REGION_DENIED"):
        inspect_live_oci_inventory(tenancy_id=tenant,region=region,query=run)
    assert calls==[]

@pytest.mark.parametrize("kind",["compartment","vcn","subnet"])
def test_duplicate_named_resource_denied(kind):
    run,calls,data=inputs()
    if kind=="compartment":
        data[("iam","compartment","list")]*=2
    elif kind=="vcn":
        data[("network","vcn","list")]*=2
    else:
        data[("network","subnet","list")]*=2
    with pytest.raises(OCIInventoryBlocked,match="OCI_AMBIGUOUS_RESOURCE"):
        inspect_live_oci_inventory(tenancy_id=TEN,region=TARGET_REGION,query=run)

def test_bad_vm_ocid_is_denied():
    with pytest.raises(OCIInventoryBlocked,match="OCI_RESPONSE_SCHEMA_DENIED"):
        check(machines=({"id":"invalid","lifecycle-state":"RUNNING"},))

@pytest.mark.parametrize("response",[
    None,[],{},{"data":{}},{"data":[None]},{"data":[],"secret":"do-not-print"}
])
def test_invalid_api_envelope_fail_closed(response):
    def fetch(_):
        return response
    with pytest.raises(OCIInventoryBlocked,match="OCI_RESPONSE_SCHEMA_DENIED"):
        inspect_live_oci_inventory(tenancy_id=TEN,region=TARGET_REGION,query=fetch)

def test_raw_provider_errors_never_echo_secrets():
    def fail(_):
        raise RuntimeError("api secret=TOPSECRET23")
    with pytest.raises(OCIInventoryBlocked,match="OCI_REMOTE_READ_FAILED") as exc:
        inspect_live_oci_inventory(tenancy_id=TEN,region=TARGET_REGION,query=fail)
    assert "TOPSECRET23" not in str(exc.value)

def _cli_module():
    file=ROOT/"backend/scripts/aistudio_oci_live_inventory_readonly.py"
    spec=importlib.util.spec_from_file_location("oci_m37300_cli",file)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_cli_redacts_ocids_and_denies_cloud_actions(monkeypatch,capsys):
    m=_cli_module()
    run,calls,_=inputs()
    monkeypatch.setattr(m,"read_cli_identity",lambda:(TEN,TARGET_REGION))
    monkeypatch.setattr(m,"_run",run)
    assert m.main()==0
    stdout=capsys.readouterr().out
    assert "OCI_M37300_LIVE_INVENTORY=READ_ONLY_PASS" in stdout
    assert "OCI_STAGING_VM_RUNNING=0" in stdout
    assert "OCI_DEPLOYMENT_AUTHORIZED=NO" in stdout
    assert "PIX_REAL=OFF" in stdout
    assert all(s not in stdout for s in (TEN,COMP,VCN,VM))
    assert len(calls)==7

def test_cli_config_not_present_fails_with_safe_reason(monkeypatch,capsys):
    m=_cli_module()
    monkeypatch.setenv("OCI_CLI_CONFIG_FILE","/tmp/nonexistent-m37300-oci-config")
    assert m.main()==2
    stdout=capsys.readouterr().out
    assert "OCI_M37300_LIVE_INVENTORY=BLOCKED" in stdout
    assert "OCI_RESOURCE_CREATED=NO" in stdout
    assert "OCI_PRODUCTION_AUTHORIZATION=NOT_GRANTED" in stdout

def test_cli_json_rejects_duplicate_fields_and_nonfinite():
    m=_cli_module()
    with pytest.raises(OCIInventoryBlocked,match="OCI_AMBIGUOUS_JSON"):
        json.loads('{"data":[],"data":[]}',object_pairs_hook=m._unique)
    with pytest.raises(OCIInventoryBlocked,match="OCI_INVALID_JSON"):
        json.loads('{"data":NaN}',parse_constant=m._no_nonfinite)

def test_cli_config_parses_existing_profile_without_output(monkeypatch,tmp_path):
    m=_cli_module()
    p=tmp_path/"config"
    p.write_text("[DEFAULT]\nuser=ocid1.user.oc1..aaaaaaaa\n"
                 f"tenancy={TEN}\nregion={TARGET_REGION}\n"
                 "fingerprint=aa:bb:cc\nkey_file=/root/secrets/private.pem\n")
    monkeypatch.setenv("OCI_CLI_CONFIG_FILE",str(p))
    assert m.read_cli_identity()==(TEN,TARGET_REGION)

def test_cli_forwards_selected_oci_profile_without_exposing_config(monkeypatch):
    m=_cli_module()
    calls=[]
    monkeypatch.setenv("OCI_CLI_PROFILE","FR_FINANCE_OCI")
    monkeypatch.setenv("OCI_CLI_CONFIG_FILE","/tmp/oci-m37300-example-config")
    monkeypatch.setattr(m.shutil,"which",lambda name:"/usr/bin/oci")
    def mock_run(args,**kw):
        calls.append((args,kw))
        return SimpleNamespace(returncode=0,stdout=b'{"data":[]}',stderr=b'PRIVATE_KEY_TEXT')
    monkeypatch.setattr(m.subprocess,"run",mock_run)
    assert m._run(("iam","region-subscription","list","--all"))=={"data":[]}
    assert len(calls)==1
    args,opts=calls[0]
    assert args[:4]==["oci","iam","region-subscription","list"]
    assert args[args.index("--profile")+1]=="FR_FINANCE_OCI"
    assert args[args.index("--config-file")+1]=="/tmp/oci-m37300-example-config"
    assert opts["capture_output"] is True


def test_source_contains_only_oci_list_commands():
    code=(ROOT/"backend/app/oci_staging_live_inventory.py").read_text()
    cli=(ROOT/"backend/scripts/aistudio_oci_live_inventory_readonly.py").read_text()
    assert "SAFE_QUERY_GROUPS" in code
    for dangerous in ("oci compute instance launch","oci compute instance terminate",
                      "oci network vcn create","oci iam compartment create",
                      "oci kms management vault create","terraform apply",
                      "oci compute instance action"):
        assert dangerous not in code+cli
    assert "capture_output=True" in cli
    assert 'OCI_RESOURCE_CREATED=NO' in cli
