"""FR Finance M37331-M37340 — OCI IAM evidence, READ ONLY.

Counts IAM configuration candidates, never attests effective secret access,
instance-principal authentication or authorizes live services. No credentials,
policy statements, group names, matching rules or OCIDs in result.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

TARGET_REGION="sa-saopaulo-1"
TARGET_COMPARTMENT="fr-finance-staging"
_PROJECT_NAME=re.compile(r"fr[-_]?finance", re.IGNORECASE)
_CANDIDATE_STATEMENT=re.compile(
    r"allow\s+dynamic-group\s+[A-Za-z0-9_.-]+\s+to\s+read\s+"
    r"secret-bundles\s+in\s+compartment\s+fr-finance-staging",
    flags=re.IGNORECASE,
)


class IAMReadOnlyBlocked(ValueError):
    """Fixed codes only: never include raw provider responses or identities."""


@dataclass(frozen=True)
class IAMReadOnlySummary:
    region: str
    staging_compartment: str
    root_dynamic_groups_active: int
    project_named_dynamic_groups_active: int
    root_policies_active: int
    staging_policies_active: int
    candidate_secret_bundle_statements: int
    overly_broad_secret_grants_manual_review: bool
    inspection_only: bool = True
    workload_instance_principal_verified: bool = False
    policy_effective_permissions_verified: bool = False
    tenant_secret_isolation_verified: bool = False
    vault_present_verified: bool = False
    real_secret_access_tested: bool = False
    cloud_mutations_performed: bool = False
    deployment_authorized: bool = False
    real_users_authorized: bool = False
    pix_real_authorized: bool = False


def _ensure_rows(query:Callable, target:str, compartment:str) -> list[dict]:
    if target not in ("compartment","dynamic-group","policy-root","policy-staging"):
        raise IAMReadOnlyBlocked("OCI_IAM_UNLISTED_OPERATION")
    try:
        result=query(target, compartment)
    except IAMReadOnlyBlocked:
        raise
    except Exception:
        raise IAMReadOnlyBlocked("OCI_IAM_REMOTE_READ_FAILED") from None
    if (type(result) is not list or len(result)>2000
            or any(type(item) is not dict for item in result)):
        raise IAMReadOnlyBlocked("OCI_IAM_SCHEMA_INVALID")
    return result


def _id(value:object, resource:str)->bool:
    return (type(value) is str and
            value.startswith("ocid1."+resource+".oc1.") and
            18 < len(value) < 360 and
            all(ch.isalnum() or ch in ".-_" for ch in value))


def inspect_iam_readonly(tenancy_id:str,region:str,query:Callable)->IAMReadOnlySummary:
    if region!=TARGET_REGION or not _id(tenancy_id,"tenancy"):
        raise IAMReadOnlyBlocked("OCI_IAM_REGION_OR_TENANCY_DENIED")

    compartments=_ensure_rows(query,"compartment",tenancy_id)
    matches=[c for c in compartments
             if c.get("name")==TARGET_COMPARTMENT and
                c.get("lifecycle-state")=="ACTIVE"]
    if len(matches)!=1 or not _id(matches[0].get("id"),"compartment"):
        raise IAMReadOnlyBlocked("OCI_IAM_STAGING_COMPARTMENT_NOT_UNIQUE")
    staging=matches[0]["id"]

    groups=_ensure_rows(query,"dynamic-group",tenancy_id)
    policies_root=_ensure_rows(query,"policy-root",tenancy_id)
    policies_stage=_ensure_rows(query,"policy-staging",staging)

    for group in groups:
        if (not _id(group.get("id"),"dynamicgroup") or
                group.get("lifecycle-state") not in ("ACTIVE","INACTIVE","CREATING","DELETING","DELETED") or
                type(group.get("name")) is not str or
                type(group.get("matching-rule")) is not str):
            raise IAMReadOnlyBlocked("OCI_IAM_SCHEMA_INVALID")

    def count_and_scan(policies:list[dict], scope:str):
        active=0
        candidates=0
        broad=False
        for policy in policies:
            if (not _id(policy.get("id"),"policy") or
                    policy.get("compartment-id")!=scope or
                    policy.get("lifecycle-state") not in ("ACTIVE","INACTIVE","CREATING","DELETING","DELETED") or
                    type(policy.get("name")) is not str or
                    type(policy.get("statements")) is not list or
                    len(policy["statements"])>100 or
                    any(type(s) is not str or not 0<len(s)<2048
                        for s in policy["statements"])):
                raise IAMReadOnlyBlocked("OCI_IAM_SCHEMA_INVALID")
            if policy["lifecycle-state"]!="ACTIVE":
                continue
            active+=1
            for statement in policy["statements"]:
                cleaned=" ".join(statement.strip().split())
                if _CANDIDATE_STATEMENT.fullmatch(cleaned):
                    candidates+=1
                # Conservative warning only; absence doesn't prove safe IAM.
                if (re.search(r"\ballow\s+(?:any-user|any-group|dynamic-group)\b",
                              cleaned,re.I) and
                        re.search(r"\b(?:manage|use)\s+(?:all-resources|secret-family)\b",
                                  cleaned,re.I) and
                        re.search(r"\bin\s+tenancy\b",cleaned,re.I)):
                    broad=True
        return active,candidates,broad

    root_active,root_candidates,root_broad=count_and_scan(policies_root,tenancy_id)
    staging_active,staging_candidates,staging_broad=count_and_scan(policies_stage,staging)
    active_groups=[g for g in groups if g["lifecycle-state"]=="ACTIVE"]
    return IAMReadOnlySummary(
        region=region,staging_compartment="ACTIVE",
        root_dynamic_groups_active=len(active_groups),
        project_named_dynamic_groups_active=sum(
            _PROJECT_NAME.search(g["name"]) is not None for g in active_groups),
        root_policies_active=root_active,
        staging_policies_active=staging_active,
        candidate_secret_bundle_statements=root_candidates+staging_candidates,
        overly_broad_secret_grants_manual_review=root_broad or staging_broad,
    )
