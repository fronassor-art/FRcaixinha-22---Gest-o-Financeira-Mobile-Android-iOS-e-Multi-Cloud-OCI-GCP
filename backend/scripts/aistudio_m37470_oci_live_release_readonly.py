#!/usr/bin/env python3
"""M37470 — authenticated OCI live READ-ONLY status + release gate crosscheck.

Run in Debian PRoot/Termux with preconfigured OCI SDK and OCI CLI. No OCI
create/update/delete/launch; no resource IDs, tokens or policy text output.
A successful cloud read is NOT consent to deploy, pay, activate or use Pix.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(ROOT/"backend"))

from app.oci_staging_live_inventory import OCIInventoryBlocked,inspect_live_oci_inventory
from app.oci_existing_network_audit import NetworkAuditBlocked,inspect_existing_root_network
from app.oci_iam_readiness_readonly import IAMReadOnlyBlocked,inspect_iam_readonly
from app.oci_live_release_bridge_m37470 import (
    OCIRealEvidenceBlocked,correlate_readonly_oci,
    attach_oci_observation_to_release,
)
from app.saas_operational_blockers_m37469 import build_operational_blocker_report
from aistudio_oci_live_inventory_readonly import read_cli_identity,_run
from aistudio_oci_existing_network_readonly import _sdk_query
from aistudio_oci_iam_readonly import _query


def read_only_oci_observation():
    """All provider operations delegated to M37300/M37316/M37340 allowlists."""
    import oci
    tenancy,region=read_cli_identity()
    cfg=oci.config.from_file(
        file_location=str(Path(os.environ.get(
            "OCI_CLI_CONFIG_FILE","~/.oci/config")).expanduser()),
        profile_name=os.environ.get("OCI_CLI_PROFILE","DEFAULT"),
    )
    if cfg.get("tenancy")!=tenancy or cfg.get("region")!=region:
        raise OCIRealEvidenceBlocked("M37470_OCI_PROFILE_MISMATCH")
    inventory=inspect_live_oci_inventory(
        tenancy_id=tenancy,region=region,query=_run,
    )
    network_client=oci.core.VirtualNetworkClient(
        cfg,timeout=(5,30),retry_strategy=oci.retry.NoneRetryStrategy(),
    )
    network=inspect_existing_root_network(
        tenancy_id=tenancy,region=region,
        query=lambda command:_sdk_query(network_client,oci,command),
    )
    iam_client=oci.identity.IdentityClient(
        cfg,timeout=(5,30),retry_strategy=oci.retry.NoneRetryStrategy(),
    )
    iam=inspect_iam_readonly(
        tenancy_id=tenancy,region=region,
        query=lambda target,scope:_query(iam_client,oci,target,scope),
    )
    return correlate_readonly_oci(inventory,network,iam)


def main(argv:list[str]|None=None)->int:
    parser=argparse.ArgumentParser(
        description="FR Finance M37470 — inventário OCI autenticado, somente leitura"
    )
    parser.add_argument(
        "action",choices=("offline","live","json"),
        nargs="?",default="offline",
    )
    args=parser.parse_args(argv)
    try:
        base=build_operational_blocker_report(root=ROOT,env=os.environ)
        if args.action=="offline":
            print("=== FR FINANCE M37470 — OCI OFFLINE BASELINE ===")
            print("M37470_MODE=NO_CLOUD_ACCESS")
            print("M37470_CI_PACKAGES="+str(base["ci_source_packages_present"])
                  +"/"+str(base["ci_package_count"]))
            print("M37470_LIVE_GATES_VERIFIED=0/20")
            print("M37470_PROVIDER_GATES_VERIFIED=0/7")
            print("M37470_OCI_VM=NOT_QUERIED")
            print("M37470_PRODUCTION_RELEASE=BLOCKED")
            print("M37470_OFFLINE_REPORT=PASS")
            print("M37470_ORIGINAL_POSTGRES_UNTOUCHED=YES")
            return 0

        observation=read_only_oci_observation()
        combined=attach_oci_observation_to_release(base,observation)
    except (OCIInventoryBlocked,NetworkAuditBlocked,
            IAMReadOnlyBlocked,OCIRealEvidenceBlocked):
        print("M37470_OCI_READONLY=BLOCKED_INCOMPLETE_OR_UNTRUSTED_EVIDENCE")
        print("M37470_CLOUD_RESOURCE_CREATED=NO")
        print("M37470_REAL_ACTIVATION_AUTHORIZED=NO")
        print("M37470_PIX_REAL=OFF")
        return 2
    except Exception:
        # OCI SDK error may include OCIDs, account details or credentials.
        print("M37470_OCI_READONLY=BLOCKED_RUNTIME_OR_REMOTE_READ")
        print("M37470_CLOUD_RESOURCE_CREATED=NO")
        print("M37470_REAL_ACTIVATION_AUTHORIZED=NO")
        print("M37470_PIX_REAL=OFF")
        return 2

    if args.action=="json":
        print(json.dumps(
            combined,ensure_ascii=False,sort_keys=True,indent=2,
        ))
        return 0
    x=combined["oci_observed"]
    print("=== FR FINANCE M37470 — OCI LIVE READ ONLY ===")
    print("M37470_OCI_READONLY=PASS")
    print("M37470_REGION="+x["region"])
    print("M37470_VM_STAGING="+x["vm_lifecycle"])
    print("M37470_VM_RUNNING_COUNT="+str(x["staging_running"]))
    print("M37470_VM_PROVISIONING_COUNT="+str(x["staging_provisioning"]))
    print("M37470_ROOT_RUNNING_COUNT="+str(x["root_running"]))
    print("M37470_ACTIVE_VAULT_COUNT="+str(x["staging_active_vaults"]))
    print("M37470_NETWORK_STATUS="+x["network_status"])
    print("M37470_IGW_ROUTE_OBSERVED="+str(x["internet_route_configured"]).upper())
    print("M37470_HTTPS_443_RULE_OBSERVED="+str(x["tcp_443_rule_present"]).upper())
    print("M37470_PUBLIC_SSH_REVIEW="+str(x["public_tcp_22_review"]).upper())
    print("M37470_PUBLIC_DB_REVIEW="+str(x["public_database_port_review"]).upper())
    print("M37470_IAM_PROJECT_GROUPS="+str(x["project_dynamic_groups_count"]))
    print("M37470_HTTPS_REAL=NOT_VERIFIED")
    print("M37470_DATABASE_TLS_RLS=NOT_VERIFIED")
    print("M37470_INSTANCE_PRINCIPAL=NOT_VERIFIED")
    print("M37470_BACKUP_RESTORE=NOT_VERIFIED")
    print("M37470_REAL_USER_CONSENT=NOT_VERIFIED")
    print("M37470_PROVIDER_PAYMENTS=NOT_VERIFIED")
    print("M37470_LIVE_GATES_VERIFIED=0/20")
    print("M37470_PROVIDER_GATES_VERIFIED=0/7")
    print("M37470_PRODUCTION_RELEASE=BLOCKED")
    print("M37470_DEPLOYMENT_AUTHORIZED=NO")
    print("M37470_CLOUD_RESOURCE_CREATED=NO")
    print("M37470_PAID_UPGRADE=NOT_REQUESTED")
    print("M37470_REAL_ACTIVATION_AUTHORIZED=NO")
    print("M37470_PIX_REAL=OFF")
    print("M37470_ORIGINAL_POSTGRES_UNTOUCHED=YES")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
