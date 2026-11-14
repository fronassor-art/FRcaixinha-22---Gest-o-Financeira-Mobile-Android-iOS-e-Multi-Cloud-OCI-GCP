#!/usr/bin/env python3
"""M37322: single authorized OCI read-only report, NEVER deployment.

Use the OCI SDK environment in Debian PRoot. A PASS means cloud reads
were authenticated and parsed; it is NOT approval to deploy the backend.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))

from app.oci_staging_live_inventory import OCIInventoryBlocked,inspect_live_oci_inventory
from app.oci_existing_network_audit import NetworkAuditBlocked,inspect_existing_root_network
from app.oci_staging_operational_readiness import (
    ReleaseReadinessBlocked,assess_staging_readiness,
)
from aistudio_oci_live_inventory_readonly import read_cli_identity,_run
from aistudio_oci_existing_network_readonly import _sdk_query


def main()->int:
    print("=== FR FINANCE OCI M37322 READ ONLY OPERATIONAL GATES ===")
    try:
        import oci
        tenancy,region=read_cli_identity()
        inventory=inspect_live_oci_inventory(
            tenancy_id=tenancy,region=region,query=_run,
        )
        cfg=oci.config.from_file(
            file_location=str(Path(os.environ.get(
                "OCI_CLI_CONFIG_FILE","~/.oci/config")).expanduser()),
            profile_name=os.environ.get("OCI_CLI_PROFILE","DEFAULT"),
        )
        if cfg.get("tenancy")!=tenancy or cfg.get("region")!=region:
            raise ReleaseReadinessBlocked("OCI_PROFILE_MISMATCH")
        client=oci.core.VirtualNetworkClient(
            cfg,timeout=(5,30),retry_strategy=oci.retry.NoneRetryStrategy(),
        )
        network=inspect_existing_root_network(
            tenancy_id=tenancy,region=region,
            query=lambda cmd:_sdk_query(client,oci,cmd),
        )
        report=assess_staging_readiness(inventory,network)
    except (OCIInventoryBlocked,NetworkAuditBlocked,ReleaseReadinessBlocked) as exc:
        # Fixed, redacted reasons from local contract, never OCI provider errors.
        print("OCI_M37322_STATUS=BLOCKED")
        print("OCI_CAUSE="+str(exc))
        print("OCI_RESOURCE_CREATED=NO")
        print("OCI_PAID_UPGRADE=NOT_REQUESTED")
        print("OCI_DEPLOYMENT_AUTHORIZED=NO")
        print("PIX_REAL=OFF")
        return 2
    except Exception:
        print("OCI_M37322_STATUS=BLOCKED")
        print("OCI_CAUSE=OCI_RUNTIME_READ_OR_SDK_FAILED")
        print("OCI_RESOURCE_CREATED=NO")
        print("OCI_DEPLOYMENT_AUTHORIZED=NO")
        print("PIX_REAL=OFF")
        return 2

    print("OCI_M37322_STATUS=READ_ONLY_PASS")
    print("OCI_REGION="+report.region)
    print("OCI_NETWORK_STATE="+network.state)
    print("OCI_ROOT_VM_RUNNING="+str(report.root_running))
    print("OCI_STAGING_VM_RUNNING="+str(report.staging_running))
    print("OCI_STAGING_VM_PROVISIONING="+str(report.staging_provisioning))
    print("OCI_STAGING_ACTIVE_VAULT="+str(report.staging_active_vaults))
    print("OCI_NETWORK_PUBLIC_IP_ALLOWED="+str(network.subnet_allows_public_ip).upper())
    print("OCI_IGW_AND_ROUTE="+str(
        network.internet_gateway_enabled and network.default_ipv4_route_to_igw
    ).upper())
    print("OCI_PUBLIC_TCP_443_RULE="+str(network.public_tcp_443_rule_present).upper())
    print("OCI_PUBLIC_SSH_OR_DB_EXPOSURE="+str(
        network.public_tcp_22_rule_present or network.public_db_port_exposure
    ).upper())
    print("OCI_BLOCKER_COUNT="+str(len(report.blockers)))
    for blocker in report.blockers:
        print("OCI_BLOCKER="+blocker)
    print("OCI_RESOURCE_CREATED=NO")
    print("OCI_PAID_UPGRADE=NOT_REQUESTED")
    print("OCI_DEPLOYMENT_AUTHORIZED=NO")
    print("OCI_REAL_USERS=OFF")
    print("PIX_REAL=OFF")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
