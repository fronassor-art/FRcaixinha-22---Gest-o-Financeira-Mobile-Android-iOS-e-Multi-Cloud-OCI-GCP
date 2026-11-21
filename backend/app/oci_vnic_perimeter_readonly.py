"""FR Finance M38210–M38249: inspect *observed* OCI VNIC/NSG perimeter.

No remote operations in this module. Snapshot provenance must come from the
authenticated OCI read-only collector, not from a user or API response. NSG
rules cannot prove subnet Security Lists, host firewall, live HTTPS, identity,
or production readiness. This module never authorizes a deployment.
"""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import Mapping

_REGION = "sa-saopaulo-1"


class PerimeterReadOnlyBlocked(ValueError):
    """Fixed, non-sensitive error codes only."""


@dataclass(frozen=True)
class VnicPerimeterSnapshot:
    region: str
    instance_lifecycle: str
    staging_compartment_confirmed: bool
    instance_compartment_confirmed: bool
    subnet_name: str
    vcn_name: str
    vnic_lifecycle: str
    primary_vnic: bool
    public_ipv4: str | None
    nsg_rules: tuple[tuple[Mapping, ...], ...]


@dataclass(frozen=True)
class VnicPerimeterReport:
    mode: str
    instance_running: bool
    public_ipv4_present: bool
    attached_nsg_count: int
    public_ipv4_443_ingress_candidate: bool
    public_ssh_ingress_review: bool
    public_database_ingress_review: bool
    blockers: tuple[str, ...]
    authenticated_oci_read_declared: bool = False
    external_firewall_verified: bool = False
    subnet_security_lists_verified_by_this_probe: bool = False
    host_firewall_verified: bool = False
    public_dns_tls_verified: bool = False
    backend_health_verified: bool = False
    database_rls_verified: bool = False
    deployment_authorized: bool = False
    real_user_activation_authorized: bool = False
    real_pix_authorized: bool = False
    cloud_mutations_performed: bool = False


def _valid_public_ipv4(address: object) -> bool:
    if type(address) is not str:
        return False
    try:
        ip = ip_address(address)
        return ip.version == 4 and ip.is_global
    except ValueError:
        return False


def _rule_port_set(rule: Mapping) -> tuple[bool, bool, bool]:
    """(public 443 candidate, public SSH risk, public database risk)."""
    if (type(rule) is not dict
            or rule.get("direction") != "INGRESS"
            or type(rule.get("protocol")) is not str
            or type(rule.get("source")) is not str
            or type(rule.get("source_type")) is not str
            or rule.get("source_type") not in ("CIDR_BLOCK", "NETWORK_SECURITY_GROUP")):
        raise PerimeterReadOnlyBlocked("M38210_NSG_RULE_SCHEMA_INVALID")
    if rule["source_type"] == "NETWORK_SECURITY_GROUP":
        return False, False, False
    try:
        cidr = ip_network(rule["source"], strict=True)
    except ValueError:
        raise PerimeterReadOnlyBlocked("M38210_NSG_RULE_SCHEMA_INVALID") from None

    # An NSG public ingress candidate requires exposure to the IPv4 internet,
    # not just one authorized IP. Any global range on SSH or PostgreSQL is
    # flagged for manual review even if the source is narrow.
    internet_ipv4 = cidr.version == 4 and cidr.prefixlen == 0
    public_range = not cidr.is_private
    protocol = rule["protocol"]
    if protocol not in ("6", "all"):
        # A protocol we don't inspect cannot attest safe exposure.
        raise PerimeterReadOnlyBlocked("M38210_NSG_PROTOCOL_UNATTESTED")
    if protocol == "all":
        return internet_ipv4, public_range, public_range
    tcp = rule.get("tcp_options")
    if tcp is None:
        return internet_ipv4, public_range, public_range
    if type(tcp) is not dict:
        raise PerimeterReadOnlyBlocked("M38210_NSG_PORTS_INVALID")
    bounds = tcp.get("destination_port_range")
    if bounds is None:
        return internet_ipv4, public_range, public_range
    if (type(bounds) is not dict or set(bounds) != {"min", "max"}
            or type(bounds.get("min")) is not int
            or type(bounds.get("max")) is not int
            or not 1 <= bounds["min"] <= bounds["max"] <= 65535):
        raise PerimeterReadOnlyBlocked("M38210_NSG_PORTS_INVALID")
    low, high = bounds["min"], bounds["max"]
    return (
        internet_ipv4 and low <= 443 <= high,
        public_range and low <= 22 <= high,
        public_range and (low <= 5432 <= high or low <= 5433 <= high),
    )


def assess_vnic_perimeter(
    snapshot: VnicPerimeterSnapshot,
) -> VnicPerimeterReport:
    if (
        type(snapshot) is not VnicPerimeterSnapshot
        or snapshot.region != _REGION
        or type(snapshot.instance_lifecycle) is not str
        or snapshot.instance_lifecycle not in (
            "RUNNING", "STARTING", "PROVISIONING", "STOPPED", "STOPPING",
        )
        or type(snapshot.staging_compartment_confirmed) is not bool
        or type(snapshot.instance_compartment_confirmed) is not bool
        or snapshot.subnet_name != "FR Finance"
        or snapshot.vcn_name != "FR Finance"
        or snapshot.vnic_lifecycle not in ("AVAILABLE", "PROVISIONING")
        or type(snapshot.primary_vnic) is not bool
        or snapshot.public_ipv4 is not None
           and type(snapshot.public_ipv4) is not str
        or type(snapshot.nsg_rules) is not tuple
        or len(snapshot.nsg_rules) > 16
        or any(type(group) is not tuple or len(group) > 1000
               for group in snapshot.nsg_rules)
    ):
        raise PerimeterReadOnlyBlocked("M38210_SNAPSHOT_SCHEMA_INVALID")
    if not all((
        snapshot.staging_compartment_confirmed,
        snapshot.instance_compartment_confirmed,
        snapshot.primary_vnic,
    )):
        raise PerimeterReadOnlyBlocked("M38210_INSTANCE_SCOPE_UNVERIFIED")

    has_public_ipv4 = _valid_public_ipv4(snapshot.public_ipv4)
    if snapshot.public_ipv4 is not None and not has_public_ipv4:
        raise PerimeterReadOnlyBlocked("M38210_PUBLIC_IP_UNSAFE")

    https_candidate, public_ssh, public_db = False, False, False
    for group in snapshot.nsg_rules:
        for rule in group:
            https, ssh, db = _rule_port_set(rule)
            https_candidate = https_candidate or https
            public_ssh = public_ssh or ssh
            public_db = public_db or db

    blockers: list[str] = []
    if snapshot.instance_lifecycle != "RUNNING":
        blockers.append("OCI_STAGING_INSTANCE_NOT_RUNNING")
    if snapshot.vnic_lifecycle != "AVAILABLE":
        blockers.append("OCI_PRIMARY_VNIC_NOT_AVAILABLE")
    if not has_public_ipv4:
        blockers.append("OCI_PUBLIC_IPV4_MISSING_OR_PROXY_ARCHITECTURE_REQUIRED")
    if not snapshot.nsg_rules:
        blockers.append("OCI_NSG_ATTACHMENT_MISSING")
    if not https_candidate:
        blockers.append("OCI_NSG_PUBLIC_IPV4_443_NOT_OBSERVED")
    if public_ssh:
        blockers.append("OCI_NSG_PUBLIC_SSH_REVIEW_REQUIRED")
    if public_db:
        blockers.append("OCI_NSG_PUBLIC_POSTGRESQL_REVIEW_REQUIRED")

    # NSG configuration is a necessary inspection, never proof of actual
    # reachability. The OS firewall, TLS, ingress Security Lists, IAM and
    # database isolation remain independent external release blockers.
    blockers.extend((
        "OCI_SECURITY_LIST_EFFECTIVE_PATH_NOT_ATTESTED_BY_NSG",
        "OCI_HOST_FIREWALL_NOT_ATTESTED",
        "OCI_PUBLIC_TLS_AND_BACKEND_NOT_ATTESTED",
        "OCI_AUTH_DB_RLS_AND_RESTORE_NOT_ATTESTED",
    ))
    return VnicPerimeterReport(
        mode="OCI_VNIC_NSG_READ_ONLY_OBSERVATION",
        instance_running=snapshot.instance_lifecycle == "RUNNING",
        public_ipv4_present=has_public_ipv4,
        attached_nsg_count=len(snapshot.nsg_rules),
        public_ipv4_443_ingress_candidate=https_candidate,
        public_ssh_ingress_review=public_ssh,
        public_database_ingress_review=public_db,
        blockers=tuple(blockers),
    )
