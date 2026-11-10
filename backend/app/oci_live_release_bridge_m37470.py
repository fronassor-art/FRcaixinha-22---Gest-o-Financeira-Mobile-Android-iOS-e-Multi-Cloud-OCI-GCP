"""M37470: safe OCI LIVE inventory bridge to canonical release blockers.

Accept ONLY typed summaries returned by the existing authenticated OCI
read-only inspectors. No call here creates resources, connects to a
provider, alters application state, or upgrades the 20 real release gates.
A VM RUNNING proves only an observed lifecycle state, not public reachability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .oci_existing_network_audit import NetworkReport
from .oci_iam_readiness_readonly import IAMReadOnlySummary
from .oci_staging_live_inventory import OCIInventorySummary
from .oci_unified_readiness_readonly import UnifiedReadiness, assess_unified_readonly
from .saas_operational_blockers_m37469 import build_operational_blocker_report


class OCIRealEvidenceBlocked(ValueError):
    """Fixed error identifiers only; never include OCIDs/secrets/provider data."""


@dataclass(frozen=True)
class OCIRealEvidenceM37470:
    region: str
    inventory_from_authenticated_api: bool
    staging_vm_status: str
    staging_vm_running: int
    staging_vm_provisioning: int
    root_vm_running: int
    staging_vault_active: int
    network_status: str
    vcn_found: bool
    subnet_found: bool
    internet_route_observed: bool
    tcp_443_rule_observed: bool
    public_tcp_22_exposure: bool
    public_db_exposure: bool
    iam_inventory_observed: bool
    active_project_dynamic_groups: int
    effective_iam_verified: bool = False
    public_dns_https_verified: bool = False
    database_tls_rls_verified: bool = False
    backup_restore_verified: bool = False
    actual_workload_identity_verified: bool = False
    contract_real_identity_verified: bool = False
    legal_consent_verified: bool = False
    psps_verified: bool = False
    production_authorized: bool = False
    staged_deploy_authorized: bool = False
    user_activation_authorized: bool = False
    pix_authorized: bool = False
    paid_upgrade_authorized: bool = False
    writes_performed: bool = False


def _nonnegative(n: object)->bool:
    return type(n) is int and 0<=n<=100_000


def correlate_readonly_oci(
    inventory: OCIInventorySummary,
    network: NetworkReport,
    iam: IAMReadOnlySummary,
) -> OCIRealEvidenceM37470:
    """Read-only observations only; no authority inferred from positive state."""
    if (type(inventory) is not OCIInventorySummary
            or type(network) is not NetworkReport
            or type(iam) is not IAMReadOnlySummary
            or inventory.region!="sa-saopaulo-1"
            or network.region!=inventory.region
            or iam.region!=inventory.region
            or inventory.home_region_observed is not True
            or inventory.observations_from_live_api is not True
            or inventory.staging_compartment!="ACTIVE"
            or inventory.root_vcn!="AVAILABLE"
            or inventory.root_subnet!="AVAILABLE"
            or network.vcn!="AVAILABLE"
            or network.subnet!="AVAILABLE"
            or network.vcn_private_ipv4 is not True
            or network.subnet_private_ipv4 is not True
            or iam.staging_compartment!="ACTIVE"
            or iam.inspection_only is not True):
        raise OCIRealEvidenceBlocked("M37470_OCI_LIVE_TYPED_INPUT_REQUIRED")
    positive_flags=(
        inventory.deployment_authorized,
        inventory.api_public_https_verified,
        inventory.database_tls_rls_verified,
        inventory.backups_restored_verified,
        inventory.paid_upgrade_authorized,
        inventory.real_users_authorized,
        inventory.real_pix_authorized,
        network.nsgs_on_future_vnic_verified,
        network.host_firewall_verified,
        network.public_https_verified,
        network.vm_running_verified,
        network.iam_vault_verified,
        network.deployment_authorized,
        network.real_pix_authorized,
        network.mutations_performed,
        iam.workload_instance_principal_verified,
        iam.policy_effective_permissions_verified,
        iam.tenant_secret_isolation_verified,
        iam.vault_present_verified,
        iam.real_secret_access_tested,
        iam.cloud_mutations_performed,
        iam.deployment_authorized,
        iam.real_users_authorized,
        iam.pix_real_authorized,
    )
    if any(v is not False for v in positive_flags):
        raise OCIRealEvidenceBlocked("M37470_UNATTESTED_LIVE_PERMISSIONS")
    counts=(
        inventory.root_instances_running,
        inventory.staging_instances_running,
        inventory.staging_instances_provisioning,
        inventory.staging_vaults_active,
        iam.root_dynamic_groups_active,
        iam.project_named_dynamic_groups_active,
        iam.root_policies_active,
        iam.staging_policies_active,
        iam.candidate_secret_bundle_statements,
        network.security_lists_checked,
    )
    if (any(not _nonnegative(x) for x in counts)
            or iam.project_named_dynamic_groups_active>iam.root_dynamic_groups_active
            or type(inventory.staging_vm_present) is not bool
            or inventory.staging_vm_present!=(inventory.staging_instances_running>0)):
        raise OCIRealEvidenceBlocked("M37470_OCI_COUNT_OR_LIFECYCLE_INVALID")
    network_fields=(
        network.vcn_private_ipv4,network.subnet_private_ipv4,
        network.subnet_allows_public_ip,network.internet_gateway_enabled,
        network.default_ipv4_route_to_igw,network.public_tcp_80_rule_present,
        network.public_tcp_443_rule_present,network.public_tcp_22_rule_present,
        network.public_db_port_exposure,
        iam.overly_broad_secret_grants_manual_review,
    )
    if any(type(x) is not bool for x in network_fields):
        raise OCIRealEvidenceBlocked("M37470_OCI_NETWORK_OR_IAM_INVALID")
    # The existing unified module has additional independent invariants.
    try:
        unified: UnifiedReadiness=assess_unified_readonly(inventory,network,iam)
    except (ValueError, TypeError, AttributeError):
        raise OCIRealEvidenceBlocked("M37470_OCI_UNIFIED_CROSSCHECK_FAILED") from None
    if (type(unified) is not UnifiedReadiness
            or unified.deployment_authorized
            or unified.paid_upgrade_authorized
            or unified.user_activation_authorized
            or unified.real_pix_authorized
            or unified.cloud_mutations_performed):
        raise OCIRealEvidenceBlocked("M37470_OCI_UNIFIED_GRANTS_DENIED")

    vm = (
        "RUNNING_OBSERVED_NOT_PUBLIC_SERVICE_PROOF"
        if inventory.staging_instances_running>0 else
        "PROVISIONING_OBSERVED_NOT_RUNNING"
        if inventory.staging_instances_provisioning>0 else
        "NO_RUNNING_STAGING_INSTANCE_OBSERVED"
    )
    return OCIRealEvidenceM37470(
        region=inventory.region,
        inventory_from_authenticated_api=True,
        staging_vm_status=vm,
        staging_vm_running=inventory.staging_instances_running,
        staging_vm_provisioning=inventory.staging_instances_provisioning,
        root_vm_running=inventory.root_instances_running,
        staging_vault_active=inventory.staging_vaults_active,
        network_status=network.state,
        vcn_found=True,subnet_found=True,
        internet_route_observed=network.default_ipv4_route_to_igw,
        tcp_443_rule_observed=network.public_tcp_443_rule_present,
        public_tcp_22_exposure=network.public_tcp_22_rule_present,
        public_db_exposure=network.public_db_port_exposure,
        iam_inventory_observed=True,
        active_project_dynamic_groups=iam.project_named_dynamic_groups_active,
    )


def attach_oci_observation_to_release(
    base: dict, evidence: OCIRealEvidenceM37470,
)->dict:
    """Bind a single OCI observation to M37469 without changing any release gate."""
    if (type(base) is not dict
            or base.get("package")!="M37469"
            or base.get("mode")!="LOCAL_READ_ONLY_NO_NETWORK_NO_DB"
            or base.get("production_authorized") is not False
            or base.get("staging_deployment_authorized") is not False
            or base.get("live_gates_verified")!=0
            or base.get("live_gate_count")!=20
            or base.get("provider_gates_verified")!=0
            or base.get("provider_gate_count")!=7
            or base.get("release_approval_decision")!="NOT_ISSUED"
            or type(evidence) is not OCIRealEvidenceM37470
            or evidence.region!="sa-saopaulo-1"
            or evidence.inventory_from_authenticated_api is not True
            or evidence.staging_vm_status not in (
                "RUNNING_OBSERVED_NOT_PUBLIC_SERVICE_PROOF",
                "PROVISIONING_OBSERVED_NOT_RUNNING",
                "NO_RUNNING_STAGING_INSTANCE_OBSERVED")
            or evidence.staging_vm_running<0
            or evidence.staging_vm_provisioning<0
            or evidence.staging_vm_status!=(
                "RUNNING_OBSERVED_NOT_PUBLIC_SERVICE_PROOF"
                if evidence.staging_vm_running>0 else
                "PROVISIONING_OBSERVED_NOT_RUNNING"
                if evidence.staging_vm_provisioning>0 else
                "NO_RUNNING_STAGING_INSTANCE_OBSERVED")
            or any(getattr(evidence,f) is not False for f in (
                "effective_iam_verified","public_dns_https_verified",
                "database_tls_rls_verified","backup_restore_verified",
                "actual_workload_identity_verified",
                "contract_real_identity_verified","legal_consent_verified",
                "psps_verified","production_authorized",
                "staged_deploy_authorized","user_activation_authorized",
                "pix_authorized","paid_upgrade_authorized",
                "writes_performed"))):
        raise OCIRealEvidenceBlocked("M37470_RELEASE_EVIDENCE_OR_SCOPE_INVALID")
    merged=dict(base)
    merged["package"]="M37470"
    merged["mode"]="OCI_AUTHENTICATED_READ_ONLY_WITH_OFFLINE_MATRIX"
    merged["infrastructure_state"]="LIVE_READ_INVENTORY_ONLY_NOT_DEPLOYED"
    merged["oci_staging_vm_running"]=evidence.staging_vm_status
    merged["oci_observed"]={
        "region":evidence.region,
        "vm_lifecycle":evidence.staging_vm_status,
        "staging_running":evidence.staging_vm_running,
        "staging_provisioning":evidence.staging_vm_provisioning,
        "root_running":evidence.root_vm_running,
        "staging_active_vaults":evidence.staging_vault_active,
        "network_status":evidence.network_status,
        "vcn_present":evidence.vcn_found,
        "subnet_present":evidence.subnet_found,
        "internet_route_configured":evidence.internet_route_observed,
        "tcp_443_rule_present":evidence.tcp_443_rule_observed,
        "public_tcp_22_review":evidence.public_tcp_22_exposure,
        "public_database_port_review":evidence.public_db_exposure,
        "iam_listing_performed":evidence.iam_inventory_observed,
        "project_dynamic_groups_count":evidence.active_project_dynamic_groups,
    }
    merged["live_gates_verified"]=0
    merged["provider_gates_verified"]=0
    merged["production_authorized"]=False
    merged["staging_deployment_authorized"]=False
    merged["release_status"]="BLOCKED_REQUIRES_INDEPENDENT_LIVE_PROOFS"
    merged["release_approval_decision"]="NOT_ISSUED"
    merged["network_calls_performed"]=True  # authenticated READ only, not mutation
    merged["writes_performed"]=False
    return merged
