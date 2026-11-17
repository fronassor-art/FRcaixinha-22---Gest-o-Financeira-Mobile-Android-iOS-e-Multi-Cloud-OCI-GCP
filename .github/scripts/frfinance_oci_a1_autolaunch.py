#!/usr/bin/env python3
"""FR Finance OCI A1 GitHub runner. Fail closed; no credentials in source."""
import ipaddress
import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import oci

REGION = "sa-saopaulo-1"
NAME = "fr-finance-a1-always-free"
SHAPE = "VM.Standard.A1.Flex"
IMAGE = "Canonical-Ubuntu-24.04-aarch64-2026.10.27-0"
PENDING_TITLE = "FR Finance — OCI A1 launch pending reconciliation"
ACCEPTED_TITLE = "FR Finance — OCI A1 launch accepted"
RETRY_WINDOW = timedelta(hours=23)


def log(message):
    print(datetime.now(timezone.utc).isoformat(), message, flush=True)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def items(fn, *args, **kwargs):
    return oci.pagination.list_call_get_all_results(fn, *args, **kwargs).data


def gh(*args):
    env = os.environ.copy()
    require(bool(env.get("GH_TOKEN")), "GITHUB_TOKEN_MISSING")
    result = subprocess.run(
        ["gh", *args], text=True, capture_output=True, timeout=30, env=env, check=False
    )
    require(result.returncode == 0, "GITHUB_GUARD_UNAVAILABLE")
    return result.stdout.strip()


def find_guard():
    # Closed accepted issues remain a permanent fence after VM termination.
    result = gh(
        "issue", "list", "--state", "all", "--limit", "10000",
        "--json", "number,title,body,state,url"
    )
    guards = [
        issue for issue in json.loads(result)
        if issue["title"] == ACCEPTED_TITLE
        or (issue["title"] == PENDING_TITLE and issue["state"] == "OPEN")
    ]
    require(len(guards) <= 1, "MULTIPLE_LAUNCH_GUARDS_REVIEW_REQUIRED")
    return guards[0] if guards else None


def open_guard():
    require(find_guard() is None, "PREVIOUS_LAUNCH_REQUIRES_RECONCILIATION")
    # The token is durable before calling Oracle. An uncertain issue create blocks launch.
    state = {
        "retry_token": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    url = gh("issue", "create", "--title", PENDING_TITLE,
             "--body", json.dumps(state, sort_keys=True))
    require(url.startswith("https://github.com/"), "GITHUB_GUARD_CREATION_NOT_CONFIRMED")
    return {"url": url, "title": PENDING_TITLE, "state": "OPEN",
            "body": json.dumps(state)}


def retry_token(guard):
    require(guard["title"] == PENDING_TITLE and guard["state"] == "OPEN",
            "LAUNCH_ALREADY_ACCEPTED")
    try:
        state = json.loads(guard["body"])
        created = datetime.fromisoformat(state["created_at"])
        token = state["retry_token"]
    except (KeyError, ValueError, TypeError):
        raise RuntimeError("LEGACY_GUARD_MANUAL_REVIEW_REQUIRED") from None
    require(
        created.tzinfo is not None
        and timedelta(0) <= datetime.now(timezone.utc) - created < RETRY_WINDOW,
        "RETRY_TOKEN_WINDOW_EXPIRED_MANUAL_REVIEW_REQUIRED",
    )
    require(isinstance(token, str) and len(token) == 32
            and all(c in "0123456789abcdef" for c in token), "INVALID_RETRY_TOKEN")
    return token


def close_guard(guard):
    gh("issue", "close", guard["url"], "--comment",
       "Oracle confirmed OUT_OF_HOST_CAPACITY; no launch accepted on this attempt.")


def mark_accepted(guard, state):
    gh("issue", "edit", guard["url"], "--title", ACCEPTED_TITLE,
       "--body", "OCI accepted the A1 launch request. State: " + state +
       ". Scheduled runs only reconcile; no further launch is permitted.")


def disable_schedule():
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    require(repo.count("/") == 1, "GITHUB_REPOSITORY_MISSING")
    gh("api", "-X", "PUT", "repos/" + repo +
       "/actions/workflows/frfinance-oci-a1-autolaunch.yml/disable")
    log("WORKFLOW_DISABLED=YES")


def reconcile_existing(guard, instances):
    named = [vm for vm in instances
             if vm.display_name == NAME and vm.lifecycle_state != "TERMINATED"]
    require(len(named) <= 1, "DUPLICATE_NAMED_INSTANCES_REVIEW_REQUIRED")
    if not named:
        return False
    log("VM_FOUND=YES STATE=" + named[0].lifecycle_state)
    if guard and guard["title"] == PENDING_TITLE:
        mark_accepted(guard, named[0].lifecycle_state)
    if os.environ.get("GITHUB_EVENT_NAME") == "schedule":
        disable_schedule()
    return True


def verify_home_region(iam, tenancy):
    regions = items(iam.list_region_subscriptions, tenancy)
    homes = [region for region in regions if region.is_home_region]
    require(len(homes) == 1 and homes[0].region_name == REGION
            and homes[0].status == "READY", "HOME_REGION_NOT_VERIFIED")


def main():
    required = ("FRF_OCI_USER_OCID", "FRF_OCI_TENANCY_OCID",
                "FRF_OCI_FINGERPRINT", "FRF_OCI_PRIVATE_KEY_PEM")
    require(all(os.environ.get(k) for k in required), "MISSING_REQUIRED_SECRETS")
    require(os.environ.get("FRF_OCI_REGION", REGION) == REGION, "WRONG_REGION")
    with tempfile.TemporaryDirectory(prefix="frfinance-oci-") as directory:
        path = os.path.join(directory, "oci.pem")
        with open(path, "w", encoding="utf-8") as file:
            file.write(os.environ["FRF_OCI_PRIVATE_KEY_PEM"])
        os.chmod(path, 0o600)
        cfg = {
            "user": os.environ["FRF_OCI_USER_OCID"],
            "tenancy": os.environ["FRF_OCI_TENANCY_OCID"],
            "fingerprint": os.environ["FRF_OCI_FINGERPRINT"],
            "key_file": path,
            "region": REGION,
        }
        oci.config.validate_config(cfg)
        root = cfg["tenancy"]
        iam = oci.identity.IdentityClient(cfg)
        compute = oci.core.ComputeClient(cfg)
        network = oci.core.VirtualNetworkClient(cfg)
        block = oci.core.BlockstorageClient(cfg)
        osp = oci.osp_gateway.SubscriptionServiceClient(cfg)
        subscription = osp.list_subscriptions(REGION, root).data
        plans = subscription if isinstance(subscription, list) else getattr(subscription, "items", [])
        require([getattr(plan, "plan_type", "") for plan in plans] == ["FREE_TIER"],
                "FREE_TIER_NOT_VERIFIED")
        verify_home_region(iam, root)

        compartments = [root] + [
            compartment.id for compartment in items(
                iam.list_compartments, root, compartment_id_in_subtree=True,
                access_level="ACCESSIBLE"
            ) if compartment.lifecycle_state == "ACTIVE"
        ]
        instances = []
        for cid in compartments:
            instances.extend(items(compute.list_instances, cid))
        guard = find_guard()
        if reconcile_existing(guard, instances):
            return
        if guard and guard["title"] == ACCEPTED_TITLE:
            log("LAUNCH_ALREADY_ACCEPTED=YES MANUAL_REVIEW_IF_VM_ABSENT=YES")
            return
        require(not any(vm.lifecycle_state != "TERMINATED" for vm in instances),
                "OTHER_INSTANCE_REVIEW_REQUIRED")
        for cid in compartments:
            require(not any(volume.lifecycle_state != "TERMINATED" for volume in
                            items(block.list_volumes, compartment_id=cid)),
                    "BLOCK_VOLUME_REVIEW_REQUIRED")
            require(not any(volume.lifecycle_state != "TERMINATED" for volume in
                            items(block.list_boot_volumes, compartment_id=cid)),
                    "BOOT_VOLUME_REVIEW_REQUIRED")
        ads = items(iam.list_availability_domains, root)
        require(len(ads) == 1 and ads[0].name.endswith("SA-SAOPAULO-1-AD-1"),
                "AD_REVIEW_REQUIRED")
        shapes = [shape for shape in items(compute.list_shapes, root,
                  availability_domain=ads[0].name)
                  if shape.shape == SHAPE and shape.is_flexible]
        require(len(shapes) == 1, "A1_SHAPE_UNAVAILABLE")
        vcns = [vcn for vcn in items(network.list_vcns, root)
                if vcn.display_name == "FR Finance" and vcn.lifecycle_state == "AVAILABLE"]
        require(len(vcns) == 1, "VCN_REVIEW_REQUIRED")
        subnets = [subnet for subnet in items(network.list_subnets, root, vcn_id=vcns[0].id)
                   if subnet.display_name == "FR Finance"
                   and subnet.lifecycle_state == "AVAILABLE"
                   and not subnet.prohibit_public_ip_on_vnic]
        require(len(subnets) == 1, "SUBNET_REVIEW_REQUIRED")
        subnet = subnets[0]
        gateways = {gateway.id for gateway in items(
            network.list_internet_gateways, root, vcn_id=vcns[0].id
        ) if gateway.is_enabled}
        route = network.get_route_table(subnet.route_table_id).data
        require(any(rule.destination == "0.0.0.0/0"
                    and rule.network_entity_id in gateways
                    for rule in (route.route_rules or [])), "ROUTE_REVIEW_REQUIRED")
        sources = []
        for sid in subnet.security_list_ids or []:
            for rule in network.get_security_list(sid).data.ingress_security_rules or []:
                if str(rule.protocol) != "6":
                    continue
                rng = getattr(getattr(rule, "tcp_options", None),
                              "destination_port_range", None)
                if rng is None or rng.min <= 22 <= rng.max:
                    require(getattr(rule, "source_type", "CIDR_BLOCK") == "CIDR_BLOCK",
                            "SSH_SOURCE_REVIEW_REQUIRED")
                    sources.append(ipaddress.ip_network(rule.source, strict=False))
        require(bool(sources) and all(source.version == 4 and source.prefixlen == 32
                                      for source in sources), "SSH22_MUST_BE_IPV4_32")
        images = [image for image in items(
            compute.list_images, root, operating_system="Canonical Ubuntu", shape=SHAPE
        ) if image.display_name == IMAGE and image.lifecycle_state == "AVAILABLE"]
        require(len(images) == 1, "PINNED_IMAGE_UNAVAILABLE")
        log("PREFLIGHT=PASS REGION=SAO_PAULO PLAN=FREE_TIER SSH22=IPV4_32")

        if os.environ.get("FRF_OCI_LAUNCH_ENABLED") != "true":
            log("DRY_RUN_ONLY=YES LAUNCH_INSTANCE=NOT_CALLED")
            return
        key = os.environ.get("FRF_OCI_SSH_PUBLIC_KEY", "").strip()
        require(key.startswith("ssh-ed25519 ") and len(key.split()) in (2, 3),
                "INVALID_SSH_PUBLIC_KEY")
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
        if guard is None:
            guard = open_guard()
        else:
            log("PENDING_LAUNCH_RECONCILIATION=YES")
        token = retry_token(guard)
        try:
            response = compute.launch_instance(
                details, opc_retry_token=token,
                retry_strategy=oci.retry.NoneRetryStrategy())
        except oci.exceptions.ServiceError as exc:
            message = (exc.message or "").lower()
            if exc.code in ("InternalError", "OutOfHostCapacity") and (
                "out of host capacity" in message or "outofhostcapacity" in message
            ):
                log("OUT_OF_HOST_CAPACITY=CONFIRMED")
                close_guard(guard)
                return
            log("LAUNCH_RESULT=UNCERTAIN RETRY_SAME_TOKEN=YES")
            raise RuntimeError("OCI_SERVICE_ERROR_REVIEW_REQUIRED") from None
        except Exception:
            log("LAUNCH_RESULT=UNCERTAIN RETRY_SAME_TOKEN=YES")
            raise RuntimeError("OCI_TRANSPORT_REVIEW_REQUIRED") from None
        log("VM_LAUNCH_ACCEPTED=YES STATE=" + response.data.lifecycle_state)
        mark_accepted(guard, response.data.lifecycle_state)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        log("BLOCKED=" + (str(exc)[:100] if isinstance(exc, RuntimeError)
                          else type(exc).__name__))
        sys.exit(1)
