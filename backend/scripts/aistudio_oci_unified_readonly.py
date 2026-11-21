#!/usr/bin/env python3
"""M37360: join live OCI inventory, network and IAM READ ONLY; no mutations."""
import os
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))
from app.oci_staging_live_inventory import OCIInventoryBlocked,inspect_live_oci_inventory
from app.oci_existing_network_audit import NetworkAuditBlocked,inspect_existing_root_network
from app.oci_iam_readiness_readonly import IAMReadOnlyBlocked,inspect_iam_readonly
from app.oci_unified_readiness_readonly import UnifiedReadinessBlocked,assess_unified_readonly,format_unified_report
from aistudio_oci_live_inventory_readonly import read_cli_identity,_run
from aistudio_oci_existing_network_readonly import _sdk_query
from aistudio_oci_iam_readonly import _query

def main()->int:
    try:
        import oci
        tenancy,region=read_cli_identity()
        config=oci.config.from_file(
            file_location=str(Path(os.environ.get("OCI_CLI_CONFIG_FILE","~/.oci/config")).expanduser()),
            profile_name=os.environ.get("OCI_CLI_PROFILE","DEFAULT"),
        )
        if config.get("tenancy")!=tenancy or config.get("region")!=region:
            raise UnifiedReadinessBlocked("OCI_UNIFIED_PROFILE_MISMATCH")
        inventory=inspect_live_oci_inventory(tenancy_id=tenancy,region=region,query=_run)
        network_client=oci.core.VirtualNetworkClient(
            config,timeout=(5,30),retry_strategy=oci.retry.NoneRetryStrategy())
        network=inspect_existing_root_network(
            tenancy_id=tenancy,region=region,
            query=lambda cmd:_sdk_query(network_client,oci,cmd))
        identity_client=oci.identity.IdentityClient(
            config,timeout=(5,30),retry_strategy=oci.retry.NoneRetryStrategy())
        iam=inspect_iam_readonly(
            tenancy_id=tenancy,region=region,
            query=lambda target,scope:_query(identity_client,oci,target,scope))
        report=assess_unified_readonly(inventory,network,iam)
    except (OCIInventoryBlocked,NetworkAuditBlocked,IAMReadOnlyBlocked,UnifiedReadinessBlocked) as exc:
        print("M37360_STATUS=BLOCKED")
        print("M37360_CAUSE="+str(exc))
        print("OCI_RESOURCE_CREATED=NO")
        print("OCI_DEPLOYMENT_AUTHORIZED=NO")
        print("PIX_REAL=OFF")
        return 2
    except Exception:
        print("M37360_STATUS=BLOCKED")
        print("M37360_CAUSE=OCI_UNIFIED_REMOTE_READ_FAILED")
        print("OCI_RESOURCE_CREATED=NO")
        print("OCI_DEPLOYMENT_AUTHORIZED=NO")
        print("PIX_REAL=OFF")
        return 2
    for line in format_unified_report(report):
        print(line)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
