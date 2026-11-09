#!/usr/bin/env python3
"""M37312-M37316: inspect the existing FR Finance root network via OCI SDK.

Only list_vcns/list_subnets/list_internet_gateways/get_route_table/
get_security_list are invoked. This does not check NSGs on a future VM,
instance capacity, IP reachability, DNS, TLS, OS firewall or service health.
No configuration or raw OCI payload is printed.
"""
from __future__ import annotations

import os
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.oci_existing_network_audit import (
    NetworkAuditBlocked,REGION,inspect_existing_root_network,
)


def _sdk_query(client, oci, command):
    key=tuple(command[:3])
    lists={
        ("network","vcn","list"):"list_vcns",
        ("network","subnet","list"):"list_subnets",
        ("network","internet-gateway","list"):"list_internet_gateways",
    }
    gets={
        ("network","route-table","get"):"get_route_table",
        ("network","security-list","get"):"get_security_list",
    }
    if key in lists:
        if (command[-1]!="--all" or len(command) not in (6,8)
                or command[3]!="--compartment-id"
                or (len(command)==8 and command[5]!="--vcn-id")):
            raise NetworkAuditBlocked("OCI_NETWORK_COMMAND_DENIED")
        method=getattr(client,lists[key])
        args={"limit":100,"retry_strategy":oci.retry.NoneRetryStrategy()}
        if len(command)==8:
            args["vcn_id"]=command[6]
        results=[]
        seen=set()
        page=None
        for _ in range(50):
            options=dict(args)
            if page is not None:
                options["page"]=page
            try:
                response=method(command[4],**options)
            except Exception:
                raise NetworkAuditBlocked("OCI_NETWORK_LIST_FAILED") from None
            if (type(response.status) is not int or response.status!=200
                    or type(response.data) is not list or len(response.data)>100):
                raise NetworkAuditBlocked("OCI_NETWORK_LIST_RESPONSE_INVALID")
            results.extend(oci.util.to_dict(x) for x in response.data)
            if len(results)>1000:
                raise NetworkAuditBlocked("OCI_NETWORK_LIST_TOO_LARGE")
            page=response.next_page
            if page is None:
                return {"data":results}
            if (type(page) is not str or not page or len(page)>2048
                    or page in seen):
                raise NetworkAuditBlocked("OCI_NETWORK_PAGINATION_INVALID")
            seen.add(page)
        raise NetworkAuditBlocked("OCI_NETWORK_PAGINATION_LIMIT")
    if key in gets:
        if (len(command)!=5 or command[3] not in ("--rt-id","--security-list-id")
                or (key==("network","route-table","get") and command[3]!="--rt-id")
                or (key==("network","security-list","get")
                    and command[3]!="--security-list-id")):
            raise NetworkAuditBlocked("OCI_NETWORK_COMMAND_DENIED")
        method=getattr(client,gets[key])
        try:
            response=method(command[4],retry_strategy=oci.retry.NoneRetryStrategy())
        except Exception:
            raise NetworkAuditBlocked("OCI_NETWORK_GET_FAILED") from None
        if type(response.status) is not int or response.status!=200 or response.data is None:
            raise NetworkAuditBlocked("OCI_NETWORK_GET_RESPONSE_INVALID")
        return {"data":oci.util.to_dict(response.data)}
    raise NetworkAuditBlocked("OCI_NETWORK_COMMAND_DENIED")


def main() -> int:
    print("=== FR FINANCE M37316 OCI NETWORK READ ONLY ===")
    try:
        import oci
        cfg=oci.config.from_file(
            file_location=str(Path(os.environ.get("OCI_CLI_CONFIG_FILE",
                                                   "~/.oci/config")).expanduser()),
            profile_name=os.environ.get("OCI_CLI_PROFILE","DEFAULT"),
        )
        if cfg.get("region")!=REGION or type(cfg.get("tenancy")) is not str:
            raise NetworkAuditBlocked("OCI_NETWORK_CONFIG_REGION_INVALID")
        sdk=oci.core.VirtualNetworkClient(
            cfg,timeout=(5,30),retry_strategy=oci.retry.NoneRetryStrategy(),
        )
        report=inspect_existing_root_network(
            tenancy_id=cfg["tenancy"],region=cfg["region"],
            query=lambda command:_sdk_query(sdk,oci,command),
        )
    except NetworkAuditBlocked as exc:
        print("OCI_M37316_NETWORK_AUDIT=BLOCKED")
        print("OCI_CAUSE="+str(exc))
        print("OCI_RESOURCE_CREATED=NO")
        print("PIX_REAL=OFF")
        return 2
    except Exception:
        print("OCI_M37316_NETWORK_AUDIT=BLOCKED")
        print("OCI_CAUSE=OCI_SDK_UNAVAILABLE_OR_READ_FAILED")
        print("OCI_RESOURCE_CREATED=NO")
        print("PIX_REAL=OFF")
        return 2
    print("OCI_M37316_NETWORK_AUDIT=READ_ONLY_PASS")
    print("OCI_REGION="+report.region)
    print("OCI_NETWORK_STATE="+report.state)
    print("OCI_VCN="+report.vcn)
    print("OCI_SUBNET="+report.subnet)
    print("OCI_VCN_PRIVATE_IPV4="+str(report.vcn_private_ipv4).upper())
    print("OCI_SUBNET_PRIVATE_IPV4="+str(report.subnet_private_ipv4).upper())
    print("OCI_SUBNET_ALLOWS_PUBLIC_IP="+str(report.subnet_allows_public_ip).upper())
    print("OCI_IGW_ENABLED="+str(report.internet_gateway_enabled).upper())
    print("OCI_DEFAULT_ROUTE_TO_IGW="+str(report.default_ipv4_route_to_igw).upper())
    print("OCI_SECURITY_LISTS_CHECKED="+str(report.security_lists_checked))
    print("OCI_PUBLIC_TCP_80_RULE="+str(report.public_tcp_80_rule_present).upper())
    print("OCI_PUBLIC_TCP_443_RULE="+str(report.public_tcp_443_rule_present).upper())
    print("OCI_PUBLIC_TCP_22_RULE="+str(report.public_tcp_22_rule_present).upper())
    print("OCI_PUBLIC_DB_PORT_EXPOSURE="+str(report.public_db_port_exposure).upper())
    print("OCI_NSG_VNIC=NOT_VERIFIED")
    print("OCI_PUBLIC_HTTPS=NOT_VERIFIED")
    print("OCI_HOST_FIREWALL=NOT_VERIFIED")
    print("OCI_VM_DEPLOYMENT=NOT_AUTHORIZED")
    print("OCI_RESOURCE_CREATED=NO")
    print("OCI_PAID_UPGRADE=NOT_REQUESTED")
    print("REAL_USER_ACTIVATION=OFF")
    print("PIX_REAL=OFF")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
