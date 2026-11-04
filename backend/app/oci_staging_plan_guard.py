"""M2700: OCI staging Terraform plan security gate, READ ONLY.

Reviews a separately generated terraform-show JSON file without AWS/OCI calls,
secret extraction, or filesystem mutation. This cannot establish that anything
was provisioned. Plans containing sensitive data must stay LOCAL, not in git.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

CONTRACT = "AI_STUDIO_M2700_OCI_STAGING_PLAN_GUARD_V1"
MAX_BYTES = 8_000_000
RESOURCES = {
    "oci_core_vcn.staging": "oci_core_vcn",
    "oci_core_security_list.deny_all": "oci_core_security_list",
    "oci_core_route_table.isolated": "oci_core_route_table",
    "oci_core_subnet.private": "oci_core_subnet",
}
_ALLOWED_ACTIONS = {("create",), ("no-op",)}
_CHECKED_FIELDS = {
    "oci_core_vcn.staging": ("cidr_blocks", "ipv6cidr_blocks"),
    "oci_core_security_list.deny_all": ("ingress_security_rules", "egress_security_rules"),
    "oci_core_route_table.isolated": ("route_rules",),
    "oci_core_subnet.private": (
        "cidr_block", "ipv6cidr_blocks", "ipv6cidr_block",
        "prohibit_public_ip_on_vnic",
    ),
}


class StagingPlanBlocked(ValueError):
    """Fail-closed condition; do not include untrusted plan data in error."""


def _blocked() -> None:
    raise StagingPlanBlocked("Plano OCI staging reprovado; revisar localmente.")


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            _blocked()
        out[key] = value
    return out


def _nonfinite(_: str) -> None:
    _blocked()


def _empty(value: Any) -> bool:
    return value is None or value == []


def _safe_value(address: str, after: Mapping[str, Any], unknown: Any) -> None:
    if not isinstance(unknown, Mapping):
        _blocked()
    for field in _CHECKED_FIELDS[address]:
        if field in unknown and not _empty(unknown[field]):
            _blocked()

    # Network-policy fields on the wrong resource are invalid, not ignored.
    if address != "oci_core_security_list.deny_all" and (
        "ingress_security_rules" in after or "egress_security_rules" in after
    ):
        _blocked()
    if address != "oci_core_route_table.isolated" and "route_rules" in after:
        _blocked()
    if address == "oci_core_vcn.staging":
        if after.get("cidr_blocks") != ["10.77.0.0/16"]:
            _blocked()
        if not _empty(after.get("ipv6cidr_blocks")):
            _blocked()
    elif address == "oci_core_security_list.deny_all":
        if not _empty(after.get("ingress_security_rules")):
            _blocked()
        if not _empty(after.get("egress_security_rules")):
            _blocked()
    elif address == "oci_core_route_table.isolated":
        if not _empty(after.get("route_rules")):
            _blocked()
    elif address == "oci_core_subnet.private":
        if after.get("cidr_block") != "10.77.10.0/24":
            _blocked()
        if after.get("prohibit_public_ip_on_vnic") is not True:
            _blocked()
        if not _empty(after.get("ipv6cidr_block")):
            _blocked()
        if not _empty(after.get("ipv6cidr_blocks")):
            _blocked()


def audit_plan(plan: object) -> tuple[str, ...]:
    """Reject all resources except isolated VCN, deny-all list, route, subnet.

    Allows only create/no-op actions: no update/delete/recreate. A plan PASS is
    one precondition, not a license to run terraform apply.
    """
    if type(plan) is not dict:
        _blocked()
    version = plan.get("format_version")
    if type(version) is not str or not version.startswith("1."):
        _blocked()
    changes = plan.get("resource_changes")
    if type(changes) is not list or len(changes) != len(RESOURCES):
        _blocked()
    observed: set[str] = set()
    for resource in changes:
        if type(resource) is not dict or resource.get("mode") != "managed":
            _blocked()
        address = resource.get("address")
        if type(address) is not str or address not in RESOURCES or address in observed:
            _blocked()
        if resource.get("type") != RESOURCES[address]:
            _blocked()
        if resource.get("provider_name") not in (
            "registry.terraform.io/oracle/oci",
            None,
        ):
            _blocked()
        if resource.get("index") is not None:
            _blocked()
        change = resource.get("change")
        if type(change) is not dict:
            _blocked()
        actions = change.get("actions")
        if type(actions) is not list or tuple(actions) not in _ALLOWED_ACTIONS:
            _blocked()
        after = change.get("after")
        if type(after) is not dict:
            _blocked()
        _safe_value(address, after, change.get("after_unknown", {}))
        observed.add(address)
    if observed != set(RESOURCES):
        _blocked()
    # There must be no extra instances hidden in planned_values.
    module = plan.get("planned_values", {}).get("root_module")
    if type(module) is not dict or module.get("child_modules"):
        _blocked()
    current = module.get("resources")
    if type(current) is not list or len(current) != len(RESOURCES):
        _blocked()
    planned_addresses = set()
    for resource in current:
        if type(resource) is not dict or resource.get("mode") != "managed":
            _blocked()
        address = resource.get("address")
        if address not in RESOURCES or resource.get("type") != RESOURCES[address]:
            _blocked()
        if address in planned_addresses:
            _blocked()
        planned_addresses.add(address)
    if planned_addresses != observed:
        _blocked()
    return tuple(sorted(observed))


def audit_plan_file(file: Path) -> tuple[str, ...]:
    if type(file) is not Path or not file.is_file():
        _blocked()
    size = file.stat().st_size
    if not 0 < size <= MAX_BYTES:
        _blocked()
    try:
        raw = file.read_bytes()
        plan = json.loads(
            raw, object_pairs_hook=_no_duplicate_keys,
            parse_constant=_nonfinite,
        )
    except (OSError, ValueError, UnicodeError, TypeError):
        _blocked()
    return audit_plan(plan)
