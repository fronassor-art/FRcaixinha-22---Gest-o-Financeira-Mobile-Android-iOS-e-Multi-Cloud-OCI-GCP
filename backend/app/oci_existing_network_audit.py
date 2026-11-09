"""M37312-M37316: OCI existing VCN security/readiness audit, read only.

This is NOT an OCI Terraform planner or deployment gate: the API, TLS, NSGs
on future VNICs, security of OS, price and capacity remain unverified.
No modify, create, terminate, or secret-read operations.
"""
from __future__ import annotations

from dataclasses import dataclass
from ipaddress import ip_network
from typing import Callable

REGION = "sa-saopaulo-1"
VCN_NAME = "FR Finance"
SUBNET_NAME = "FR Finance"


class NetworkAuditBlocked(ValueError):
    """Fixed, non-sensitive reason only; never include raw OCI data."""


@dataclass(frozen=True)
class NetworkReport:
    region: str
    state: str
    vcn: str
    subnet: str
    vcn_private_ipv4: bool
    subnet_private_ipv4: bool
    subnet_allows_public_ip: bool
    internet_gateway_enabled: bool
    default_ipv4_route_to_igw: bool
    security_lists_checked: int
    public_tcp_80_rule_present: bool
    public_tcp_443_rule_present: bool
    public_tcp_22_rule_present: bool
    public_db_port_exposure: bool
    nsgs_on_future_vnic_verified: bool = False
    host_firewall_verified: bool = False
    public_https_verified: bool = False
    vm_running_verified: bool = False
    iam_vault_verified: bool = False
    deployment_authorized: bool = False
    real_pix_authorized: bool = False
    mutations_performed: bool = False


def _blocked(reason: str):
    raise NetworkAuditBlocked(reason)


def _ocid(value: object, kind: str) -> bool:
    return (type(value) is str and value.startswith("ocid1."+kind+".oc1.")
            and 18 < len(value) < 360 and " " not in value
            and "/" not in value and "\n" not in value)


def _json(query: Callable, command: tuple[str,...], *, list_mode: bool):
    try:
        response=query(command)
    except NetworkAuditBlocked:
        raise
    except Exception:
        raise NetworkAuditBlocked("OCI_NETWORK_READ_FAILED") from None
    if type(response) is not dict or set(response)!={"data"}:
        _blocked("OCI_NETWORK_SCHEMA_INVALID")
    data=response["data"]
    if list_mode:
        if type(data) is not list or len(data)>1000 or any(type(x) is not dict for x in data):
            _blocked("OCI_NETWORK_SCHEMA_INVALID")
    elif type(data) is not dict:
        _blocked("OCI_NETWORK_SCHEMA_INVALID")
    return data


def _unique(rows: list[dict], name: str, kind: str):
    matches=[r for r in rows if r.get("display-name")==name
             and r.get("lifecycle-state")=="AVAILABLE"]
    if len(matches)>1:
        _blocked("OCI_NETWORK_NAME_AMBIGUOUS")
    if matches and not _ocid(matches[0].get("id"),kind):
        _blocked("OCI_NETWORK_ID_INVALID")
    return matches[0] if matches else None


def _private_cidr(raw: object) -> bool:
    if type(raw) is not str:
        return False
    try:
        net=ip_network(raw,strict=True)
        return net.version==4 and net.is_private and not net.is_multicast
    except ValueError:
        return False


def _covers_public_source(raw: object) -> bool:
    if type(raw) is not str:
        return False
    try:
        ip=ip_network(raw,strict=False)
        return ip.prefixlen == 0 and ip.network_address.is_unspecified
    except ValueError:
        return False


def _port_exposed(rule: dict, port: int) -> bool:
    if not _covers_public_source(rule.get("source")):
        return False
    proto=str(rule.get("protocol"))
    if proto in ("all","-1"):
        return True
    if proto != "6":
        return False
    tcp=rule.get("tcp-options")
    if tcp is None:
        return True
    if type(tcp) is not dict:
        _blocked("OCI_NETWORK_SCHEMA_INVALID")
    rng=tcp.get("destination-port-range")
    if rng is None:
        return True
    if (type(rng) is not dict or type(rng.get("min")) is not int
            or type(rng.get("max")) is not int
            or not 1 <= rng["min"] <= rng["max"] <= 65535):
        _blocked("OCI_NETWORK_SCHEMA_INVALID")
    return rng["min"] <= port <= rng["max"]


def inspect_existing_root_network(tenancy_id: str, region: str, query: Callable) -> NetworkReport:
    """Perform exact read-only query sequence for the existing root network."""
    if not _ocid(tenancy_id,"tenancy") or region!=REGION:
        _blocked("OCI_NETWORK_REGION_OR_TENANCY_DENIED")
    vcn_rows=_json(query,("network","vcn","list",
        "--compartment-id",tenancy_id,"--all"),list_mode=True)
    vcn=_unique(vcn_rows,VCN_NAME,"vcn")
    if vcn is None:
        _blocked("OCI_NETWORK_VCN_NOT_FOUND")
    cidr=vcn.get("cidr-blocks")
    if cidr is None:
        cidr=[vcn.get("cidr-block")]
    if (type(cidr) is not list or not cidr or len(cidr)>5
            or not all(_private_cidr(x) for x in cidr)):
        _blocked("OCI_NETWORK_VCN_CIDR_UNSAFE_OR_MISSING")

    subnets=_json(query,("network","subnet","list",
        "--compartment-id",tenancy_id,"--vcn-id",vcn["id"],"--all"),list_mode=True)
    subnet=_unique([r for r in subnets if r.get("vcn-id")==vcn["id"]],
                   SUBNET_NAME,"subnet")
    if subnet is None:
        _blocked("OCI_NETWORK_SUBNET_NOT_FOUND")
    if not _private_cidr(subnet.get("cidr-block")):
        _blocked("OCI_NETWORK_SUBNET_CIDR_UNSAFE_OR_MISSING")
    public_flag=subnet.get("prohibit-public-ip-on-vnic")
    if type(public_flag) is not bool:
        _blocked("OCI_NETWORK_PUBLIC_IP_POLICY_UNKNOWN")

    route_id=subnet.get("route-table-id")
    sec_ids=subnet.get("security-list-ids")
    if (not _ocid(route_id,"routetable") or type(sec_ids) is not list
            or len(sec_ids) not in range(1,17)
            or len(set(sec_ids))!=len(sec_ids)
            or any(not _ocid(x,"securitylist") for x in sec_ids)):
        _blocked("OCI_NETWORK_ROUTE_OR_SECURITY_LIST_MISSING")

    r=_json(query,("network","route-table","get",
                   "--rt-id",route_id),list_mode=False)
    if r.get("id")!=route_id or r.get("lifecycle-state")!="AVAILABLE":
        _blocked("OCI_NETWORK_ROUTE_TABLE_INVALID")
    rules=r.get("route-rules")
    if type(rules) is not list or len(rules)>200:
        _blocked("OCI_NETWORK_ROUTE_TABLE_INVALID")
    gwrows=_json(query,("network","internet-gateway","list",
        "--compartment-id",tenancy_id,"--vcn-id",vcn["id"],"--all"),list_mode=True)
    gwids=set()
    for g in gwrows:
        if (g.get("vcn-id")==vcn["id"]
                and g.get("lifecycle-state")=="AVAILABLE"
                and g.get("is-enabled") is True):
            if not _ocid(g.get("id"),"internetgateway"):
                _blocked("OCI_NETWORK_GATEWAY_INVALID")
            gwids.add(g["id"])
    to_igw=False
    for rule in rules:
        if type(rule) is not dict:
            _blocked("OCI_NETWORK_ROUTE_TABLE_INVALID")
        if (rule.get("destination")=="0.0.0.0/0"
                and rule.get("destination-type")=="CIDR_BLOCK"
                and rule.get("network-entity-id") in gwids):
            to_igw=True

    inbound=[]
    for sid in sec_ids:
        sec=_json(query,("network","security-list","get",
                         "--security-list-id",sid),list_mode=False)
        if sec.get("id")!=sid or sec.get("lifecycle-state")!="AVAILABLE":
            _blocked("OCI_NETWORK_SECURITY_LIST_INVALID")
        items=sec.get("ingress-security-rules")
        if type(items) is not list or len(items)>500 or any(type(x) is not dict for x in items):
            _blocked("OCI_NETWORK_SECURITY_LIST_INVALID")
        inbound.extend(items)

    p80=any(_port_exposed(x,80) for x in inbound)
    p443=any(_port_exposed(x,443) for x in inbound)
    p22=any(_port_exposed(x,22) for x in inbound)
    db=any(_port_exposed(x,p) for x in inbound for p in (5432,5433))
    if db or p22:
        state="NETWORK_PUBLIC_ADMIN_OR_DATABASE_EXPOSURE_REVIEW"
    elif not to_igw:
        state="NETWORK_NO_CONFIRMED_DEFAULT_IGW_ROUTE"
    elif not p443:
        state="NETWORK_HTTPS_INGRESS_NOT_PREPARED"
    else:
        state="NETWORK_ONLY_NO_VM_OR_PUBLIC_TLS_PROOF"
    return NetworkReport(
        region=region,state=state,vcn="AVAILABLE",subnet="AVAILABLE",
        vcn_private_ipv4=True,subnet_private_ipv4=True,
        subnet_allows_public_ip=not public_flag,
        internet_gateway_enabled=bool(gwids),default_ipv4_route_to_igw=to_igw,
        security_lists_checked=len(sec_ids),public_tcp_80_rule_present=p80,
        public_tcp_443_rule_present=p443,public_tcp_22_rule_present=p22,
        public_db_port_exposure=db,
    )
