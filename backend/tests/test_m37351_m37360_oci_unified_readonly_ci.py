"""M37360: no deployment, secret read, or money movement; read-only mocks."""
from dataclasses import replace
from pathlib import Path
import pytest
from app.oci_staging_live_inventory import OCIInventorySummary
from app.oci_existing_network_audit import NetworkReport
from app.oci_iam_readiness_readonly import IAMReadOnlySummary
from app.oci_unified_readiness_readonly import UnifiedReadinessBlocked,assess_unified_readonly,format_unified_report

ROOT=Path(__file__).resolve().parents[2]
def fixture():
    inv=OCIInventorySummary(
        region="sa-saopaulo-1",home_region_observed=True,
        staging_compartment="ACTIVE",root_vcn="AVAILABLE",root_subnet="AVAILABLE",
        root_instances_running=0,staging_instances_running=0,staging_instances_provisioning=0,
        staging_vaults_active=0,staging_vm_present=False,observations_from_live_api=True)
    net=NetworkReport(
        region="sa-saopaulo-1",state="NETWORK_HTTPS_INGRESS_NOT_PREPARED",
        vcn="AVAILABLE",subnet="AVAILABLE",vcn_private_ipv4=True,subnet_private_ipv4=True,
        subnet_allows_public_ip=True,internet_gateway_enabled=True,default_ipv4_route_to_igw=True,
        security_lists_checked=1,public_tcp_80_rule_present=False,public_tcp_443_rule_present=False,
        public_tcp_22_rule_present=False,public_db_port_exposure=False)
    iam=IAMReadOnlySummary(
        region="sa-saopaulo-1",staging_compartment="ACTIVE",
        root_dynamic_groups_active=0,project_named_dynamic_groups_active=0,
        root_policies_active=1,staging_policies_active=0,candidate_secret_bundle_statements=0,
        overly_broad_secret_grants_manual_review=False)
    return inv,net,iam

def test_zero_vm_vault_iam_results_block_release():
    report=assess_unified_readonly(*fixture())
    assert report.staging_running==0
    assert len(report.blockers)>=11
    for code in ("OCI_STAGING_RUNNING_VM_ABSENT","OCI_STAGING_ACTIVE_VAULT_ABSENT",
                 "OCI_NO_ACTIVE_DYNAMIC_GROUPS_OBSERVED",
                 "OCI_NO_SECRET_BUNDLE_POLICY_CANDIDATE_OBSERVED",
                 "OCI_IAM_EFFECTIVE_PERMISSION_NOT_ATTESTED",
                 "OCI_OTHER_TENANT_SECRET_DENIAL_NOT_TESTED"):
        assert code in report.blockers
    for flag in ("effective_iam_verified","instance_principal_verified",
                 "tenant_secret_isolation_verified","deployment_authorized",
                 "paid_upgrade_authorized","user_activation_authorized",
                 "real_pix_authorized","cloud_mutations_performed"):
        assert getattr(report,flag) is False

def test_candidate_group_and_vm_do_not_prove_access():
    inv,net,iam=fixture()
    inv=replace(inv,staging_instances_running=1,staging_vm_present=True,staging_vaults_active=1)
    net=replace(net,public_tcp_443_rule_present=True)
    iam=replace(iam,root_dynamic_groups_active=1,project_named_dynamic_groups_active=1,
                candidate_secret_bundle_statements=1)
    report=assess_unified_readonly(inv,net,iam)
    assert "OCI_NO_ACTIVE_DYNAMIC_GROUPS_OBSERVED" not in report.blockers
    assert "OCI_IAM_EFFECTIVE_PERMISSION_NOT_ATTESTED" in report.blockers
    assert not report.deployment_authorized

@pytest.mark.parametrize("flag",[
    "workload_instance_principal_verified","policy_effective_permissions_verified",
    "tenant_secret_isolation_verified","real_secret_access_tested",
    "cloud_mutations_performed","deployment_authorized","real_users_authorized",
    "pix_real_authorized","vault_present_verified",
])
def test_iam_claimed_effective_or_mutated_is_denied(flag):
    inv,net,iam=fixture()
    with pytest.raises(UnifiedReadinessBlocked,match="NOT_READ_ONLY"):
        assess_unified_readonly(inv,net,replace(iam,**{flag:True}))

@pytest.mark.parametrize("field,value",[
    ("region","us-ashburn-1"),("staging_compartment","INACTIVE"),("inspection_only",False),
])
def test_invalid_iam_context_rejected(field,value):
    inv,net,iam=fixture()
    with pytest.raises(UnifiedReadinessBlocked):
        assess_unified_readonly(inv,net,replace(iam,**{field:value}))

@pytest.mark.parametrize("field,value",[
    ("root_dynamic_groups_active",-1),("root_dynamic_groups_active",True),
    ("project_named_dynamic_groups_active",2),("candidate_secret_bundle_statements",9999),
])
def test_invalid_counts_rejected(field,value):
    inv,net,iam=fixture()
    with pytest.raises(UnifiedReadinessBlocked,match="COUNTS_INVALID"):
        assess_unified_readonly(inv,net,replace(iam,**{field:value}))

def test_unattested_inventory_rejected():
    inv,net,iam=fixture()
    with pytest.raises(UnifiedReadinessBlocked,match="LIVE_EVIDENCE_INCOMPLETE"):
        assess_unified_readonly(replace(inv,observations_from_live_api=False),net,iam)

def test_public_database_exposure_cannot_be_approved():
    inv,net,iam=fixture()
    result=assess_unified_readonly(inv,replace(net,public_db_port_exposure=True),iam)
    assert "OCI_PUBLIC_ADMIN_OR_DB_PORT_REVIEW_REQUIRED" in result.blockers
    assert not result.deployment_authorized

def test_broad_policy_is_manual_review():
    inv,net,iam=fixture()
    result=assess_unified_readonly(inv,net,replace(iam,overly_broad_secret_grants_manual_review=True))
    assert "OCI_IAM_BROAD_POLICY_MANUAL_REVIEW" in result.blockers

def test_output_redacted_and_no_activation():
    result=assess_unified_readonly(*fixture())
    output="\n".join(format_unified_report(result))
    for marker in ("M37360_STATUS=READ_ONLY_PASS","OCI_DEPLOYMENT_AUTHORIZED=NO",
                   "OCI_INSTANCE_PRINCIPAL=NOT_AUTHENTICATED",
                   "PIX_REAL=OFF","REAL_USER_ACTIVATION=OFF"):
        assert marker in output
    for marker in ("ocid1.","matching_rule","secret-bundles","BEGIN PRIVATE KEY"):
        assert marker not in output

def test_script_contains_no_cloud_write_or_secret_bundle_read():
    code=(ROOT/"backend/scripts/aistudio_oci_unified_readonly.py").read_text()
    for forbidden in ("create_policy(","launch_instance(","create_vault(",
                      "create_dynamic_group(","get_secret_bundle(","terraform apply",
                      "subprocess.run(","psycopg.connect("):
        assert forbidden not in code
