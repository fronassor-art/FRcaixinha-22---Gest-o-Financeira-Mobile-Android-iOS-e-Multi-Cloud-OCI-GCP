#!/usr/bin/env python3
"""FR Finance M37340 — OCI IAM policy & dynamic-group inventory, READ ONLY.

Operates with the local operator's configured OCI SDK profile in Debian.
Does not attempt InstancePrincipal authentication or access to Vault secrets.
Only fixed labels/counts are printed; never policy bodies/OCIDs/credentials.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.oci_iam_readiness_readonly import (
    IAMReadOnlyBlocked,inspect_iam_readonly,TARGET_REGION,
)

_PAGE_LIMIT=100
_MAX_PAGES=30


def _to_minimal(target:str, object_:object) -> dict:
    if target=="compartment":
        fields=("id","name","lifecycle_state")
    elif target=="dynamic-group":
        fields=("id","name","lifecycle_state","matching_rule")
    else:
        fields=("id","name","lifecycle_state","compartment_id","statements")
    data={key.replace("_","-"):getattr(object_,key,None) for key in fields}
    if target in ("policy-root","policy-staging"):
        stmts=data.get("statements")
        if type(stmts) is list:
            data["statements"]=list(stmts)
    return data


def _query(sdk,oci,target:str,compartment_id:str)->list[dict]:
    methods={
        "compartment":"list_compartments",
        "dynamic-group":"list_dynamic_groups",
        "policy-root":"list_policies",
        "policy-staging":"list_policies",
    }
    if target not in methods:
        raise IAMReadOnlyBlocked("OCI_IAM_UNLISTED_OPERATION")
    method=getattr(sdk,methods[target])
    result=[]
    page=None
    pages_seen=set()
    for _ in range(_MAX_PAGES):
        kwargs={
            "limit":_PAGE_LIMIT,
            "retry_strategy":oci.retry.NoneRetryStrategy(),
        }
        if page is not None:
            kwargs["page"]=page
        try:
            response=method(compartment_id,**kwargs)
        except Exception:
            raise IAMReadOnlyBlocked("OCI_IAM_REMOTE_READ_FAILED") from None
        if (type(response.status) is not int or response.status!=200
                or type(response.data) is not list
                or len(response.data)>_PAGE_LIMIT):
            raise IAMReadOnlyBlocked("OCI_IAM_RESPONSE_INVALID")
        result.extend(_to_minimal(target,resource) for resource in response.data)
        if len(result)>2000:
            raise IAMReadOnlyBlocked("OCI_IAM_TOO_MANY_RESOURCES")
        page=response.next_page
        if page is None:
            return result
        if (type(page) is not str or not page or len(page)>2048
                or page in pages_seen):
            raise IAMReadOnlyBlocked("OCI_IAM_PAGINATION_INVALID")
        pages_seen.add(page)
    raise IAMReadOnlyBlocked("OCI_IAM_PAGINATION_LIMIT")


def main()->int:
    print("=== FR FINANCE M37340 IAM REAL READ ONLY ===")
    try:
        import oci
        profile=os.environ.get("OCI_CLI_PROFILE","DEFAULT")
        config_file=Path(os.environ.get(
            "OCI_CLI_CONFIG_FILE","~/.oci/config")).expanduser()
        config=oci.config.from_file(
            file_location=str(config_file),profile_name=profile,
        )
        tenancy=config.get("tenancy")
        if config.get("region")!=TARGET_REGION or type(tenancy) is not str:
            raise IAMReadOnlyBlocked("OCI_IAM_PROFILE_OR_REGION_INVALID")
        client=oci.identity.IdentityClient(
            config,timeout=(5,30),
            retry_strategy=oci.retry.NoneRetryStrategy(),
        )
        report=inspect_iam_readonly(
            tenancy_id=tenancy,region=config["region"],
            query=lambda target,scope:_query(client,oci,target,scope),
        )
    except IAMReadOnlyBlocked as exc:
        print("M37340_IAM=BLOCKED")
        print("M37340_CAUSE="+str(exc))
        print("OCI_RESOURCE_CREATED=NO")
        print("OCI_DEPLOYMENT_AUTHORIZED=NO")
        print("PIX_REAL=OFF")
        return 2
    except Exception:
        print("M37340_IAM=BLOCKED")
        print("M37340_CAUSE=OCI_IAM_CLIENT_UNAVAILABLE")
        print("OCI_RESOURCE_CREATED=NO")
        print("OCI_DEPLOYMENT_AUTHORIZED=NO")
        print("PIX_REAL=OFF")
        return 2

    print("M37340_IAM=READ_ONLY_PASS")
    print("OCI_REGION="+report.region)
    print("OCI_STAGING_COMPARTMENT="+report.staging_compartment)
    print("OCI_ROOT_DYNAMIC_GROUPS_ACTIVE="+str(report.root_dynamic_groups_active))
    print("OCI_PROJECT_NAMED_DYNAMIC_GROUPS_ACTIVE="+
          str(report.project_named_dynamic_groups_active))
    print("OCI_ROOT_POLICIES_ACTIVE="+str(report.root_policies_active))
    print("OCI_STAGING_POLICIES_ACTIVE="+str(report.staging_policies_active))
    print("OCI_CANDIDATE_SECRET_BUNDLE_STATEMENTS="+
          str(report.candidate_secret_bundle_statements))
    print("OCI_POSSIBLE_BROAD_POLICY_MANUAL_REVIEW="+
          str(report.overly_broad_secret_grants_manual_review).upper())
    print("OCI_DYNAMIC_GROUP_MEMBERSHIP_ATTESTED=NO")
    print("OCI_EFFECTIVE_IAM_PERMISSIONS_ATTESTED=NO")
    print("OCI_INSTANCE_PRINCIPAL_AUTHENTICATED=NO")
    print("OCI_SECRET_VALUES_READ=NO")
    print("OCI_VAULT_EXISTS=NOT_ATTESTED_BY_IAM")
    print("OCI_RESOURCE_CREATED=NO")
    print("OCI_CONFIG_CHANGED=NO")
    print("OCI_PAID_UPGRADE=NOT_REQUESTED")
    print("OCI_DEPLOYMENT_AUTHORIZED=NO")
    print("REAL_USER_ACTIVATION=OFF")
    print("PIX_REAL=OFF")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
