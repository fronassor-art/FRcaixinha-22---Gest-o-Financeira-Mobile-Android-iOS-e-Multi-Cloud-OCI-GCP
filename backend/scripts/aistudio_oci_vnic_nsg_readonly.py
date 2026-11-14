#!/usr/bin/env python3
"""M38210–M38249: opt-in OCI VM/VNIC/NSG READ-ONLY authenticated snapshot.

Never logs public IPs, OCIDs, account data, policy rules or SDK exceptions.
All OCI calls below are GET or LIST only. No provisioning, secret access,
API deployment, firewall updates, database writes or provider activation.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))

from app.oci_vnic_perimeter_readonly import (
    PerimeterReadOnlyBlocked, VnicPerimeterSnapshot, assess_vnic_perimeter,
)
from aistudio_provider_intake import _default_file, read_file


def _blocked(reason: str) -> PerimeterReadOnlyBlocked:
    return PerimeterReadOnlyBlocked(reason)


def _live_snapshot() -> VnicPerimeterSnapshot:
    public = read_file(_default_file())["public_inputs"]
    required = ("OCI_REGION", "OCI_COMPARTMENT_OCID", "OCI_INSTANCE_OCID")
    if not all(key in public for key in required):
        raise _blocked("M38210_PUBLIC_OCI_IDENTIFIERS_NOT_CONFIGURED")
    if public["OCI_REGION"] != "sa-saopaulo-1":
        raise _blocked("M38210_OCI_REGION_MISMATCH")

    # Import only after the opt-in action + public intake were validated.
    import oci
    cfg = oci.config.from_file(
        file_location=str(Path(os.environ.get(
            "OCI_CLI_CONFIG_FILE", "~/.oci/config",
        )).expanduser()),
        profile_name=os.environ.get("OCI_CLI_PROFILE", "DEFAULT"),
    )
    if cfg.get("region") != "sa-saopaulo-1":
        raise _blocked("M38210_OCI_PROFILE_REGION_MISMATCH")

    compartment_id = public["OCI_COMPARTMENT_OCID"]
    instance_id = public["OCI_INSTANCE_OCID"]
    identity = oci.identity.IdentityClient(
        cfg, timeout=(5, 25), retry_strategy=oci.retry.NoneRetryStrategy(),
    )
    compartment = identity.get_compartment(compartment_id).data
    if (
        compartment.id != compartment_id
        or compartment.name != "fr-finance-staging"
        or compartment.lifecycle_state != "ACTIVE"
        or compartment.compartment_id != cfg.get("tenancy")
    ):
        raise _blocked("M38210_STAGING_COMPARTMENT_NOT_ATTESTED")

    compute = oci.core.ComputeClient(
        cfg, timeout=(5, 25), retry_strategy=oci.retry.NoneRetryStrategy(),
    )
    network = oci.core.VirtualNetworkClient(
        cfg, timeout=(5, 25), retry_strategy=oci.retry.NoneRetryStrategy(),
    )
    instance = compute.get_instance(instance_id).data
    if instance.id != instance_id or instance.compartment_id != compartment_id:
        raise _blocked("M38210_INSTANCE_COMPARTMENT_NOT_MATCHED")
    state = instance.lifecycle_state
    if state not in ("RUNNING", "STARTING", "PROVISIONING", "STOPPED", "STOPPING"):
        raise _blocked("M38210_INSTANCE_LIFECYCLE_NOT_ATTESTED")

    attachments = compute.list_vnic_attachments(
        compartment_id=compartment_id, instance_id=instance_id, limit=100,
    )
    if (
        attachments.headers.get("opc-next-page")
        or type(attachments.data) is not list
        or not 1 <= len(attachments.data) <= 16
    ):
        raise _blocked("M38210_INSTANCE_ATTACHMENTS_INCOMPLETE")

    primary: list[tuple[object, object]] = []
    for attachment in attachments.data:
        if attachment.instance_id != instance_id:
            raise _blocked("M38210_ATTACHMENT_INSTANCE_MISMATCH")
        if attachment.lifecycle_state != "ATTACHED":
            continue
        vnic = network.get_vnic(attachment.vnic_id).data
        if vnic.id != attachment.vnic_id:
            raise _blocked("M38210_VNIC_ID_MISMATCH")
        if vnic.is_primary is True:
            primary.append((attachment, vnic))
    if len(primary) != 1:
        raise _blocked("M38210_PRIMARY_VNIC_NOT_UNIQUE")

    _, vnic = primary[0]
    subnet = network.get_subnet(vnic.subnet_id).data
    vcn = network.get_vcn(subnet.vcn_id).data
    if (
        subnet.id != vnic.subnet_id
        or subnet.display_name != "FR Finance"
        or subnet.lifecycle_state != "AVAILABLE"
        or vcn.id != subnet.vcn_id
        or vcn.display_name != "FR Finance"
        or vcn.lifecycle_state != "AVAILABLE"
    ):
        raise _blocked("M38210_VNIC_SUBNET_VCN_MISMATCH")

    nsg_ids = vnic.nsg_ids
    if (
        type(nsg_ids) is not list or len(nsg_ids) > 16
        or len(set(nsg_ids)) != len(nsg_ids)
    ):
        raise _blocked("M38210_ATTACHED_NSG_LIST_INVALID")

    groups: list[tuple[dict, ...]] = []
    for nsg_id in nsg_ids:
        nsg = network.get_network_security_group(nsg_id).data
        if nsg.id != nsg_id or nsg.vcn_id != vcn.id or nsg.lifecycle_state != "AVAILABLE":
            raise _blocked("M38210_NSG_SCOPE_MISMATCH")
        response = network.list_network_security_group_security_rules(
            nsg_id, direction="INGRESS", limit=1000,
        )
        if (
            response.headers.get("opc-next-page")
            or type(response.data) is not list
            or len(response.data) > 1000
        ):
            raise _blocked("M38210_NSG_RULES_PAGINATION_INCOMPLETE")
        groups.append(tuple(oci.util.to_dict(rule) for rule in response.data))

    return VnicPerimeterSnapshot(
        region="sa-saopaulo-1", instance_lifecycle=state,
        staging_compartment_confirmed=True,
        instance_compartment_confirmed=True,
        subnet_name=subnet.display_name, vcn_name=vcn.display_name,
        vnic_lifecycle=vnic.lifecycle_state, primary_vnic=vnic.is_primary,
        public_ipv4=vnic.public_ip, nsg_rules=tuple(groups),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FR Finance OCI VNIC/NSG status. Only OFFLINE or explicit authorized READ-ONLY.",
    )
    parser.add_argument("action", nargs="?", choices=("offline", "live"), default="offline")
    parser.add_argument("approval", nargs="?", default=None)
    args = parser.parse_args(argv)

    if args.action == "offline":
        if args.approval is not None:
            print("M38249_STATUS=BLOCKED_INVALID_ACTION")
            return 2
        print("=== FR FINANCE M38210-M38249 — OCI VNIC/NSG ===")
        print("M38249_MODE=OFFLINE_NO_OCI_CONNECTION")
        print("M38249_STAGING_VNIC=NOT_QUERIED")
        print("M38249_NSG_443=NOT_QUERIED")
        print("M38249_NETWORK_SECURITY=NOT_ATTESTED")
        print("M38249_DB_ORIGINAL=UNTOUCHED")
        print("M38249_CLOUD_MUTATIONS=NONE")
        print("M38249_PIX_REAL=OFF")
        print("M38249_PRODUCTION=BLOCKED")
        return 0

    if args.approval != "AUTHORIZE_OCI_VNIC_READ_ONLY":
        print("M38249_STATUS=BLOCKED_OPERATOR_APPROVAL_REQUIRED")
        return 2

    try:
        snapshot = _live_snapshot()
        report = replace(assess_vnic_perimeter(snapshot),
                         authenticated_oci_read_declared=True)
    except PerimeterReadOnlyBlocked as exc:
        # Codes above are a fixed, non-sensitive local allowlist.
        print("M38249_STATUS=BLOCKED")
        print("M38249_CAUSE=" + str(exc))
        print("M38249_CLOUD_MUTATIONS=NONE")
        print("M38249_PRODUCTION=BLOCKED")
        return 2
    except Exception:
        # Never print OCI SDK exceptions: may disclose tenancy/OCID/policy.
        print("M38249_STATUS=BLOCKED_REMOTE_OR_RUNTIME_READ")
        print("M38249_CLOUD_MUTATIONS=NONE")
        print("M38249_PRODUCTION=BLOCKED")
        return 2

    print("=== FR FINANCE M38249 — OCI VNIC NSG LIVE READ ONLY ===")
    print("M38249_STATUS=READ_ONLY_OBSERVATION")
    print("M38249_INSTANCE_RUNNING=" + str(report.instance_running).upper())
    print("M38249_PUBLIC_IPV4_PRESENT=" + str(report.public_ipv4_present).upper())
    print("M38249_NSG_COUNT=" + str(report.attached_nsg_count))
    print("M38249_NSG_443_IPV4_CANDIDATE=" +
          str(report.public_ipv4_443_ingress_candidate).upper())
    print("M38249_NSG_PUBLIC_SSH_REVIEW=" +
          str(report.public_ssh_ingress_review).upper())
    print("M38249_NSG_PUBLIC_DB_REVIEW=" +
          str(report.public_database_ingress_review).upper())
    for blocker in report.blockers:
        print("M38249_BLOCKER=" + blocker)
    print("M38249_HOST_FIREWALL=NOT_ATTESTED")
    print("M38249_PUBLIC_TLS=NOT_ATTESTED")
    print("M38249_DATABASE_RLS=NOT_ATTESTED")
    print("M38249_CLOUD_MUTATIONS=NONE")
    print("M38249_EMAIL_REAL=OFF")
    print("M38249_PIX_REAL=OFF")
    print("M38249_REAL_ACTIVATION=OFF")
    print("M38249_PRODUCTION=BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
