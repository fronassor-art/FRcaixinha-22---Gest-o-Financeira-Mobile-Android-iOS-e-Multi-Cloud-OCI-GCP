"""M40934: inspect registered FastAPI routes (in addition to M40931 AST).

CI-only import. No TestClient/startup event, PostgreSQL, migrations, HTTP
requests, OCI, PSP or other financial network activity.
"""
from __future__ import annotations

import unittest

from fastapi import FastAPI
from fastapi.routing import APIRoute

from app.main import app
from app.dependencies import require_master
from app.m40930_master_write_no_go import require_unreleased_master_write

MASTER_PREFIX = "/api/v1/master/"
MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
EXPECTED = {
    ("POST", "/api/v1/master/admin-onboarding/transition-preview"): "PREVIEW",
    ("POST", "/api/v1/master/admin-onboarding/preflight"): "PREFLIGHT",
    ("POST", "/api/v1/master/license-prices"): "BLOCKED",
    ("POST", "/api/v1/master/support-session"): "CONTRACT_DENIED",
    ("POST", "/api/v1/master/saas-promotions/draft"): "BLOCKED",
    ("POST", "/api/v1/master/saas-promotions/transition"): "BLOCKED",
}


def _deps(route: APIRoute) -> set:
    result = set()
    queue = list(route.dependant.dependencies)
    while queue:
        item = queue.pop()
        result.add(item.call)
        queue.extend(item.dependencies)
    return result


def check_registered_master_routes(routes) -> int:
    found = {}
    for route in routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith(MASTER_PREFIX):
            continue
        for method in set(route.methods) & MUTATION_METHODS:
            key = (method, route.path)
            if key in found:
                raise AssertionError("M40934_DUPLICATE_MASTER_MUTATION:" + repr(key))
            found[key] = route
    if set(found) != set(EXPECTED):
        raise AssertionError(
            "M40934_RUNTIME_MASTER_ROUTE_DRIFT extra=%r missing=%r" % (
                sorted(set(found) - set(EXPECTED)),
                sorted(set(EXPECTED) - set(found)),
            )
        )
    for key, route in found.items():
        deps = _deps(route)
        if require_master not in deps:
            raise AssertionError("M40934_REAL_ROUTE_MASTER_AUTH_MISSING:" + repr(key))
        policy = EXPECTED[key]
        if policy == "BLOCKED":
            if require_unreleased_master_write not in deps:
                raise AssertionError("M40934_REAL_ROUTE_GUARD_MISSING:" + repr(key))
        elif require_unreleased_master_write in deps:
            raise AssertionError("M40934_UNREVIEWED_ROUTE_DEPENDENCY_DRIFT:" + repr(key))
    return len(found)


class MasterRuntimeRouteInventory(unittest.TestCase):
    def test_actual_real_fastapi_app_is_contained(self):
        self.assertEqual(check_registered_master_routes(app.routes), 6)

    def test_unreviewed_dynamic_master_route_is_detected(self):
        fake = FastAPI()

        @fake.post("/api/v1/master/m40934-unreviewed")
        def synthetic():
            return {"synthetic": True}

        with self.assertRaisesRegex(AssertionError, "M40934_RUNTIME_MASTER_ROUTE_DRIFT"):
            check_registered_master_routes([*app.routes, *fake.routes])

    def test_missing_registered_master_guard_is_rejected(self):
        fake = FastAPI()

        @fake.post("/api/v1/master/license-prices")
        def synthetic():
            return {"synthetic": True}

        # Force omission of the real guarded route, preserving its path.
        replaced = [
            route for route in app.routes
            if not (isinstance(route, APIRoute)
                    and route.path == "/api/v1/master/license-prices"
                    and "POST" in route.methods)
        ]
        with self.assertRaisesRegex(AssertionError, "M40934_REAL_ROUTE_MASTER_AUTH_MISSING"):
            check_registered_master_routes([*replaced, *fake.routes])

    def test_no_financial_mode_release_through_routing(self):
        from app.m40840_financial_sql_release_no_go import (
            FinancialSQLReleaseBlocked, require_nonproduction_financial_sql,
        )
        with self.assertRaises(FinancialSQLReleaseBlocked):
            require_nonproduction_financial_sql({
                "ENVIRONMENT": "production", "PIX_REAL": "OFF",
                "PAGAMENTOS_REAIS": "OFF", "ATIVACAO_REAL": "OFF",
            })
        self.assertEqual(
            check_registered_master_routes(app.routes), len(EXPECTED),
        )


if __name__ == "__main__":
    unittest.main()
