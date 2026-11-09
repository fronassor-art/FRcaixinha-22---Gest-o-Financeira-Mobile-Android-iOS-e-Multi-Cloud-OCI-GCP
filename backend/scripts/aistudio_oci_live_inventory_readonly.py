#!/usr/bin/env python3
"""M37300: actual OCI API *read-only* inventory, no cloud mutation.

Run under the same Debian/Termux environment where OCI CLI is configured.
No OCIDs, tokens, keys, public IPs, raw JSON or error payloads are printed.
"""
from __future__ import annotations
import configparser
import json
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.oci_staging_live_inventory import (
    TARGET_REGION,OCIInventoryBlocked,inspect_live_oci_inventory,
)

MAX_OUTPUT=2_000_000
MAX_SECONDS=30


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise OCIInventoryBlocked("OCI_AMBIGUOUS_JSON")
        result[key]=value
    return result


def _no_nonfinite(_):
    raise OCIInventoryBlocked("OCI_INVALID_JSON")


def read_cli_identity():
    path=Path(os.environ.get("OCI_CLI_CONFIG_FILE","~/.oci/config")).expanduser()
    profile=os.environ.get("OCI_CLI_PROFILE","DEFAULT")
    if re.fullmatch(r"[A-Za-z0-9_-]{1,64}",profile or "") is None or not path.is_file():
        raise OCIInventoryBlocked("OCI_CLI_CONFIG_UNAVAILABLE")
    cfg=configparser.RawConfigParser()
    try:
        cfg.read(path,encoding="utf-8")
        tenancy=cfg.get(profile,"tenancy")
        region=cfg.get(profile,"region")
    except (OSError,configparser.Error,ValueError):
        raise OCIInventoryBlocked("OCI_CLI_CONFIG_UNAVAILABLE") from None
    return tenancy,region


def _sdk_compute_list(command:tuple[str,...]):
    """Read OCI ListInstances using typed SDK responses, never CLI stdout.

    OCI CLI 3.96 in Debian returned exit code 0 with EMPTY stdout for
    compute instance list in BOTH compartments. Do not infer zero instances
    from that ambiguous transport. The SDK requires HTTP 200 + typed list.
    """
    if (len(command)!=6 or command[:3]!=("compute","instance","list")
            or command[3]!="--compartment-id" or command[5]!="--all"):
        raise OCIInventoryBlocked("OCI_COMMAND_NOT_READ_ONLY")
    compartment=command[4]
    if (type(compartment) is not str
            or not compartment.startswith(("ocid1.tenancy.oc1.",
                                            "ocid1.compartment.oc1."))):
        raise OCIInventoryBlocked("OCI_COMPUTE_SCOPE_INVALID")
    try:
        import oci
        cfg=oci.config.from_file(
            file_location=str(Path(os.environ.get(
                "OCI_CLI_CONFIG_FILE","~/.oci/config")).expanduser()),
            profile_name=os.environ.get("OCI_CLI_PROFILE","DEFAULT"),
        )
        if cfg.get("region")!=TARGET_REGION:
            raise OCIInventoryBlocked("OCI_TENANCY_OR_REGION_DENIED")
        client=oci.core.ComputeClient(
            cfg,timeout=(5,30),retry_strategy=oci.retry.NoneRetryStrategy(),
        )
        results=[]
        page=None
        visited_pages=set()
        for _ in range(100):
            opts={"limit":100,"retry_strategy":oci.retry.NoneRetryStrategy()}
            if page is not None:
                opts["page"]=page
            response=client.list_instances(compartment,**opts)
            if (type(response.status) is not int or response.status!=200
                    or type(response.data) is not list
                    or len(response.data)>100):
                raise OCIInventoryBlocked("OCI_COMPUTE_SDK_RESPONSE_INVALID")
            for instance in response.data:
                iid=getattr(instance,"id",None)
                state=getattr(instance,"lifecycle_state",None)
                if (type(iid) is not str or type(state) is not str):
                    raise OCIInventoryBlocked("OCI_COMPUTE_SDK_RESPONSE_INVALID")
                results.append({"id":iid,"lifecycle-state":state})
            page=response.next_page
            if page is None:
                return {"data":results}
            if (type(page) is not str or not page or len(page)>2048
                    or page in visited_pages):
                raise OCIInventoryBlocked("OCI_COMPUTE_PAGINATION_INVALID")
            visited_pages.add(page)
        raise OCIInventoryBlocked("OCI_COMPUTE_PAGINATION_LIMIT")
    except OCIInventoryBlocked:
        raise
    except Exception:
        # Deliberately withhold potentially sensitive provider/client errors.
        raise OCIInventoryBlocked("OCI_COMPUTE_SDK_READ_FAILED") from None


def _run(command:tuple[str,...]):
    if command[:3]==("compute","instance","list"):
        return _sdk_compute_list(command)
    if shutil.which("oci") is None:
        raise OCIInventoryBlocked("OCI_CLI_NOT_INSTALLED")
    # Explicit allowlist enforcement also lives in the inspection module.
    # Never echo the command: it contains the tenancy's public OCID.
    try:
        flags=["--profile",os.environ.get("OCI_CLI_PROFILE","DEFAULT")]
        if os.environ.get("OCI_CLI_CONFIG_FILE"):
            flags.extend(("--config-file",str(Path(os.environ["OCI_CLI_CONFIG_FILE"]).expanduser())))
        completed=subprocess.run(
            ["oci",*command,"--region",TARGET_REGION,"--output","json","--no-retry",*flags],
            capture_output=True,check=False,timeout=MAX_SECONDS,
        )
        if completed.returncode!=0 or not 0<len(completed.stdout)<=MAX_OUTPUT:
            raise OCIInventoryBlocked("OCI_REMOTE_READ_FAILED")
        return json.loads(completed.stdout,object_pairs_hook=_unique,
                          parse_constant=_no_nonfinite)
    except OCIInventoryBlocked:
        raise
    except (OSError,subprocess.SubprocessError,UnicodeError,ValueError,TypeError):
        raise OCIInventoryBlocked("OCI_REMOTE_READ_FAILED") from None


def main()->int:
    print("=== FR FINANCE OCI M37300 LIVE READ ONLY ===")
    try:
        tenancy,region=read_cli_identity()
        result=inspect_live_oci_inventory(
            tenancy_id=tenancy,region=region,query=_run,
        )
    except OCIInventoryBlocked as exc:
        print("OCI_M37300_LIVE_INVENTORY=BLOCKED")
        print("OCI_CAUSE="+str(exc))
        print("OCI_RESOURCE_CREATED=NO")
        print("OCI_PRODUCTION_AUTHORIZATION=NOT_GRANTED")
        print("PIX_REAL=OFF")
        return 2
    print("OCI_M37300_LIVE_INVENTORY=READ_ONLY_PASS")
    print("OCI_REGION="+result.region)
    print("OCI_HOME_REGION=CONFIRMED")
    print("OCI_STAGING_COMPARTMENT="+result.staging_compartment)
    print("OCI_ROOT_VCN="+result.root_vcn)
    print("OCI_ROOT_SUBNET="+result.root_subnet)
    print("OCI_ROOT_VM_RUNNING="+str(result.root_instances_running))
    print("OCI_COMPUTE_SOURCE=SDK_HTTP_200_TYPED_LIST")
    print("OCI_STAGING_VM_RUNNING="+str(result.staging_instances_running))
    print("OCI_STAGING_VM_PROVISIONING="+str(result.staging_instances_provisioning))
    print("OCI_STAGING_VAULT_ACTIVE="+str(result.staging_vaults_active))
    print("OCI_PUBLIC_HTTPS=NOT_VERIFIED")
    print("OCI_DB_TLS_RLS=NOT_VERIFIED")
    print("OCI_BACKUP_RESTORE=NOT_VERIFIED")
    print("OCI_DEPLOYMENT_AUTHORIZED=NO")
    print("OCI_RESOURCE_CREATED=NO")
    print("OCI_PAID_UPGRADE=NOT_REQUESTED")
    print("PIX_REAL=OFF")
    print("ACTIVATION_REAL=OFF")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
