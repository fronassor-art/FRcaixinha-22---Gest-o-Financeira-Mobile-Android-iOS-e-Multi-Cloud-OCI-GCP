# AI Studio M2600: isolated OCI staging network, declaration ONLY.
# Explicit terraform apply requires separate owner authorization.
terraform {
  required_version = ">= 1.6.0"
  required_providers {
    oci = {
      source = "oracle/oci"
      version = ">= 6.0, < 9.0"
    }
  }
}

variable "compartment_id" {
  type = string
  description = "Dedicated OCI staging compartment OCID"
}
variable "region" {
  type = string
  description = "OCI region approved for staging"
}
provider "oci" {
  region = var.region
}
resource "oci_core_vcn" "staging" {
  compartment_id = var.compartment_id
  cidr_blocks = ["10.77.0.0/16"]
  display_name = "frcaixinha-aistudio-staging"
  dns_label = "frcastage"
  lifecycle {
    prevent_destroy = true
  }
}
resource "oci_core_security_list" "deny_all" {
  compartment_id = var.compartment_id
  vcn_id = oci_core_vcn.staging.id
  display_name = "frcaixinha-staging-deny-all"
  # No ingress/egress entries (explicit deny-all).
}
resource "oci_core_route_table" "isolated" {
  compartment_id = var.compartment_id
  vcn_id = oci_core_vcn.staging.id
  display_name = "frcaixinha-staging-no-internet-routes"
  # No route rules, NAT or Internet gateway.
}
resource "oci_core_subnet" "private" {
  compartment_id = var.compartment_id
  vcn_id = oci_core_vcn.staging.id
  cidr_block = "10.77.10.0/24"
  display_name = "frcaixinha-private-staging"
  dns_label = "privsvc"
  prohibit_public_ip_on_vnic = true
  security_list_ids = [oci_core_security_list.deny_all.id]
  route_table_id = oci_core_route_table.isolated.id
}
output "private_subnet_id" {
  value = oci_core_subnet.private.id
}
