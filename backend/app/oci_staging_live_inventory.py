"""FR Finance AI Studio M36900-M37300: read-only OCI staging inventory.

Queries the actual Oracle CLI, but NEVER provisions resources, extracts
secrets, uses a paid upgrade, changes firewall, deploys code or applies SQL.
The sanitized output cannot be used as an operational release approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping
import re

TARGET_REGION = "sa-saopaulo-1"
TARGET_COMPARTMENT = "fr-finance-staging"
TARGET_VCN = "FR Finance"
TARGET_SUBNET = "FR Finance"
_OCID = re.compile(r"ocid1\.(?:tenancy|compartment|vcn|instance)\.oc1\.(?:\.[a-z0-9]{8,256}|[a-z0-9-]+\.[a-z0-9]{8,256})\Z")
SAFE_QUERY_GROUPS = frozenset((
    ("iam","region-subscription","list"),
    ("iam","compartment","list"),
    ("compute","instance","list"),
    ("network","vcn","list"),
    ("network","subnet","list"),
    ("kms","management","vault","list"),
))


class OCIInventoryBlocked(Exception):
    """Never include the raw API payload, account IDs or provider errors."""


@dataclass(frozen=True)
class OCIInventorySummary:
    region: str
    home_region_observed: bool
    staging_compartment: str
    root_vcn: str
    root_subnet: str
    staging_instances_running: int
    staging_instances_provisioning: int
    staging_vaults_active: int
    staging_vm_present: bool
    observations_from_live_api: bool
    deployment_authorized: bool = False
    api_public_https_verified: bool = False
    database_tls_rls_verified: bool = False
    backups_restored_verified: bool = False
    paid_upgrade_authorized: bool = False
    real_users_authorized: bool = False
    real_pix_authorized: bool = False


def _ocid(value: object, resource: str) -> bool:
    return type(value) is str and value.startswith("ocid1."+resource+".oc1.") and _OCID.fullmatch(value) is not None


def _data(response: object) -> list[dict]:
    if (type(response) is not dict or set(response) != {"data"}
            or type(response["data"]) is not list or len(response["data"]) > 10000):
        raise OCIInventoryBlocked("OCI_RESPONSE_SCHEMA_DENIED")
    for value in response["data"]:
        if type(value) is not dict:
            raise OCIInventoryBlocked("OCI_RESPONSE_SCHEMA_DENIED")
    return response["data"]


def _match_one(rows: list[dict], name: str, lifecycle: str, id_type: str) -> dict | None:
    matches = [r for r in rows if r.get("display-name") == name
               and r.get("lifecycle-state") == lifecycle]
    if len(matches)>1:
        raise OCIInventoryBlocked("OCI_AMBIGUOUS_RESOURCE")
    if matches and not _ocid(matches[0].get("id"),id_type):
        raise OCIInventoryBlocked("OCI_RESPONSE_SCHEMA_DENIED")
    return matches[0] if matches else None


def _list(query: Callable[[tuple[str,...]],object], command: tuple[str,...]) -> list[dict]:
    if command[:3] not in SAFE_QUERY_GROUPS and command[:4] not in SAFE_QUERY_GROUPS:
        raise OCIInventoryBlocked("OCI_COMMAND_NOT_READ_ONLY")
    if command[-1] != "--all" or any(x in command for x in (
        "create","update","delete","launch","start","stop","terminate","apply",
        "instance-action","secret-bundle","get-secret-bundle",
    )):
        raise OCIInventoryBlocked("OCI_COMMAND_NOT_READ_ONLY")
    try:
        return _data(query(command))
    except OCIInventoryBlocked:
        raise
    except Exception:
        raise OCIInventoryBlocked("OCI_REMOTE_READ_FAILED") from None


def inspect_live_oci_inventory(*,tenancy_id: str, region: str,
                               query: Callable[[tuple[str,...]],object]) -> OCIInventorySummary:
    """Provide an OCI CLI JSON reader; no external read means no actual proof."""
    if not _ocid(tenancy_id,"tenancy") or region != TARGET_REGION:
        raise OCIInventoryBlocked("OCI_TENANCY_OR_REGION_DENIED")

    regions=_list(query,("iam","region-subscription","list","--all"))
    home=[r for r in regions if r.get("region-name")==region
          and r.get("is-home-region") is True
          and r.get("status") in ("READY","READY_TO_USE")]
    if len(home)!=1:
        raise OCIInventoryBlocked("OCI_HOME_REGION_NOT_VERIFIED")

    compartments=_list(query,("iam","compartment","list",
        "--compartment-id",tenancy_id,"--all"))
    folder=_match_one(compartments,TARGET_COMPARTMENT,"ACTIVE","compartment")
    if folder is None:
        raise OCIInventoryBlocked("OCI_STAGING_COMPARTMENT_NOT_FOUND")

    root_vcns=_list(query,("network","vcn","list",
        "--compartment-id",tenancy_id,"--all"))
    vcn=_match_one(root_vcns,TARGET_VCN,"AVAILABLE","vcn")
    if vcn:
        subnets=_list(query,("network","subnet","list",
            "--compartment-id",tenancy_id,"--vcn-id",vcn["id"],"--all"))
        found=[r for r in subnets if r.get("display-name")==TARGET_SUBNET
               and r.get("lifecycle-state")=="AVAILABLE"
               and r.get("vcn-id")==vcn["id"]]
        if len(found)>1:
            raise OCIInventoryBlocked("OCI_AMBIGUOUS_RESOURCE")
        subnet_status="AVAILABLE" if len(found)==1 else "MISSING"
    else:
        subnet_status="NOT_CHECKED"

    machines=_list(query,("compute","instance","list",
        "--compartment-id",folder["id"],"--all"))
    for machine in machines:
        if not _ocid(machine.get("id"),"instance"):
            # Instance IDs have the same public OCI format as other resource IDs.
            raise OCIInventoryBlocked("OCI_RESPONSE_SCHEMA_DENIED")
    running=sum(r.get("lifecycle-state")=="RUNNING" for r in machines)
    provisioning=sum(r.get("lifecycle-state") in ("PROVISIONING","STARTING") for r in machines)

    vaults=_list(query,("kms","management","vault","list",
        "--compartment-id",folder["id"],"--all"))
    active=sum(r.get("lifecycle-state")=="ACTIVE" for r in vaults)

    return OCIInventorySummary(
        region=region,home_region_observed=True,staging_compartment="ACTIVE",
        root_vcn="AVAILABLE" if vcn else "MISSING",root_subnet=subnet_status,
        staging_instances_running=running,staging_instances_provisioning=provisioning,
        staging_vaults_active=active,staging_vm_present=running>0,
        observations_from_live_api=True,
    )
