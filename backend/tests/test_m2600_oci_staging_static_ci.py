"""M2600: static OCI network safety check; no actual terraform apply."""
from pathlib import Path

TF = Path(__file__).resolve().parents[2] / "infra/oci/staging/network.tf"


def test_network_declared_private_and_not_deployed():
    text=TF.read_text(encoding="utf-8")
    for required in (
        'resource "oci_core_vcn"', 'resource "oci_core_subnet"',
        'resource "oci_core_security_list"', 'resource "oci_core_route_table"',
        "prohibit_public_ip_on_vnic = true", "prevent_destroy = true",
        "security_list_ids", "route_table_id"
    ):
        assert required in text
    for forbidden in (
        'resource "oci_core_instance"', 'resource "oci_core_internet_gateway"',
        'resource "oci_core_nat_gateway"', 'resource "oci_load_balancer_load_balancer"',
        '0.0.0.0/0', "ingress_security_rules {",
        "egress_security_rules {", "route_rules {", "client_secret",
        "access_token", "private_key"
    ):
        assert forbidden not in text
