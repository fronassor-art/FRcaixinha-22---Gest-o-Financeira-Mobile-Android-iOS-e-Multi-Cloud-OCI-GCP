"""M2700: fail-closed OCI terraform-plan JSON audit using offline fixtures."""
import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.oci_staging_plan_guard import (
    CONTRACT, StagingPlanBlocked, audit_plan, audit_plan_file,
)

ROOT=Path(__file__).resolve().parents[2]


def good_plan():
    data = {
        "oci_core_vcn.staging": (
            "oci_core_vcn",
            {"cidr_blocks": ["10.77.0.0/16"], "ipv6cidr_blocks": []}),
        "oci_core_security_list.deny_all": (
            "oci_core_security_list",
            {"ingress_security_rules": [], "egress_security_rules": []}),
        "oci_core_route_table.isolated": (
            "oci_core_route_table", {"route_rules": []}),
        "oci_core_subnet.private": (
            "oci_core_subnet",
            {"cidr_block": "10.77.10.0/24",
             "ipv6cidr_blocks": [],
             "prohibit_public_ip_on_vnic": True}),
    }
    changes=[]
    resources=[]
    for address, (rtype, after) in data.items():
        changes.append({
            "address": address, "mode": "managed", "type": rtype,
            "provider_name": "registry.terraform.io/oracle/oci",
            "change": {
                "actions": ["create"],
                "before": None,
                "after": after,
                "after_unknown": {},
            },
        })
        resources.append({
            "address": address, "mode": "managed",
            "type": rtype, "values": after,
        })
    return {
        "format_version": "1.2",
        "resource_changes": changes,
        "planned_values": {"root_module": {"resources": resources}},
    }


def find(plan, address):
    return next(x for x in plan["resource_changes"] if x["address"] == address)


def test_only_four_isolated_resources_are_accepted():
    plan=good_plan()
    assert len(audit_plan(plan))==4
    assert audit_plan(copy.deepcopy(plan))==audit_plan(plan)


@pytest.mark.parametrize("address,field,value", [
    ("oci_core_subnet.private","prohibit_public_ip_on_vnic",False),
    ("oci_core_subnet.private","prohibit_public_ip_on_vnic",None),
    ("oci_core_subnet.private","cidr_block","0.0.0.0/0"),
    ("oci_core_subnet.private","ipv6cidr_block","2001:db8::/64"),
    ("oci_core_subnet.private","ipv6cidr_blocks",["2001:db8::/64"]),
    ("oci_core_vcn.staging","cidr_blocks",["10.0.0.0/8"]),
    ("oci_core_vcn.staging","ipv6cidr_blocks",["2001:db8::/64"]),
    ("oci_core_security_list.deny_all","ingress_security_rules",[{"source":"0.0.0.0/0"}]),
    ("oci_core_security_list.deny_all","egress_security_rules",[{"destination":"0.0.0.0/0"}]),
    ("oci_core_route_table.isolated","route_rules",[{"destination":"0.0.0.0/0"}]),
])
def test_public_network_or_unexpected_change_rejected(address,field,value):
    p=good_plan()
    find(p,address)["change"]["after"][field]=value
    with pytest.raises(StagingPlanBlocked):
        audit_plan(p)


@pytest.mark.parametrize("actions", [
    ["delete"], ["update"], ["delete","create"],
    ["create","delete"], [], ["read"],
])
def test_destroy_update_or_replace_is_blocked(actions):
    p=good_plan()
    find(p,"oci_core_vcn.staging")["change"]["actions"]=actions
    with pytest.raises(StagingPlanBlocked):
        audit_plan(p)


def test_critical_unknown_attribute_blocked():
    p=good_plan()
    find(p,"oci_core_subnet.private")["change"]["after_unknown"]["prohibit_public_ip_on_vnic"]=True
    with pytest.raises(StagingPlanBlocked):
        audit_plan(p)


@pytest.mark.parametrize("mod", [
    lambda x:x["resource_changes"].pop(),
    lambda x:x["resource_changes"].append(x["resource_changes"][0].copy()),
    lambda x:x["resource_changes"][0].update(address="oci_core_instance.attacker"),
    lambda x:x["resource_changes"][0].update(type="oci_core_instance"),
    lambda x:x["resource_changes"][0].update(index=0),
    lambda x:x["resource_changes"][0].update(mode="data"),
    lambda x:x["resource_changes"][0].update(provider_name="registry.terraform.io/hashicorp/aws"),
    lambda x:x["planned_values"]["root_module"].update(child_modules=[{"resources":[]}]),
    lambda x:x["planned_values"]["root_module"]["resources"].append(
        {"address":"oci_core_instance.attacker","mode":"managed","type":"oci_core_instance"}),
    lambda x:x.update(format_version="2.0"),
])
def test_other_resources_and_bad_plan_schema_blocked(mod):
    p=good_plan()
    mod(p)
    with pytest.raises(StagingPlanBlocked):
        audit_plan(p)


@pytest.mark.parametrize("payload", [
    b"",b"not JSON",b"null",b"[]",
    b'{"format_version":"1.2","format_version":"1.3"}',
    b'{"x":NaN}',
    b"x"*8_000_001,
])
def test_planned_values_are_not_allowed_to_hide_public_rules():
    p=good_plan()
    values=next(x for x in p["planned_values"]["root_module"]["resources"]
                if x["address"]=="oci_core_security_list.deny_all")
    values["values"]["egress_security_rules"]=[{"destination":"0.0.0.0/0"}]
    with pytest.raises(StagingPlanBlocked):
        audit_plan(p)


@pytest.mark.parametrize("mutate", [
    lambda p:p.update(planned_values=None),
    lambda p:p.update(planned_values=[]),
    lambda p:p["resource_changes"][0]["change"].update(actions=[{}]),
    lambda p:p["planned_values"]["root_module"]["resources"][0].update(address=[]),
    lambda p:p["planned_values"]["root_module"]["resources"][0].update(values="oops"),
])
def test_malformed_nested_plan_fails_closed_without_crashes(mutate):
    p=good_plan()
    mutate(p)
    with pytest.raises(StagingPlanBlocked):
        audit_plan(p)


def test_file_guard_rejects_incorrect_or_large_json(tmp_path,payload):
    path=tmp_path/"tfplan.json"
    path.write_bytes(payload)
    with pytest.raises(StagingPlanBlocked):
        audit_plan_file(path)


def test_cli_never_exposes_plan_or_sensitive_data(tmp_path):
    sample=good_plan()
    path=tmp_path/"sensitive-secret-staging-plan.json"
    sample["resource_changes"][0]["change"]["after"]["ingress_security_rules"]=[
        {"api_key":"SECRETVALUE-DO-NOT-PRINT"}
    ]
    path.write_text(json.dumps(sample),encoding="utf-8")
    command=[sys.executable,str(ROOT/"backend/scripts/aistudio_oci_plan_guard.py"),str(path)]
    result=subprocess.run(command,text=True,capture_output=True)
    assert result.returncode==3
    assert "OCI_STAGING_PLAN_GUARD=BLOCKED" in result.stdout
    assert "SECRETVALUE" not in result.stdout+result.stderr
    assert "sensitive-secret" not in result.stdout+result.stderr


def test_cli_success_is_not_apply_permission(tmp_path):
    path=tmp_path/"plan.json"
    path.write_text(json.dumps(good_plan()),encoding="utf-8")
    command=[sys.executable,str(ROOT/"backend/scripts/aistudio_oci_plan_guard.py"),str(path)]
    result=subprocess.run(command,text=True,capture_output=True)
    assert result.returncode==0
    assert "OCI_STAGING_PLAN_GUARD=PASS" in result.stdout
    assert "APPLY_AUTORIZADO=NAO" in result.stdout


def test_contract_and_old_gate_still_block_financial():
    with TestClient(app) as c:
        body=c.get("/api/health/features/m2700").json()
    assert body["workstream"]=="AI_STUDIO"
    assert body["contract"]==CONTRACT
    assert body["oci_plan_guard_enabled"] is True
    assert body["oci_staging_deployed"] is False
    assert body["terraform_apply_authorized"] is False
    for name in ("provider_connected","bank_reconciled","ledger_written",
                 "financial_closing_authorized","real_payments_enabled"):
        assert body[name] is False


def test_gitignore_protects_local_terraform_state_and_vars():
    content=(ROOT/".gitignore").read_text(encoding="utf-8")
    for value in ("**/.terraform/","**/*.tfstate","**/*.tfstate.*",
                  "**/*.tfvars","**/*.tfplan","**/*tfplan.json"):
        assert value in content
