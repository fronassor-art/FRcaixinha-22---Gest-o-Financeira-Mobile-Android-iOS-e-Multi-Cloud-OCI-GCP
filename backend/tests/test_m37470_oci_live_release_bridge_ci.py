"""M37470 OCI authenticated inventory correlation: never release real FR Finance."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import importlib.util
import json

import pytest

from app.oci_existing_network_audit import NetworkReport
from app.oci_iam_readiness_readonly import IAMReadOnlySummary
from app.oci_staging_live_inventory import OCIInventorySummary
from app.oci_live_release_bridge_m37470 import (
    OCIRealEvidenceBlocked,
    OCIRealEvidenceM37470,
    attach_oci_observation_to_release,
    correlate_readonly_oci,
)
from app.saas_operational_blockers_m37469 import build_operational_blocker_report

ROOT=Path(__file__).resolve().parents[2]
CLI=ROOT/"backend/scripts/aistudio_m37470_oci_live_release_readonly.py"


def inventory(*,running=0,provisioning=0,**changes):
    args=dict(
        region="sa-saopaulo-1",home_region_observed=True,
        staging_compartment="ACTIVE",
        root_vcn="AVAILABLE",root_subnet="AVAILABLE",
        root_instances_running=0,
        staging_instances_running=running,
        staging_instances_provisioning=provisioning,
        staging_vaults_active=0,
        staging_vm_present=bool(running),
        observations_from_live_api=True,
    )
    args.update(changes)
    return OCIInventorySummary(**args)


def network(**changes):
    args=dict(
        region="sa-saopaulo-1",state="NETWORK_ONLY_NO_VM_OR_PUBLIC_TLS_PROOF",
        vcn="AVAILABLE",subnet="AVAILABLE",
        vcn_private_ipv4=True,subnet_private_ipv4=True,
        subnet_allows_public_ip=True,
        internet_gateway_enabled=True,default_ipv4_route_to_igw=True,
        security_lists_checked=1,
        public_tcp_80_rule_present=False,public_tcp_443_rule_present=True,
        public_tcp_22_rule_present=False,public_db_port_exposure=False,
    )
    args.update(changes)
    return NetworkReport(**args)


def iam(**changes):
    args=dict(
        region="sa-saopaulo-1",staging_compartment="ACTIVE",
        root_dynamic_groups_active=1,project_named_dynamic_groups_active=1,
        root_policies_active=1,staging_policies_active=1,
        candidate_secret_bundle_statements=1,
        overly_broad_secret_grants_manual_review=False,
    )
    args.update(changes)
    return IAMReadOnlySummary(**args)


def observe(i=None,n=None,a=None):
    return correlate_readonly_oci(
        inventory() if i is None else i,
        network() if n is None else n,
        iam() if a is None else a,
    )


def baseline():
    return build_operational_blocker_report(root=ROOT,env={})


def test_zero_staging_vm_stays_absent_after_authenticated_read():
    x=observe()
    assert x.staging_vm_status=="NO_RUNNING_STAGING_INSTANCE_OBSERVED"
    assert x.staging_vm_running==0
    assert x.inventory_from_authenticated_api is True
    assert x.region=="sa-saopaulo-1"


def test_running_vm_observed_but_never_dns_https_or_deployment():
    x=observe(i=inventory(running=1))
    assert x.staging_vm_status=="RUNNING_OBSERVED_NOT_PUBLIC_SERVICE_PROOF"
    assert x.staging_vm_running==1
    assert x.vcn_found and x.subnet_found
    assert x.internet_route_observed
    assert x.tcp_443_rule_observed
    assert x.iam_inventory_observed
    assert x.active_project_dynamic_groups==1
    assert not x.public_dns_https_verified
    assert not x.database_tls_rls_verified
    assert not x.production_authorized
    assert not x.staged_deploy_authorized
    assert not x.paid_upgrade_authorized
    assert not x.user_activation_authorized
    assert not x.pix_authorized
    assert not x.writes_performed


def test_provisioning_only_never_becomes_running():
    x=observe(i=inventory(provisioning=2))
    assert x.staging_vm_status=="PROVISIONING_OBSERVED_NOT_RUNNING"
    assert x.staging_vm_running==0
    assert x.staging_vm_provisioning==2


@pytest.mark.parametrize("wrong",[
    {"region":"us-ashburn-1"},
    {"home_region_observed":False},
    {"observations_from_live_api":False},
    {"staging_compartment":"MISSING"},
    {"root_vcn":"MISSING"},
    {"root_subnet":"MISSING"},
    {"staging_vm_present":True},
    {"staging_instances_running":-1},
    {"staging_instances_provisioning":-1},
    {"root_instances_running":True},
    {"staging_vaults_active":-1},
    {"deployment_authorized":True},
    {"api_public_https_verified":True},
    {"database_tls_rls_verified":True},
    {"backups_restored_verified":True},
    {"paid_upgrade_authorized":True},
    {"real_users_authorized":True},
    {"real_pix_authorized":True},
])
def test_untrusted_or_fake_oci_inventory_rejected(wrong):
    with pytest.raises(OCIRealEvidenceBlocked):
        observe(i=inventory(**wrong))


@pytest.mark.parametrize("wrong",[
    {"region":"us-ashburn-1"},
    {"vcn":"MISSING"},{"subnet":"MISSING"},
    {"vcn_private_ipv4":False},
    {"subnet_private_ipv4":False},
    {"security_lists_checked":-1},
    {"public_tcp_22_rule_present":"TRUE"},
    {"public_db_port_exposure":None},
    {"public_https_verified":True},
    {"host_firewall_verified":True},
    {"nsgs_on_future_vnic_verified":True},
    {"vm_running_verified":True},
    {"iam_vault_verified":True},
    {"deployment_authorized":True},
    {"real_pix_authorized":True},
    {"mutations_performed":True},
])
def test_network_inventory_cannot_self_attest_live_approval(wrong):
    with pytest.raises(OCIRealEvidenceBlocked):
        observe(n=network(**wrong))


@pytest.mark.parametrize("wrong",[
    {"region":"us-ashburn-1"},
    {"staging_compartment":"MISSING"},
    {"inspection_only":False},
    {"root_dynamic_groups_active":-1},
    {"project_named_dynamic_groups_active":2},
    {"root_policies_active":-1},
    {"staging_policies_active":-1},
    {"candidate_secret_bundle_statements":-1},
    {"workload_instance_principal_verified":True},
    {"policy_effective_permissions_verified":True},
    {"tenant_secret_isolation_verified":True},
    {"vault_present_verified":True},
    {"real_secret_access_tested":True},
    {"cloud_mutations_performed":True},
    {"deployment_authorized":True},
    {"real_users_authorized":True},
    {"pix_real_authorized":True},
])
def test_iam_inventory_never_proves_secret_access(wrong):
    with pytest.raises(OCIRealEvidenceBlocked):
        observe(a=iam(**wrong))


def test_merge_full_live_observation_cannot_promote_any_of_twenty_gates():
    merged=attach_oci_observation_to_release(
        baseline(),observe(i=inventory(running=2)),
    )
    assert merged["package"]=="M37470"
    assert merged["mode"]=="OCI_AUTHENTICATED_READ_ONLY_WITH_OFFLINE_MATRIX"
    assert merged["live_gate_count"]==20
    assert merged["live_gates_verified"]==0
    assert merged["provider_gate_count"]==7
    assert merged["provider_gates_verified"]==0
    assert not merged["production_authorized"]
    assert not merged["staging_deployment_authorized"]
    assert merged["release_approval_decision"]=="NOT_ISSUED"
    assert merged["network_calls_performed"] is True
    assert merged["writes_performed"] is False
    assert merged["oci_observed"]["staging_running"]==2
    assert merged["oci_staging_vm_running"]=="RUNNING_OBSERVED_NOT_PUBLIC_SERVICE_PROOF"


def test_merge_does_not_mutate_original_matrix():
    original=baseline()
    old=original.copy()
    merged=attach_oci_observation_to_release(original,observe())
    assert original==old and original["package"]=="M37469"
    assert merged is not original


@pytest.mark.parametrize("bad",[
    {"package":"OTHER"},
    {"mode":"AUTO_ACTIVATION"},
    {"production_authorized":True},
    {"staging_deployment_authorized":True},
    {"live_gates_verified":1},
    {"live_gate_count":19},
    {"provider_gates_verified":1},
    {"provider_gate_count":6},
    {"release_approval_decision":"APPROVED"},
    {"writes_performed":True},
    {"financial_tables_written":True},
    {"sql_migrations_applied":True},
    {"network_calls_performed":True},
    {"ci_proof_is_live_attestation":True},
    {"ci_only_code_cannot_activate_users":False},
    {"all_live_actions_disabled_by_this_tool":{"real_admins":True}},
    {"blockers":[]},
])

def test_existing_release_guard_can_never_be_overridden(bad):
    with pytest.raises(OCIRealEvidenceBlocked):
        attach_oci_observation_to_release({**baseline(),**bad},observe())


def test_forged_individual_live_gate_rejected():
    from copy import deepcopy
    b=deepcopy(baseline())
    b["blockers"][0]["verified_live"]=True
    with pytest.raises(OCIRealEvidenceBlocked):
        attach_oci_observation_to_release(b,observe())


@pytest.mark.parametrize("bad",[
    {"region":"us-ashburn-1"},
    {"inventory_from_authenticated_api":False},
    {"staging_vm_running":1},
    {"staging_vm_status":"RUNNING"},
    {"effective_iam_verified":True},
    {"public_dns_https_verified":True},
    {"database_tls_rls_verified":True},
    {"backup_restore_verified":True},
    {"actual_workload_identity_verified":True},
    {"contract_real_identity_verified":True},
    {"legal_consent_verified":True},
    {"psps_verified":True},
    {"production_authorized":True},
    {"staged_deploy_authorized":True},
    {"user_activation_authorized":True},
    {"pix_authorized":True},
    {"paid_upgrade_authorized":True},
    {"writes_performed":True},
])
def test_forged_live_evidence_rejected_before_merging(bad):
    with pytest.raises(OCIRealEvidenceBlocked):
        attach_oci_observation_to_release(baseline(),replace(observe(),**bad))


def test_returned_inventory_has_no_ocid_token_or_secret():
    x=attach_oci_observation_to_release(baseline(),observe(i=inventory(running=1)))
    raw=json.dumps(x,ensure_ascii=False)
    assert "ocid1." not in raw
    assert "API_KEY" not in raw
    assert "SECRET_VALUE" not in raw
    assert "refresh_token" not in raw
    assert "FR_FINANCE_OCI_PRIVATE_KEY" not in raw
    assert x["oci_observed"]["network_status"].startswith("NETWORK_")


def load_script():
    spec=importlib.util.spec_from_file_location("m37470_cli",CLI)
    assert spec is not None and spec.loader is not None
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_cli_is_offline_no_network(capsys,monkeypatch):
    mod=load_script()
    def denied():
        raise AssertionError("OCI must not be contacted by default")
    monkeypatch.setattr(mod,"read_only_oci_observation",denied)
    assert mod.main([])==0
    out=capsys.readouterr().out
    assert "M37470_MODE=NO_CLOUD_ACCESS" in out
    assert "M37470_OCI_VM=NOT_QUERIED" in out
    assert "M37470_PRODUCTION_RELEASE=BLOCKED" in out
    assert "M37470_ORIGINAL_POSTGRES_UNTOUCHED=YES" in out


def test_explicit_live_cli_mocked_authenticated_snapshot(capsys,monkeypatch):
    mod=load_script()
    monkeypatch.setattr(mod,"read_only_oci_observation",
                        lambda:observe(i=inventory(running=1)))
    assert mod.main(["live"])==0
    out=capsys.readouterr().out
    assert "M37470_OCI_READONLY=PASS" in out
    assert "M37470_VM_STAGING=RUNNING_OBSERVED_NOT_PUBLIC_SERVICE_PROOF" in out
    assert "M37470_VM_RUNNING_COUNT=1" in out
    assert "M37470_LIVE_GATES_VERIFIED=0/20" in out
    assert "M37470_PROVIDER_GATES_VERIFIED=0/7" in out
    assert "M37470_DEPLOYMENT_AUTHORIZED=NO" in out
    assert "M37470_REAL_ACTIVATION_AUTHORIZED=NO" in out
    assert "M37470_PIX_REAL=OFF" in out


def test_explicit_live_cloud_read_failure_fails_closed(capsys,monkeypatch):
    mod=load_script()
    def no_access():
        raise OCIRealEvidenceBlocked("M37470_OCI_LIVE_TYPED_INPUT_REQUIRED")
    monkeypatch.setattr(mod,"read_only_oci_observation",no_access)
    assert mod.main(["live"])==2
    out=capsys.readouterr().out
    assert "M37470_OCI_READONLY=BLOCKED_INCOMPLETE_OR_UNTRUSTED_EVIDENCE" in out
    assert "M37470_REAL_ACTIVATION_AUTHORIZED=NO" in out


def test_json_emits_only_aggregated_nonsecret_values(capsys,monkeypatch):
    mod=load_script()
    monkeypatch.setattr(mod,"read_only_oci_observation",lambda:observe())
    assert mod.main(["json"])==0
    data=json.loads(capsys.readouterr().out)
    assert data["live_gates_verified"]==0
    assert not data["production_authorized"]
    assert data["oci_observed"]["staging_running"]==0
    assert data["oci_observed"]["region"]=="sa-saopaulo-1"


def test_cli_does_not_run_oci_mutation_or_connect_to_local_db():
    script=CLI.read_text()
    for forbidden in (
        "launch_instance(", "create_instance(", "create_vault(", "update_vcn(",
        "create_dynamic_group(", "delete_policy(", "oci compute instance launch",
        "subprocess.run(", "psycopg.connect(", "asyncpg.connect(",
        "os.environ[", "payment_authorized=True", "real_pix_authorized=True",
    ):
        assert forbidden not in script
    assert "read_cli_identity()" in script
    assert "inspect_live_oci_inventory(" in script
    assert "inspect_existing_root_network(" in script
    assert "inspect_iam_readonly(" in script
    assert "oci.retry.NoneRetryStrategy()" in script


def test_workflow_runs_offline_only_and_never_live_unconfigured_on_github():
    text=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()
    assert "backend/tests/test_m37470_oci_live_release_bridge_ci.py" in text
    assert "aistudio_m37470_oci_live_release_readonly.py offline" in text
    assert "aistudio_m37470_oci_live_release_readonly.py live" not in text
    assert "M37470" not in (ROOT/"backend/migration_catalog_ai_studio.json").read_text()
