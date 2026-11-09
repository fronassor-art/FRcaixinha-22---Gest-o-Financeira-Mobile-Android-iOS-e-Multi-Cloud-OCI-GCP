"""M37360: OCI authenticated-read evidence joined; NEVER authorizes deployment."""
from dataclasses import dataclass
from .oci_existing_network_audit import NetworkReport
from .oci_iam_readiness_readonly import IAMReadOnlySummary
from .oci_staging_live_inventory import OCIInventorySummary
from .oci_staging_operational_readiness import ReleaseReadinessBlocked,assess_staging_readiness

class UnifiedReadinessBlocked(ValueError):
    """Sanitized fixed reasons only."""

@dataclass(frozen=True)
class UnifiedReadiness:
    region: str
    root_running: int
    staging_running: int
    staging_provisioning: int
    staging_active_vaults: int
    active_dynamic_groups: int
    project_named_groups: int
    candidate_secret_bundle_statements: int
    blockers: tuple[str,...]
    effective_iam_verified: bool=False
    instance_principal_verified: bool=False
    tenant_secret_isolation_verified: bool=False
    deployment_authorized: bool=False
    paid_upgrade_authorized: bool=False
    user_activation_authorized: bool=False
    real_pix_authorized: bool=False
    cloud_mutations_performed: bool=False

def assess_unified_readonly(inventory:OCIInventorySummary,network:NetworkReport,iam:IAMReadOnlySummary)->UnifiedReadiness:
    if not isinstance(inventory,OCIInventorySummary) or not isinstance(network,NetworkReport):
        raise UnifiedReadinessBlocked("OCI_UNIFIED_LIVE_EVIDENCE_INCOMPLETE")
    if not isinstance(iam,IAMReadOnlySummary):
        raise UnifiedReadinessBlocked("OCI_UNIFIED_IAM_EVIDENCE_MISSING")
    if iam.region!="sa-saopaulo-1" or iam.region!=inventory.region or iam.staging_compartment!="ACTIVE":
        raise UnifiedReadinessBlocked("OCI_UNIFIED_REGION_OR_STAGING_MISMATCH")
    if (iam.inspection_only is not True or iam.workload_instance_principal_verified
            or iam.policy_effective_permissions_verified or iam.tenant_secret_isolation_verified
            or iam.real_secret_access_tested or iam.cloud_mutations_performed
            or iam.deployment_authorized or iam.real_users_authorized or iam.pix_real_authorized
            or iam.vault_present_verified):
        raise UnifiedReadinessBlocked("OCI_UNIFIED_IAM_NOT_READ_ONLY")
    values=(iam.root_dynamic_groups_active,iam.project_named_dynamic_groups_active,
            iam.root_policies_active,iam.staging_policies_active,
            iam.candidate_secret_bundle_statements)
    if (any(type(v) is not int or not 0<=v<=2000 for v in values)
            or iam.project_named_dynamic_groups_active>iam.root_dynamic_groups_active):
        raise UnifiedReadinessBlocked("OCI_UNIFIED_IAM_COUNTS_INVALID")
    if type(iam.overly_broad_secret_grants_manual_review) is not bool:
        raise UnifiedReadinessBlocked("OCI_UNIFIED_IAM_SCHEMA_INVALID")
    try:
        base=assess_staging_readiness(inventory,network)
    except (ReleaseReadinessBlocked,TypeError,AttributeError):
        raise UnifiedReadinessBlocked("OCI_UNIFIED_LIVE_EVIDENCE_INCOMPLETE") from None
    blockers=list(base.blockers)
    if iam.root_dynamic_groups_active==0:
        blockers.append("OCI_NO_ACTIVE_DYNAMIC_GROUPS_OBSERVED")
    if iam.project_named_dynamic_groups_active==0:
        blockers.append("OCI_NO_PROJECT_NAMED_DYNAMIC_GROUP_OBSERVED")
    if iam.candidate_secret_bundle_statements==0:
        blockers.append("OCI_NO_SECRET_BUNDLE_POLICY_CANDIDATE_OBSERVED")
    if iam.overly_broad_secret_grants_manual_review:
        blockers.append("OCI_IAM_BROAD_POLICY_MANUAL_REVIEW")
    blockers.extend(("OCI_IAM_EFFECTIVE_PERMISSION_NOT_ATTESTED",
                     "OCI_INSTANCE_PRINCIPAL_NOT_AUTHENTICATED",
                     "OCI_OTHER_TENANT_SECRET_DENIAL_NOT_TESTED"))
    return UnifiedReadiness(
        region=base.region,root_running=base.root_running,
        staging_running=base.staging_running,staging_provisioning=base.staging_provisioning,
        staging_active_vaults=base.staging_active_vaults,
        active_dynamic_groups=iam.root_dynamic_groups_active,
        project_named_groups=iam.project_named_dynamic_groups_active,
        candidate_secret_bundle_statements=iam.candidate_secret_bundle_statements,
        blockers=tuple(dict.fromkeys(blockers)),
    )

def format_unified_report(report:UnifiedReadiness)->tuple[str,...]:
    if not isinstance(report,UnifiedReadiness):
        raise UnifiedReadinessBlocked("OCI_UNIFIED_REPORT_INVALID")
    if (report.region!="sa-saopaulo-1"
            or any(not isinstance(v,str) or not v.startswith("OCI_") or
                   not v.replace("_","").isalnum() for v in report.blockers)):
        raise UnifiedReadinessBlocked("OCI_UNIFIED_REPORT_INVALID")
    lines=[
        "=== FR FINANCE M37360 OCI UNIFIED READ ONLY ===",
        "M37360_STATUS=READ_ONLY_PASS",
        "OCI_REGION="+report.region,
        "OCI_ROOT_VM_RUNNING="+str(report.root_running),
        "OCI_STAGING_VM_RUNNING="+str(report.staging_running),
        "OCI_STAGING_VM_PROVISIONING="+str(report.staging_provisioning),
        "OCI_STAGING_ACTIVE_VAULTS="+str(report.staging_active_vaults),
        "OCI_ACTIVE_DYNAMIC_GROUPS="+str(report.active_dynamic_groups),
        "OCI_PROJECT_NAMED_DYNAMIC_GROUPS="+str(report.project_named_groups),
        "OCI_SECRET_POLICY_CANDIDATES="+str(report.candidate_secret_bundle_statements),
        "OCI_BLOCKER_COUNT="+str(len(report.blockers)),
    ]
    lines.extend("OCI_BLOCKER="+v for v in report.blockers)
    lines.extend((
        "OCI_IAM_EFFECTIVE_PERMISSIONS=NOT_ATTESTED",
        "OCI_INSTANCE_PRINCIPAL=NOT_AUTHENTICATED",
        "OCI_SECRET_VALUES_READ=NO",
        "OCI_RESOURCE_CREATED=NO",
        "OCI_DEPLOYMENT_AUTHORIZED=NO",
        "OCI_PAID_UPGRADE=NOT_REQUESTED",
        "POSTGRESQL_LOCAL_MODIFIED=NO",
        "MERCADO_PAGO_REAL=OFF",
        "PIX_REAL=OFF",
        "REAL_USER_ACTIVATION=OFF",
    ))
    return tuple(lines)
