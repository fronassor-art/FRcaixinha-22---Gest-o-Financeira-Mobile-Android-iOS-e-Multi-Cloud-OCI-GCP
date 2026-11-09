"""M37312-M37316: OCI existing root network audit with no cloud mutation."""
from __future__ import annotations
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest

from app.oci_existing_network_audit import (
    NetworkAuditBlocked,inspect_existing_root_network,
)

ROOT=Path(__file__).resolve().parents[2]
TEN="ocid1.tenancy.oc1.."+"a"*25
VCN="ocid1.vcn.oc1.sa-saopaulo-1."+"b"*25
SUBNET="ocid1.subnet.oc1.sa-saopaulo-1."+"c"*25
ROUTE="ocid1.routetable.oc1.sa-saopaulo-1."+"d"*25
SEC="ocid1.securitylist.oc1.sa-saopaulo-1."+"e"*25
IGW="ocid1.internetgateway.oc1.sa-saopaulo-1."+"f"*25


def data(*, subnet_public=True, rule_ports=(), public_ssh=False,
         route=True, gateway=True, vcn_private=True, sub_private=True):
    rules=[{"source":"0.0.0.0/0","protocol":"6",
            "tcp-options":{"destination-port-range":{"min":p,"max":p}}}
            for p in rule_ports]
    if public_ssh:
        rules += [{"source":"0.0.0.0/0","protocol":"6",
                   "tcp-options":{"destination-port-range":{"min":22,"max":22}}}]
    return {
        ("network","vcn","list"):{"data":[
            {"id":VCN,"display-name":"FR Finance","lifecycle-state":"AVAILABLE",
             "cidr-blocks":["10.71.0.0/16" if vcn_private else "8.8.8.0/24"]}]},
        ("network","subnet","list"):{"data":[
            {"id":SUBNET,"vcn-id":VCN,"display-name":"FR Finance",
             "lifecycle-state":"AVAILABLE",
             "cidr-block":"10.71.1.0/24" if sub_private else "8.8.8.0/24",
             "prohibit-public-ip-on-vnic":not subnet_public,
             "route-table-id":ROUTE,
             "security-list-ids":[SEC]}]},
        ("network","route-table","get"):{"data":{
            "id":ROUTE,"lifecycle-state":"AVAILABLE",
            "route-rules":[{"destination":"0.0.0.0/0","destination-type":"CIDR_BLOCK",
                             "network-entity-id":IGW}] if route else []}},
        ("network","internet-gateway","list"):{"data":[
            {"id":IGW,"vcn-id":VCN,"lifecycle-state":"AVAILABLE",
             "is-enabled":gateway}]},
        ("network","security-list","get"):{"data":{
            "id":SEC,"lifecycle-state":"AVAILABLE",
            "ingress-security-rules":rules}},
    }


def make_query(source):
    calls=[]
    def query(cmd):
        assert cmd[:3] in source
        assert "launch" not in cmd and "create" not in cmd and "update" not in cmd
        calls.append(cmd)
        return source[cmd[:3]]
    return query,calls


def check(**kwargs):
    query,calls=make_query(data(**kwargs))
    return inspect_existing_root_network(TEN,"sa-saopaulo-1",query),calls


def test_existing_network_reports_only_network_evidence():
    report,calls=check()
    assert len(calls)==5
    assert report.vcn=="AVAILABLE" and report.subnet=="AVAILABLE"
    assert report.vcn_private_ipv4 and report.subnet_private_ipv4
    assert report.subnet_allows_public_ip
    assert report.internet_gateway_enabled
    assert report.default_ipv4_route_to_igw
    assert report.security_lists_checked==1
    assert report.state=="NETWORK_HTTPS_INGRESS_NOT_PREPARED"
    assert not any(getattr(report,field) for field in (
        "public_tcp_80_rule_present","public_tcp_443_rule_present",
        "public_tcp_22_rule_present","public_db_port_exposure",
        "nsgs_on_future_vnic_verified","host_firewall_verified",
        "public_https_verified","vm_running_verified","iam_vault_verified",
        "deployment_authorized","real_pix_authorized","mutations_performed",
    ))


def test_existing_https_rule_never_authorizes_deployment():
    report,_=check(rule_ports=(443,))
    assert report.public_tcp_443_rule_present
    assert report.state=="NETWORK_ONLY_NO_VM_OR_PUBLIC_TLS_PROOF"
    assert not report.public_https_verified and not report.deployment_authorized


@pytest.mark.parametrize("ports",[(22,),(5432,),(5433,),(5432,443)])
def test_public_admin_or_db_exposure_not_silent(ports):
    report,_=check(rule_ports=ports)
    assert report.state=="NETWORK_PUBLIC_ADMIN_OR_DATABASE_EXPOSURE_REVIEW"
    assert not report.deployment_authorized


def test_route_without_enabled_gateway_not_confirmed():
    r,_=check(gateway=False)
    assert not r.internet_gateway_enabled and not r.default_ipv4_route_to_igw
    assert r.state=="NETWORK_NO_CONFIRMED_DEFAULT_IGW_ROUTE"


def test_missing_default_route_not_proof_of_public_access():
    r,_=check(route=False,rule_ports=(443,))
    assert not r.default_ipv4_route_to_igw
    assert r.state=="NETWORK_NO_CONFIRMED_DEFAULT_IGW_ROUTE"


def test_private_subnet_remains_unproven_for_public_api():
    r,_=check(subnet_public=False,rule_ports=(443,))
    assert not r.subnet_allows_public_ip
    assert r.state=="NETWORK_SUBNET_PROHIBITS_PUBLIC_IP_NEEDS_ARCHITECTURE_REVIEW"
    assert not r.public_https_verified and not r.deployment_authorized


@pytest.mark.parametrize("what",["vcn","subnet"])
def test_public_or_missing_cidr_fails_closed(what):
    kwargs={"vcn_private":False} if what=="vcn" else {"sub_private":False}
    with pytest.raises(NetworkAuditBlocked,match="CIDR_UNSAFE_OR_MISSING"):
        check(**kwargs)


@pytest.mark.parametrize("name,match",[
    ("vcn","OCI_NETWORK_VCN_NOT_FOUND"),
    ("subnet","OCI_NETWORK_SUBNET_NOT_FOUND"),
])
def test_missing_named_resources_are_not_assumed(name,match):
    obj=data()
    obj[("network",name,"list")]["data"]=[]
    query,_=make_query(obj)
    with pytest.raises(NetworkAuditBlocked,match=match):
        inspect_existing_root_network(TEN,"sa-saopaulo-1",query)


def test_multiple_matching_vcns_fails_closed():
    obj=data()
    obj[("network","vcn","list")]["data"]*=2
    query,_=make_query(obj)
    with pytest.raises(NetworkAuditBlocked,match="OCI_NETWORK_NAME_AMBIGUOUS"):
        inspect_existing_root_network(TEN,"sa-saopaulo-1",query)


def test_malformed_security_list_fails_closed():
    obj=data()
    obj[("network","security-list","get")]["data"]["ingress-security-rules"]=None
    query,_=make_query(obj)
    with pytest.raises(NetworkAuditBlocked,match="OCI_NETWORK_SECURITY_LIST_INVALID"):
        inspect_existing_root_network(TEN,"sa-saopaulo-1",query)


def test_all_protocol_public_rule_flags_ssh_and_db():
    obj=data()
    obj[("network","security-list","get")]["data"]["ingress-security-rules"]=[
        {"protocol":"all","source":"::/0"}
    ]
    query,_=make_query(obj)
    result=inspect_existing_root_network(TEN,"sa-saopaulo-1",query)
    assert result.public_tcp_22_rule_present
    assert result.public_db_port_exposure


def test_narrow_source_is_not_misclassified_as_internet_open():
    obj=data()
    obj[("network","security-list","get")]["data"]["ingress-security-rules"]=[
        {"protocol":"6","source":"10.71.0.0/16"}
    ]
    query,_=make_query(obj)
    result=inspect_existing_root_network(TEN,"sa-saopaulo-1",query)
    assert not result.public_db_port_exposure
    assert not result.public_tcp_22_rule_present


def test_wrong_tenancy_or_region_rejected_before_api():
    q,calls=make_query(data())
    for tenant,region in (("bad","sa-saopaulo-1"),(TEN,"us-ashburn-1")):
        with pytest.raises(NetworkAuditBlocked,match="OCI_NETWORK_REGION_OR_TENANCY_DENIED"):
            inspect_existing_root_network(tenant,region,q)
    assert calls==[]


def _script():
    path=ROOT/"backend/scripts/aistudio_oci_existing_network_readonly.py"
    spec=importlib.util.spec_from_file_location("frfinance_net_audit",path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_sdk(monkeypatch,source):
    calls=[]
    class NoRetry:
        pass
    def wrap(raw):
        return SimpleNamespace(status=200,data=raw,next_page=None)
    class Client:
        def __init__(self,cfg,**kw):
            assert cfg["region"]=="sa-saopaulo-1"
            assert kw["timeout"]==(5,30)
        def list_vcns(self,compartment,**kw):
            calls.append("list_vcns")
            assert compartment==TEN
            return wrap(source[("network","vcn","list")]["data"])
        def list_subnets(self,compartment,**kw):
            calls.append("list_subnets")
            assert compartment==TEN and kw["vcn_id"]==VCN
            return wrap(source[("network","subnet","list")]["data"])
        def get_route_table(self,resource_id,**kw):
            calls.append("get_route_table")
            assert resource_id==ROUTE
            return wrap(source[("network","route-table","get")]["data"])
        def list_internet_gateways(self,compartment,**kw):
            calls.append("list_internet_gateways")
            assert compartment==TEN and kw["vcn_id"]==VCN
            return wrap(source[("network","internet-gateway","list")]["data"])
        def get_security_list(self,resource_id,**kw):
            calls.append("get_security_list")
            assert resource_id==SEC
            return wrap(source[("network","security-list","get")]["data"])
    sdk=SimpleNamespace(
        config=SimpleNamespace(from_file=lambda **kw:{"tenancy":TEN,"region":"sa-saopaulo-1"}),
        core=SimpleNamespace(VirtualNetworkClient=Client),
        retry=SimpleNamespace(NoneRetryStrategy=NoRetry),
        util=SimpleNamespace(to_dict=lambda x:x),
    )
    monkeypatch.setitem(sys.modules,"oci",sdk)
    return calls,sdk


def test_live_script_with_mock_sdk_never_prints_ids(monkeypatch,capsys):
    calls,_=fake_sdk(monkeypatch,data())
    assert _script().main()==0
    stdout=capsys.readouterr().out
    assert "OCI_M37316_NETWORK_AUDIT=READ_ONLY_PASS" in stdout
    assert "OCI_PUBLIC_TCP_443_RULE=FALSE" in stdout
    assert "OCI_VM_DEPLOYMENT=NOT_AUTHORIZED" in stdout
    assert "PIX_REAL=OFF" in stdout
    for ocid in (TEN,VCN,SUBNET,ROUTE,SEC,IGW):
        assert ocid not in stdout
    assert len(calls)==5


def test_sdk_http_non_200_cannot_be_reported_as_empty(monkeypatch):
    m=_script()
    calls,sdk=fake_sdk(monkeypatch,data())
    class Bad:
        def list_vcns(self,comp,**kw):
            return SimpleNamespace(status=403,data=[],next_page=None)
    with pytest.raises(NetworkAuditBlocked,match="OCI_NETWORK_LIST_RESPONSE_INVALID"):
        m._sdk_query(Bad(),sdk,("network","vcn","list","--compartment-id",TEN,"--all"))


def test_sdk_list_no_untrusted_methods(monkeypatch):
    m=_script()
    calls,sdk=fake_sdk(monkeypatch,data())
    with pytest.raises(NetworkAuditBlocked,match="OCI_NETWORK_COMMAND_DENIED"):
        m._sdk_query(None,sdk,("network","vcn","create","--compartment-id",TEN))


def test_mutating_code_paths_not_present():
    code=(ROOT/"backend/scripts/aistudio_oci_existing_network_readonly.py").read_text()
    for token in ("create_vcn(","update_vcn(","delete_vcn(","launch_instance(",
                  "create_internet_gateway(","update_security_list(",
                  "terminate_instance(","terraform apply"):
        assert token not in code
