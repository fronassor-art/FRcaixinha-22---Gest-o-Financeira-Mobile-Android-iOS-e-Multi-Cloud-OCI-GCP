"""Offline tests for the durable OCI launch guard. No OCI credentials or API calls."""
import importlib.util
import io
import json
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.modules.setdefault("oci", types.ModuleType("oci"))
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "frfinance_oci_a1_autolaunch.py"
spec = importlib.util.spec_from_file_location("frfinance_oci_a1_autolaunch", SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GuardTests(unittest.TestCase):
    def guard(self, age=timedelta(), title=None, state="OPEN"):
        return {
            "title": title or runner.PENDING_TITLE,
            "state": state,
            "url": "https://github.com/example/repo/issues/1",
            "body": json.dumps({
                "created_at": (datetime.now(timezone.utc) - age).isoformat(),
                "retry_token": "a" * 32,
            }),
        }

    def test_pending_retry_uses_persisted_token(self):
        guard = self.guard(age=timedelta(minutes=10))
        self.assertEqual(runner.retry_token(guard), "a" * 32)

    def test_expired_token_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "RETRY_TOKEN_WINDOW_EXPIRED"):
            runner.retry_token(self.guard(age=timedelta(hours=24)))

    def test_legacy_guard_fails_closed(self):
        guard = self.guard()
        guard["body"] = "An OCI A1 launch request is pending."
        with self.assertRaisesRegex(RuntimeError, "LEGACY_GUARD"):
            runner.retry_token(guard)

    def test_accepted_guard_blocks_even_when_closed(self):
        accepted = self.guard(title=runner.ACCEPTED_TITLE, state="CLOSED")
        old_capacity = self.guard(state="CLOSED")
        with patch.object(runner, "gh", return_value=json.dumps([accepted, old_capacity])):
            self.assertEqual(runner.find_guard(), accepted)

    def test_duplicate_guards_fail_closed(self):
        with patch.object(runner, "gh", return_value=json.dumps([
            self.guard(), self.guard(title=runner.ACCEPTED_TITLE)
        ])):
            with self.assertRaisesRegex(RuntimeError, "MULTIPLE_LAUNCH_GUARDS"):
                runner.find_guard()

    def test_guard_created_before_request_with_token(self):
        commands = []
        def fake_gh(*args):
            commands.append(args)
            if args[:2] == ("issue", "list"):
                return "[]"
            return "https://github.com/example/repo/issues/1"
        with patch.object(runner, "gh", side_effect=fake_gh):
            guard = runner.open_guard()
        self.assertEqual(commands[0][:2], ("issue", "list"))
        self.assertEqual(commands[1][:2], ("issue", "create"))
        self.assertEqual(runner.retry_token(guard), json.loads(guard["body"])["retry_token"])

    def test_existing_vm_reconciles_and_disables_schedule(self):
        vm = types.SimpleNamespace(display_name=runner.NAME, lifecycle_state="RUNNING")
        with patch.dict(runner.os.environ, {"GITHUB_EVENT_NAME": "schedule"}):
            with patch.object(runner, "mark_accepted") as accepted:
                with patch.object(runner, "disable_schedule") as disabled:
                    self.assertTrue(runner.reconcile_existing(self.guard(), [vm]))
        accepted.assert_called_once()
        disabled.assert_called_once()

    def test_duplicate_vms_fail_before_any_mutation(self):
        vm = types.SimpleNamespace(display_name=runner.NAME, lifecycle_state="RUNNING")
        with patch.object(runner, "mark_accepted") as accepted:
            with self.assertRaisesRegex(RuntimeError, "DUPLICATE_NAMED_INSTANCES"):
                runner.reconcile_existing(self.guard(), [vm, vm])
        accepted.assert_not_called()


    def test_homologation_preflight_never_calls_launch(self):
        ns = types.SimpleNamespace
        response = lambda data: ns(data=data)
        iam = ns(
            list_compartments=lambda *args, **kwargs: response([]),
            list_availability_domains=lambda *args, **kwargs:
                response([ns(name="SA-SAOPAULO-1-AD-1")]),
        )
        compute = ns(
            list_instances=lambda *args, **kwargs: response([]),
            list_shapes=lambda *args, **kwargs:
                response([ns(shape=runner.SHAPE, is_flexible=True)]),
            list_images=lambda *args, **kwargs:
                response([ns(display_name=runner.IMAGE, lifecycle_state="AVAILABLE", id="image")]),
            launch_instance=lambda *args, **kwargs: self.fail("real launch reached"),
        )
        subnet = ns(
            display_name="FR Finance", lifecycle_state="AVAILABLE",
            prohibit_public_ip_on_vnic=False, id="subnet", route_table_id="route",
            security_list_ids=["security"],
        )
        rule = ns(
            protocol="6", tcp_options=ns(destination_port_range=ns(min=22, max=22)),
            source_type="CIDR_BLOCK", source="203.0.113.7/32",
        )
        network = ns(
            list_vcns=lambda *args, **kwargs:
                response([ns(display_name="FR Finance", lifecycle_state="AVAILABLE", id="vcn")]),
            list_subnets=lambda *args, **kwargs: response([subnet]),
            list_internet_gateways=lambda *args, **kwargs:
                response([ns(id="gateway", is_enabled=True)]),
            get_route_table=lambda *args, **kwargs:
                response(ns(route_rules=[ns(destination="0.0.0.0/0",
                                            network_entity_id="gateway")])),
            get_security_list=lambda *args, **kwargs:
                response(ns(ingress_security_rules=[rule])),
        )
        block = ns(
            list_volumes=lambda *args, **kwargs: response([]),
            list_boot_volumes=lambda *args, **kwargs: response([]),
        )
        osp = ns(list_subscriptions=lambda *args: response([ns(plan_type="FREE_TIER")]))
        secrets = {
            "FRF_OCI_USER_OCID": "fake-user",
            "FRF_OCI_TENANCY_OCID": "fake-tenancy",
            "FRF_OCI_FINGERPRINT": "fake-fingerprint",
            "FRF_OCI_PRIVATE_KEY_PEM": "fake-key",
            "FRF_OCI_LAUNCH_ENABLED": "false",
        }
        output = io.StringIO()
        with patch.dict(runner.os.environ, secrets):
            with patch.object(runner.oci, "config", ns(validate_config=lambda cfg: None),
                              create=True):
                with patch.object(runner.oci, "identity", ns(IdentityClient=lambda cfg: iam),
                                  create=True):
                    with patch.object(runner.oci, "core", ns(
                        ComputeClient=lambda cfg: compute,
                        VirtualNetworkClient=lambda cfg: network,
                        BlockstorageClient=lambda cfg: block), create=True):
                        with patch.object(runner.oci, "osp_gateway",
                                          ns(SubscriptionServiceClient=lambda cfg: osp),
                                          create=True):
                            with patch.object(runner, "items",
                                              side_effect=lambda fn, *a, **kw: fn(*a, **kw).data):
                                with patch.object(runner, "find_guard", return_value=None):
                                    with patch("sys.stdout", output):
                                        runner.main()
        self.assertIn("PREFLIGHT=PASS", output.getvalue())
        self.assertIn("LAUNCH_INSTANCE=NOT_CALLED", output.getvalue())


if __name__ == "__main__":
    unittest.main()
