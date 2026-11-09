#!/usr/bin/env python3
"""M37300: actual OCI API *read-only* inventory, no cloud mutation.

Run under the same Debian/Termux environment where OCI CLI is configured.
No OCIDs, tokens, keys, public IPs, raw JSON or error payloads are printed.
"""
from __future__ import annotations
import configparser
import json
import os
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
    if not profile or not profile.isalnum() or not path.is_file():
        raise OCIInventoryBlocked("OCI_CLI_CONFIG_UNAVAILABLE")
    cfg=configparser.RawConfigParser()
    try:
        cfg.read(path,encoding="utf-8")
        tenancy=cfg.get(profile,"tenancy")
        region=cfg.get(profile,"region")
    except (OSError,configparser.Error,ValueError):
        raise OCIInventoryBlocked("OCI_CLI_CONFIG_UNAVAILABLE") from None
    return tenancy,region


def _run(command:tuple[str,...]):
    if shutil.which("oci") is None:
        raise OCIInventoryBlocked("OCI_CLI_NOT_INSTALLED")
    # Explicit allowlist enforcement also lives in the inspection module.
    # Never echo the command: it contains the tenancy's public OCID.
    try:
        completed=subprocess.run(
            ["oci",*command,"--region",TARGET_REGION,"--output","json","--no-retry"],
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
