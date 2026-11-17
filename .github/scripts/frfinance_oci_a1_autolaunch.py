#!/usr/bin/env python3
"""FR Finance OCI A1 GitHub runner. Fail-closed; no credentials in source."""
import ipaddress
import os
import sys
import tempfile
from datetime import datetime, timezone
import oci

REGION = "sa-saopaulo-1"
NAME = "fr-finance-a1-always-free"
SHAPE = "VM.Standard.A1.Flex"
IMAGE = "Canonical-Ubuntu-24.04-aarch64-2026.10.27-0"

def log(s):
    print(datetime.now(timezone.utc).isoformat(), s, flush=True)

def require(cond, message):
    if not cond:
        raise RuntimeError(message)

def items(fn, *args, **kwargs):
    return oci.pagination.list_call_get_all_results(fn, *args, **kwargs).data

def main():
    required = ("FRF_OCI_USER_OCID", "FRF_OCI_TENANCY_OCID", "FRF_OCI_FINGERPRINT",
                "FRF_OCI_PRIVATE_KEY_PEM", "FRF_OCI_SSH_PUBLIC_KEY")
    require(all(os.environ.get(k) for k in required), "MISSING_REQUIRED_SECRETS")
    key = os.environ["FRF_OCI_SSH_PUBLIC_KEY"].strip()
    require(key.startswith("ssh-ed25519 ") and len(key.split()) in (2, 3), "INVALID_SSH_PUBLIC_KEY")
    require(os.environ.get("FRF_OCI_REGION", REGION) == REGION, "WRONG_REGION")
    with tempfile.TemporaryDirectory(prefix="frfinance-oci-") as directory:
        path = os.path.join(directory, "oci.pem")
        with open(path, "w", encoding="utf-8") as f:
            f.write(os.environ["FRF_OCI_PRIVATE_KEY_PEM"])
        os.chmod(path, 0o600)
        cfg = {"user": os.environ["FRF_OCI_USER_OCID"],
               "tenancy": os.environ["FRF_OCI_TENANCY_OCID"],
               "fingerprint": os.environ["FRF_OCI_FINGERPRINT"],
               "key_file": path, "region": REGION}
        oci.config.validate_config(cfg)
        root = cfg["tenancy"]
        iam = oci.identity.IdentityClient(cfg)
        compute = oci.core.ComputeClient(cfg)
        network = oci.core.VirtualNetworkClient(cfg)
        block = oci.core.BlockstorageClient(cfg)
        osp = oci.osp_gateway.SubscriptionServiceClient(cfg)
        subscription = osp.list_subscriptions(REGION, root).data
        plans = subscription if isinstance(subscription, list) else getattr(subscription, "items", [])
        require([getattr(p, "plan_type", "") for p in plans] == ["FREE_TIER"], "FREE_TIER_NOT_VERIFIED")
        compartments = [root] + [c.id for c in items(iam.list_compartments, root,
                        compartment_id_in_subtree=True, access_level="ACCESSIBLE")
                        if c.lifecycle_state == "ACTIVE"]
        for cid in compartments:
            existing = items(compute.list_instances, cid)
            for instance in existing:
                if instance.display_name == NAME and instance.lifecycle_state != "TERMINATED":
                    log("VM_FOUND=YES STATE=" + instance.lifecycle_state)
                    return
            require(not any(v.lifecycle_state != "TERMINATED" for v in existing), "OTHER_INSTANCE_REVIEW_REQUIRED")
            require(not any(v.lifecycle_state != "TERMINATED" for v in
                    items(block.list_volumes, compartment_id=cid)), "BLOCK_VOLUME_REVIEW_REQUIRED")
            require(not any(v.lifecycle_state != "TERMINATED" for v in
                    items(block.list_boot_volumes, compartment_id=cid)), "BOOT_VOLUME_REVIEW_REQUIRED")
        ads = items(iam.list_availability_domains, root)
        require(len(ads) == 1 and ads[0].name.endswith("SA-SAOPAULO-1-AD-1"), "AD_REVIEW_REQUIRED")
        shapes = [s for s in items(compute.list_shapes, root, availability_domain=ads[0].name)
                  if s.shape == SHAPE and s.is_flexible]
        require(len(shapes) == 1, "A1_SHAPE_UNAVAILABLE")
        vcns = [v for v in items(network.list_vcns, root)
                if v.display_name == "FR Finance" and v.lifecycle_state == "AVAILABLE"]
        require(len(vcns) == 1, "VCN_REVIEW_REQUIRED")
        subnets = [s for s in items(network.list_subnets, root, vcn_id=vcns[0].id)
                   if s.display_name == "FR Finance" and s.lifecycle_state == "AVAILABLE"
                   and not s.prohibit_public_ip_on_vnic]
        require(len(subnets) == 1, "SUBNET_REVIEW_REQUIRED")
        subnet = subnets[0]
        gateways = {g.id for g in items(network.list_internet_gateways, root, vcn_id=vcns[0].id)
                    if g.is_enabled}
        route = network.get_route_table(subnet.route_table_id).data
        require(any(r.destination == "0.0.0.0/0" and r.network_entity_id in gateways
                    for r in (route.route_rules or [])), "ROUTE_REVIEW_REQUIRED")
        sources = []
        for sid in subnet.security_list_ids or []:
            for rule in network.get_security_list(sid).data.ingress_security_rules or []:
                if str(rule.protocol) != "6":
                    continue
                rng = getattr(getattr(rule, "tcp_options", None), "destination_port_range", None)
                if rng is None or rng.min <= 22 <= rng.max:
                    require(getattr(rule, "source_type", "CIDR_BLOCK") == "CIDR_BLOCK", "SSH_SOURCE_REVIEW_REQUIRED")
                    sources.append(ipaddress.ip_network(rule.source, strict=False))
        require(bool(sources) and all(n.version == 4 and n.prefixlen == 32 for n in sources),
                "SSH22_MUST_BE_IPV4_32")
        images = [i for i in items(compute.list_images, root,
                  operating_system="Canonical Ubuntu", shape=SHAPE)
                  if i.display_name == IMAGE and i.lifecycle_state == "AVAILABLE"]
        require(len(images) == 1, "PINNED_IMAGE_UNAVAILABLE")
        log("PREFLIGHT=PASS REGION=SAO_PAULO PLAN=FREE_TIER SSH22=IPV4_32")
        if os.environ.get("FRF_OCI_LAUNCH_ENABLED") != "true":
            log("DRY_RUN_ONLY=YES LAUNCH_INSTANCE=NOT_CALLED")
            return
        details = oci.core.models.LaunchInstanceDetails(
            availability_domain=ads[0].name, compartment_id=root, display_name=NAME,
            shape=SHAPE, shape_config=oci.core.models.LaunchInstanceShapeConfigDetails(
                ocpus=2, memory_in_gbs=12),
            source_details=oci.core.models.InstanceSourceViaImageDetails(
                source_type="image", image_id=images[0].id,
                boot_volume_size_in_gbs=50, boot_volume_vpus_per_gb=10),
            create_vnic_details=oci.core.models.CreateVnicDetails(
                subnet_id=subnet.id, assign_public_ip=True),
            metadata={"ssh_authorized_keys": key})
        # A transport failure is ambiguous. Never automatically retry the same run.
        try:
            response = compute.launch_instance(
                details, opc_retry_token=os.environ["FRF_OCI_LAUNCH_TOKEN"],
                retry_strategy=oci.retry.NoneRetryStrategy())
        except oci.exceptions.ServiceError as exc:
            msg = (exc.message or "").lower()
            if exc.code in ("InternalError", "OutOfHostCapacity") and (
                "out of host capacity" in msg or "outofhostcapacity" in msg):
                log("OUT_OF_HOST_CAPACITY=CONFIRMED")
                return
            log("LAUNCH_RESULT=UNCERTAIN MANUAL_REVIEW_REQUIRED=YES")
            raise RuntimeError("OCI_SERVICE_ERROR_REVIEW_REQUIRED") from None
        except Exception:
            log("LAUNCH_RESULT=UNCERTAIN MANUAL_REVIEW_REQUIRED=YES")
            raise RuntimeError("OCI_TRANSPORT_REVIEW_REQUIRED") from None
        log("VM_LAUNCH_ACCEPTED=YES STATE=" + response.data.lifecycle_state)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("BLOCKED=" + (str(exc)[:100] if isinstance(exc, RuntimeError) else type(exc).__name__))
        sys.exit(1)
