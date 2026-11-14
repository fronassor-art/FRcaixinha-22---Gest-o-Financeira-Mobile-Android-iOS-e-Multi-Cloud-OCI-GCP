"""M37318-M37322: actual OCI operational blockers stay fail-closed."""
from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

from app.oci_staging_live_inventory import OCIInventorySummary
from app.oci_existing_network_audit import NetworkReport
from app.oci_staging_operational_readiness import (
    ReleaseReadinessBlocked,assess_staging_readiness,
)

ROOT=Path(__file__).resolve().parents[2]
TEN="ocid1.tenancy.oc1.."+"a"*20


def inv(**kwargs):
    basics=dict(
        region="sa-saopaulo-1",home_region_observed=True,
        staging_compartment="ACTIVE",root_vcn="AVAILABLE",
        root_subnet="AVAILABLE",root_instances_running=0,
        staging_instances_running=0,staging_instances_provisioning=0,
        staging_vaults_active=0,staging_vm_present=False,
        observations_from_live_api=True,
    )
    basics.update(kwargs)
    return OCIInventorySummary(**basics)


def net(**kwargs):
    basics=dict(
        region="sa-saopaulo-1",
        state="NETWORK_HTTPS_INGRESS_NOT_PREPARED",
        vcn="AVAILABLE",subnet="AVAILABLE",
        vcn_private_ipv4=True,subnet_private_ipv4=True,
        subnet_allows_public_ip=True,internet_gateway_enabled=True,
        default_ipv4_route_to_igw=True,security_lists_checked=1,
        public_tcp_80_rule_present=False,public_tcp_443_rule_present=False,
        public_tcp_22_rule_present=False,public_db_port_exposure=False,
    )
    basics.update(kwargs)
    return NetworkReport(**basics)


def test_live_evidence_2026_11_09_matches_safely_blocked_plan():
    summary=assess_staging_readiness(inv(),net())
    assert summary.root_running==0 and summary.staging_running==0
    assert summary.staging_active_vaults==0
    assert "OCI_STAGING_RUNNING_VM_ABSENT" in summary.blockers
    assert "OCI_STAGING_ACTIVE_VAULT_ABSENT" in summary.blockers
    assert "OCI_HTTPS_443_INGRESS_NOT_PREPARED" in summary.blockers
    assert summary.network_read_only_verified
    assert summary.compute_and_vault_read_only_verified
    for flag in ("live_backend_verified","public_https_verified",
                 "database_tls_and_rls_verified","restore_verified",
                 "tenant_auth_verified","provider_authorized",
                 "deploy_authorized","paid_resources_authorized",
                 "real_pix_authorized","real_users_authorized",
                 "cloud_mutations_performed"):
        assert getattr(summary,flag) is False


def test_vm_and_vault_presence_does_not_approve_deployment():
    summary=assess_staging_readiness(
        inv(staging_instances_running=1,staging_vaults_active=1,
            staging_vm_present=True),
        net(public_tcp_443_rule_present=True),
    )
    assert "OCI_STAGING_RUNNING_VM_ABSENT" not in summary.blockers
    assert "OCI_STAGING_ACTIVE_VAULT_ABSENT" not in summary.blockers
    assert "OCI_HTTPS_443_INGRESS_NOT_PREPARED" not in summary.blockers
    assert summary.blockers
    assert not summary.deploy_authorized
    assert not summary.real_users_authorized
    assert not summary.real_pix_authorized


def test_public_ssh_and_database_ports_are_blockers():
    summary=assess_staging_readiness(inv(),net(
        public_tcp_22_rule_present=True,public_db_port_exposure=True,
    ))
    assert "OCI_PUBLIC_ADMIN_OR_DB_PORT_REVIEW_REQUIRED" in summary.blockers


@pytest.mark.parametrize("change",[
    {"subnet_allows_public_ip":False},
    {"internet_gateway_enabled":False},
    {"default_ipv4_route_to_igw":False},
    {"vcn_private_ipv4":False},
])
def test_network_misconfiguration_stays_a_blocker(change):
    summary=assess_staging_readiness(inv(),net(**change))
    assert summary.blockers
    assert not summary.deploy_authorized


@pytest.mark.parametrize("what",[
    "region","home_region_observed","staging_compartment",
    "root_vcn","root_subnet","observations_from_live_api",
])
def test_unverified_inventory_fails_closed(what):
    value={
        "region":"us-ashburn-1",
        "home_region_observed":False,
        "staging_compartment":"UNKNOWN",
        "root_vcn":"MISSING",
        "root_subnet":"MISSING",
        "observations_from_live_api":False,
    }[what]
    with pytest.raises(ReleaseReadinessBlocked,match="OCI_LIVE_EVIDENCE_INCOMPLETE"):
        assess_staging_readiness(inv(**{what:value}),net())


def test_mismatched_region_fails_closed():
    with pytest.raises(ReleaseReadinessBlocked,match="OCI_LIVE_EVIDENCE_INCOMPLETE"):
        assess_staging_readiness(inv(),net(region="us-ashburn-1"))


def _script():
    path=ROOT/"backend/scripts/aistudio_oci_operational_gates_readonly.py"
    spec=importlib.util.spec_from_file_location("m37322_operational_gates",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_single_read_only_script_formats_live_counts_without_ocids(monkeypatch,capsys):
    m=_script()
    calls=[]
    monkeypatch.setattr(m,"read_cli_identity",lambda:(TEN,"sa-saopaulo-1"))
    def get_inventory(**kw):
        calls.append("inventory")
        assert kw["tenancy_id"]==TEN
        return inv()
    monkeypatch.setattr(m,"inspect_live_oci_inventory",get_inventory)
    def get_network(**kw):
        calls.append("network")
        assert kw["tenancy_id"]==TEN
        return net()
    monkeypatch.setattr(m,"inspect_existing_root_network",get_network)
    class NoneRetryStrategy: pass
    sdk=SimpleNamespace(
        config=SimpleNamespace(from_file=lambda **kw:{"tenancy":TEN,"region":"sa-saopaulo-1"}),
        core=SimpleNamespace(VirtualNetworkClient=lambda *a,**k: object()),
        retry=SimpleNamespace(NoneRetryStrategy=NoneRetryStrategy),
    )
    monkeypatch.setitem(sys.modules,"oci",sdk)
    assert m.main()==0
    output=capsys.readouterr().out
    assert calls==["inventory","network"]
    assert "OCI_M37322_STATUS=READ_ONLY_PASS" in output
    assert "OCI_STAGING_VM_RUNNING=0" in output
    assert "OCI_STAGING_ACTIVE_VAULT=0" in output
    assert "OCI_BLOCKER=OCI_STAGING_RUNNING_VM_ABSENT" in output
    assert "OCI_DEPLOYMENT_AUTHORIZED=NO" in output
    assert "PIX_REAL=OFF" in output
    assert TEN not in output


def test_single_read_only_script_denies_mismatched_profile(monkeypatch,capsys):
    m=_script()
    monkeypatch.setattr(m,"read_cli_identity",lambda:(TEN,"sa-saopaulo-1"))
    monkeypatch.setattr(m,"inspect_live_oci_inventory",lambda **kw:inv())
    sdk=SimpleNamespace(
        config=SimpleNamespace(from_file=lambda **kw:{"tenancy":"different","region":"sa-saopaulo-1"}),
    )
    monkeypatch.setitem(sys.modules,"oci",sdk)
    assert m.main()==2
    output=capsys.readouterr().out
    assert "OCI_M37322_STATUS=BLOCKED" in output
    assert "OCI_PROFILE_MISMATCH" in output
    assert "OCI_DEPLOYMENT_AUTHORIZED=NO" in output


def test_no_cloud_writes_finance_or_live_enrollment_in_scripts():
    code=(ROOT/"backend/scripts/aistudio_oci_operational_gates_readonly.py").read_text()
    netcode=(ROOT/"backend/scripts/aistudio_oci_existing_network_readonly.py").read_text()
    for forbidden in (
        "terraform apply","client.launch_instance(","create_vault(","create_vcn(",
        "client.update_security_list(","client.update_route_table(",
        "client.create_internet_gateway(","create_secret(","create_key(",
        "enable_real_pix(","activate_user(",
    ):
        assert forbidden not in code+netcode
    assert "OCI_DEPLOYMENT_AUTHORIZED=NO" in code
    assert "PIX_REAL=OFF" in code
