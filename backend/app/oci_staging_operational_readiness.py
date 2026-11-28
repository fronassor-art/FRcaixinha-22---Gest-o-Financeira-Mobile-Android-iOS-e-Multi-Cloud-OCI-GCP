"""M37318-M37322: fail-closed operational release readiness from *live* OCI audits.

This never authorizes provisioning, payment, deployment or real users.
Use only with OCIInventorySummary and NetworkReport produced by live reads.
"""
from __future__ import annotations
from dataclasses import dataclass

from .oci_existing_network_audit import NetworkReport
from .oci_staging_live_inventory import OCIInventorySummary


@dataclass(frozen=True)
class StagingReadiness:
    region: str
    network_read_only_verified: bool
    compute_and_vault_read_only_verified: bool
    root_running: int
    staging_running: int
    staging_provisioning: int
    staging_active_vaults: int
    blockers: tuple[str, ...]
    live_backend_verified: bool = False
    public_https_verified: bool = False
    database_tls_and_rls_verified: bool = False
    restore_verified: bool = False
    tenant_auth_verified: bool = False
    provider_authorized: bool = False
    deploy_authorized: bool = False
    paid_resources_authorized: bool = False
    real_pix_authorized: bool = False
    real_users_authorized: bool = False
    cloud_mutations_performed: bool = False


class ReleaseReadinessBlocked(ValueError):
    pass


def assess_staging_readiness(
    inventory: OCIInventorySummary,
    network: NetworkReport,
) -> StagingReadiness:
    if (not isinstance(inventory, OCIInventorySummary)
            or not isinstance(network, NetworkReport)
            or not inventory.observations_from_live_api
            or not inventory.home_region_observed
            or inventory.region != "sa-saopaulo-1"
            or network.region != inventory.region
            or inventory.staging_compartment!="ACTIVE"
            or inventory.root_vcn!="AVAILABLE"
            or inventory.root_subnet!="AVAILABLE"
            or network.vcn!="AVAILABLE"
            or network.subnet!="AVAILABLE"):
        raise ReleaseReadinessBlocked("OCI_LIVE_EVIDENCE_INCOMPLETE")

    blockers=[]
    if inventory.staging_instances_running==0:
        blockers.append("OCI_STAGING_RUNNING_VM_ABSENT")
    if inventory.staging_instances_provisioning>0:
        blockers.append("OCI_STAGING_VM_STILL_PROVISIONING")
    if inventory.staging_vaults_active==0:
        blockers.append("OCI_STAGING_ACTIVE_VAULT_ABSENT")
    if not network.vcn_private_ipv4 or not network.subnet_private_ipv4:
        blockers.append("OCI_NETWORK_PRIVATE_IPV4_NOT_VERIFIED")
    if not network.internet_gateway_enabled or not network.default_ipv4_route_to_igw:
        blockers.append("OCI_PUBLIC_ROUTE_NOT_CONFIRMED")
    if not network.subnet_allows_public_ip:
        blockers.append("OCI_SUBNET_PUBLIC_IP_PROHIBITED")
    if not network.public_tcp_443_rule_present:
        blockers.append("OCI_HTTPS_443_INGRESS_NOT_PREPARED")
    if network.public_tcp_22_rule_present or network.public_db_port_exposure:
        blockers.append("OCI_PUBLIC_ADMIN_OR_DB_PORT_REVIEW_REQUIRED")
    # These gates require independently verified operational evidence.
    blockers.extend((
        "OCI_INSTANCE_PRINCIPAL_IAM_NOT_VERIFIED",
        "OCI_NSG_AND_OS_FIREWALL_NOT_VERIFIED",
        "OCI_PUBLIC_DNS_TLS_HTTPS_NOT_VERIFIED",
        "OCI_DATABASE_TLS_RLS_NOT_VERIFIED",
        "OCI_BACKUP_RESTORE_NOT_VERIFIED",
        "OCI_BACKEND_HEALTH_AND_AUTH_NOT_VERIFIED",
        "OCI_MARKETPLACE_WEBHOOK_AND_SETTLEMENT_NOT_VERIFIED",
        "OCI_PIX_AND_USER_ACTIVATION_NOT_AUTHORIZED",
    ))
    return StagingReadiness(
        region=inventory.region,
        network_read_only_verified=True,
        compute_and_vault_read_only_verified=True,
        root_running=inventory.root_instances_running,
        staging_running=inventory.staging_instances_running,
        staging_provisioning=inventory.staging_instances_provisioning,
        staging_active_vaults=inventory.staging_vaults_active,
        blockers=tuple(blockers),
    )
