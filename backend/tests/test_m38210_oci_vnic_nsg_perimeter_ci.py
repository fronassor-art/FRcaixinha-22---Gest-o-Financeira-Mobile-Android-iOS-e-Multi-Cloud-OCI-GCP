"""FR Finance M38210–M38249: exact VNIC and NSG read-only perimeter tests."""
from dataclasses import replace
from pathlib import Path
import os
import subprocess
import sys

import pytest

from app.oci_vnic_perimeter_readonly import (
    PerimeterReadOnlyBlocked, VnicPerimeterSnapshot, assess_vnic_perimeter,
)

PUBLIC_IPV4 = "93.184.215.14"


def ingress(*, source="0.0.0.0/0", protocol="6", low=443, high=443,
            source_type="CIDR_BLOCK", direction="INGRESS", tcp=True):
    rule = dict(direction=direction, source=source, source_type=source_type,
                protocol=protocol)
    if tcp:
        rule["tcp_options"] = {"destination_port_range":{"min":low,"max":high}}
    return rule


def fixture(**changes):
    base = VnicPerimeterSnapshot(
        region="sa-saopaulo-1", instance_lifecycle="RUNNING",
        staging_compartment_confirmed=True,
        instance_compartment_confirmed=True,
        subnet_name="FR Finance", vcn_name="FR Finance",
        vnic_lifecycle="AVAILABLE", primary_vnic=True,
        public_ipv4=PUBLIC_IPV4,
        nsg_rules=((ingress(),),),
    )
    return replace(base, **changes)


def report(**changes):
    return assess_vnic_perimeter(fixture(**changes))


def test_correct_nsg_candidate_is_never_external_approval():
    r=report()
    assert r.mode == "OCI_VNIC_NSG_READ_ONLY_OBSERVATION"
    assert r.instance_running is True
    assert r.public_ipv4_present is True
    assert r.attached_nsg_count == 1
    assert r.public_ipv4_443_ingress_candidate is True
    assert not r.public_ssh_ingress_review
    assert not r.public_database_ingress_review
    assert r.blockers == (
        "OCI_SECURITY_LIST_EFFECTIVE_PATH_NOT_ATTESTED_BY_NSG",
        "OCI_HOST_FIREWALL_NOT_ATTESTED",
        "OCI_PUBLIC_TLS_AND_BACKEND_NOT_ATTESTED",
        "OCI_AUTH_DB_RLS_AND_RESTORE_NOT_ATTESTED",
    )
    for field in (
        "authenticated_oci_read_declared", "external_firewall_verified",
        "subnet_security_lists_verified_by_this_probe",
        "host_firewall_verified", "public_dns_tls_verified",
        "backend_health_verified", "database_rls_verified",
        "deployment_authorized", "real_user_activation_authorized",
        "real_pix_authorized", "cloud_mutations_performed",
    ):
        assert getattr(r,field) is False


@pytest.mark.parametrize("state",["STOPPED","STOPPING","PROVISIONING","STARTING"])
def test_vm_not_running_keeps_blocker(state):
    x=report(instance_lifecycle=state)
    assert not x.instance_running
    assert "OCI_STAGING_INSTANCE_NOT_RUNNING" in x.blockers


@pytest.mark.parametrize("state",["PROVISIONING"])
def test_vnic_not_available_blocks(state):
    r=report(vnic_lifecycle=state)
    assert "OCI_PRIMARY_VNIC_NOT_AVAILABLE" in r.blockers


def test_no_public_ip_or_nsg_is_not_a_clean_perimeter():
    r=report(public_ipv4=None,nsg_rules=())
    assert not r.public_ipv4_present
    assert not r.public_ipv4_443_ingress_candidate
    assert "OCI_PUBLIC_IPV4_MISSING_OR_PROXY_ARCHITECTURE_REQUIRED" in r.blockers
    assert "OCI_NSG_ATTACHMENT_MISSING" in r.blockers
    assert "OCI_NSG_PUBLIC_IPV4_443_NOT_OBSERVED" in r.blockers


@pytest.mark.parametrize("address",[
    "127.0.0.1","10.0.0.10","169.254.169.254","192.168.0.3",
    "100.100.100.200","0.0.0.0","::1","2001:db8::1",
    "bad","93.184.215.14:443",False,
])
def test_public_ip_must_not_be_local_or_invalid(address):
    with pytest.raises(PerimeterReadOnlyBlocked):
        report(public_ipv4=address)


@pytest.mark.parametrize("bad",[
    {"region":"us-ashburn-1"},
    {"instance_lifecycle":"TERMINATED"},
    {"instance_lifecycle":None},
    {"staging_compartment_confirmed":False},
    {"instance_compartment_confirmed":1},
    {"instance_compartment_confirmed":False},
    {"subnet_name":"Default Subnet"},
    {"vcn_name":"Another VCN"},
    {"vnic_lifecycle":"TERMINATED"},
    {"primary_vnic":False},
    {"primary_vnic":1},
    {"nsg_rules":[]},
    {"nsg_rules":((ingress(),),)*17},
    {"nsg_rules":([ingress()],)},
    {"nsg_rules":((ingress(),)*1001,)},
])
def test_scope_or_schema_inconsistent_denied(bad):
    with pytest.raises(PerimeterReadOnlyBlocked):
        report(**bad)


@pytest.mark.parametrize("rule",[
    ingress(low=22,high=22),
    ingress(low=1,high=65535),
    ingress(source="8.8.8.8/32",low=22,high=22),
    ingress(protocol="all",tcp=False),
    ingress(protocol="6",tcp=False),
    ingress(source="::/0",low=22,high=22),
])
def test_public_ssh_ingress_requires_review(rule):
    r=report(nsg_rules=((ingress(),rule),))
    assert r.public_ssh_ingress_review
    assert "OCI_NSG_PUBLIC_SSH_REVIEW_REQUIRED" in r.blockers


@pytest.mark.parametrize("rule",[
    ingress(low=5432,high=5432),
    ingress(low=5433,high=5433),
    ingress(low=22,high=6000),
    ingress(source="8.8.8.8/32",low=5432,high=5433),
    ingress(protocol="all",tcp=False),
    ingress(protocol="6",tcp=False),
])
def test_public_postgres_exposure_requires_review(rule):
    r=report(nsg_rules=((ingress(),rule),))
    assert r.public_database_ingress_review
    assert "OCI_NSG_PUBLIC_POSTGRESQL_REVIEW_REQUIRED" in r.blockers


@pytest.mark.parametrize("rule",[
    ingress(source="10.0.0.0/8"),
    ingress(source="8.8.8.8/32"),
    ingress(source="::/0"),
    ingress(low=80,high=80),
])
def test_443_rule_not_globally_ipv4_open_is_not_public_ipv4_candidate(rule):
    r=report(nsg_rules=((rule,),))
    assert not r.public_ipv4_443_ingress_candidate
    assert "OCI_NSG_PUBLIC_IPV4_443_NOT_OBSERVED" in r.blockers


def test_internal_nsg_source_does_not_become_public_risk():
    internal=ingress(source="ocid1.networksecuritygroup.oc1..synthetic",
                     source_type="NETWORK_SECURITY_GROUP",
                     protocol="all",tcp=False)
    r=report(nsg_rules=((ingress(),internal),))
    assert r.public_ipv4_443_ingress_candidate
    assert not r.public_ssh_ingress_review
    assert not r.public_database_ingress_review


@pytest.mark.parametrize("bad",[
    {"direction":"EGRESS"},
    {"direction":None},
    {"source_type":"SERVICE_CIDR_BLOCK"},
    {"source_type":None},
    {"source":"not-a-cidr"},
    {"source":"10.0.0.1/8"},
    {"protocol":"17"},
    {"protocol":1},
    {"tcp_options":{"destination_port_range":{"min":0,"max":443}}},
    {"tcp_options":{"destination_port_range":{"min":443,"max":65536}}},
    {"tcp_options":{"destination_port_range":{"min":True,"max":443}}},
    {"tcp_options":{"destination_port_range":{"min":444,"max":443}}},
    {"tcp_options":{"destination_port_range":{"min":443}}},
    {"tcp_options":"443"},
])
def test_untrusted_nsg_rule_fails_closed(bad):
    changed={**ingress(),**bad}
    with pytest.raises(PerimeterReadOnlyBlocked):
        report(nsg_rules=((changed,),))


def test_multiple_nsgs_not_launder_broad_exposure():
    r=report(nsg_rules=(
        (ingress(source="10.0.0.0/8",low=22,high=22),),
        (ingress(),ingress(low=5433,high=5433)),
        (ingress(source="1.1.1.1/32",low=22,high=22),),
    ))
    assert r.attached_nsg_count==3
    assert r.public_ipv4_443_ingress_candidate
    assert r.public_database_ingress_review
    assert r.public_ssh_ingress_review


def test_syntax_only_no_live_cloud_calls_without_explicit_approval(tmp_path):
    root=Path(__file__).resolve().parents[2]
    cmd=[sys.executable,str(
        root/"backend/scripts/aistudio_oci_vnic_nsg_readonly.py")]
    env={**os.environ,"HOME":str(tmp_path),"PYTHONPATH":str(root/"backend")}
    offline=subprocess.run(cmd+["offline"],env=env,capture_output=True,text=True,
                           timeout=10,check=False)
    assert offline.returncode==0
    assert "M38249_MODE=OFFLINE_NO_OCI_CONNECTION" in offline.stdout
    assert "M38249_PRODUCTION=BLOCKED" in offline.stdout
    for args in (["live"],["live","NO"],["offline","AUTHORIZE_OCI_VNIC_READ_ONLY"]):
        out=subprocess.run(cmd+args,env=env,capture_output=True,text=True,
                           timeout=10,check=False)
        assert out.returncode==2
        assert "M38249_STATUS=READ_ONLY_OBSERVATION" not in out.stdout


def test_sdk_collector_has_only_exact_reads_and_redacts():
    root=Path(__file__).resolve().parents[2]
    src=(root/"backend/scripts/aistudio_oci_vnic_nsg_readonly.py").read_text()
    for query in (
        "get_compartment(","get_instance(","list_vnic_attachments(",
        "get_vnic(","get_subnet(","get_vcn(",
        "get_network_security_group(",
        "list_network_security_group_security_rules(",
        'args.approval != "AUTHORIZE_OCI_VNIC_READ_ONLY"',
        "opc-next-page",
    ):
        assert query in src
    for forbidden in (
        "create_instance(","launch_instance(","update_vnic(",
        "update_network_security_group(","delete_network_security_group(",
        "change_instance_compartment(","secret-bundle",
        "get_secret_bundle(","oci.vault.VaultsClient(",
        "INSERT INTO","UPDATE public.",
        "print(instance_id","print(compartment_id","print(vnic.public_ip",
    ):
        assert forbidden not in src


def test_pure_policy_is_separate_from_cloud_reader():
    root=Path(__file__).resolve().parents[2]
    src=(root/"backend/app/oci_vnic_perimeter_readonly.py").read_text()
    for forbidden in (
        "import oci","OCI_CLI_CONFIG_FILE","get_secret_bundle(",
        "requests.","subprocess.","socket.create_connection",
        "UPDATE public.","INSERT INTO","os.environ",
    ):
        assert forbidden not in src
