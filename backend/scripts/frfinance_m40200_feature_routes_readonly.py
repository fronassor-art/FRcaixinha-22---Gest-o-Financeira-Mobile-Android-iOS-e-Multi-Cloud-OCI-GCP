#!/usr/bin/env python3
"""M40200 — authenticated-role feature route presence via public OpenAPI only.

The live probe calls only fixed GET loopback health/checkpoint/marker/OpenAPI/
readiness endpoints from M40190. It does NOT call protected tenant/member/
master or mutating routes, authenticate a member, exercise RLS, or claim
end-to-end functional readiness. The inventory is merely documentation of
GET/POST route declarations loaded into the running FR Finance API.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import classify_health
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40190_operational_readonly_checkpoint import (
    HEALTH, ROUTES, guarded, report as operational_report, safe_get,
)

TENANT = "/api/v1/tenants/{tenant_id}"
CREDIT = TENANT + "/special-credit"
MASTER = "/api/v1/master"
AUTH = "/api/v1/auth"
NOTIFICATIONS = "/api/v1/notifications"

# Immutable, public path templates. POST entries are DOCUMENTATION ONLY.
# Never send requests to any route in this table.
GROUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "ADMIN_READ": ("get", (
        TENANT + "/dashboard",
        TENANT + "/members",
        TENANT + "/admin-exclusive-cashbox",
        TENANT + "/admin-exclusive-cashbox/history",
        TENANT + "/admin-exclusive-cashbox/review-readiness",
        TENANT + "/admin-exclusive-cashbox/review-policy-gaps",
        TENANT + "/saas-promotions",
        CREDIT + "/capabilities",
        CREDIT + "/cycle-readiness",
        CREDIT + "/members",
        CREDIT + "/grants",
        CREDIT + "/campaigns",
    )),
    "ADMIN_WRITE_DOCUMENTED_ONLY": ("post", (
        CREDIT + "/grants",
        CREDIT + "/grants/{grant_id}/revoke",
        CREDIT + "/campaigns",
        CREDIT + "/campaigns/{campaign_id}/publish",
        CREDIT + "/campaigns/{campaign_id}/cancel",
    )),
    "MEMBER_READ": ("get", (
        AUTH + "/me",
        AUTH + "/contexts",
        AUTH + "/status",
        TENANT + "/my-contracts",
        CREDIT + "/opportunities",
        CREDIT + "/preferences",
        NOTIFICATIONS + "/capabilities",
        NOTIFICATIONS + "/readiness",
        NOTIFICATIONS,
    )),
    "MEMBER_WRITE_DOCUMENTED_ONLY": ("post", (
        CREDIT + "/opportunities/{recipient_id}/reply",
        CREDIT + "/preferences",
    )),
    "MASTER_READ": ("get", (
        MASTER + "/exclusive-cashbox",
        MASTER + "/exclusive-cashbox/history",
        MASTER + "/exclusive-cashbox/review-readiness",
        MASTER + "/exclusive-cashbox/review-policy-gaps",
        MASTER + "/saas-promotions",
    )),
    "MASTER_WRITE_DOCUMENTED_ONLY": ("post", (
        MASTER + "/saas-promotions/draft",
        MASTER + "/saas-promotions/transition",
    )),
}
EXPECTED_COUNT = sum(len(paths) for _, paths in GROUPS.values())


def check_schema(document):
    """Return group counts and known missing route templates; no data rows."""
    if type(document) is not dict or type(document.get("paths")) is not dict:
        return None
    paths = document["paths"]
    result = {}
    missing = []
    for name, (method, required) in GROUPS.items():
        n = 0
        for path in required:
            methods = paths.get(path)
            if (type(methods) is dict and
                    type(methods.get(method)) is dict):
                n += 1
            else:
                missing.append(method.upper() + " " + path)
        result[name] = f"{n}_OF_{len(required)}"
    return result, tuple(missing)


def report(preflight=operational_report, fetch=safe_get):
    output = {
        "M40200_OPERATIONAL_GATE": "NOT_ATTESTED",
        "M40200_ROUTE_INVENTORY": "NOT_ATTESTED",
        "M40200_EXPECTED_METHOD_PATH_PAIRS": str(EXPECTED_COUNT),
        "M40200_MISSING_COUNT": "NOT_ATTESTED",
        "M40200_AUTHORIZED_MEMBER_LOGIN": "NOT_TESTED",
        "M40200_ADMIN_MEMBER_RLS": "NOT_TESTED",
        "M40200_CREDIT_CAMPAIGN_PUBLISH": "NOT_EXECUTED",
        "M40200_EXTERNAL_CHANNELS": "NOT_ACTIVATED",
        "M40200_PROCESS_OWNER": "NOT_ATTESTED_ANDROID_OR_UNKNOWN",
        "M40200_PRODUCTION": "BLOCKED",
    }
    result = preflight()
    if (type(result) is not dict or result.get("M40190_STATUS")
            != "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"):
        output["M40200_STATUS"] = "BLOCKED_LOCAL_OPERATIONAL_GATE"
        return output
    output["M40200_OPERATIONAL_GATE"] = "PASS_M40190_LOCAL_READONLY"
    code, document = guarded(fetch, ROUTES)
    if code != 200:
        output["M40200_STATUS"] = "BLOCKED_OPENAPI_UNAVAILABLE"
        return output
    checked = check_schema(document)
    if checked is None:
        output["M40200_STATUS"] = "BLOCKED_OPENAPI_INVALID"
        return output
    groups, missing = checked
    for name, value in groups.items():
        output["M40200_" + name] = value
    output["M40200_MISSING_COUNT"] = str(len(missing))
    output["M40200_ROUTE_INVENTORY"] = (
        "DOCUMENTED_METHODS_PRESENT_NOT_ROLE_TESTED"
        if not missing else "DOCUMENTED_METHODS_INCOMPLETE"
    )
    for index, path in enumerate(missing[:12], start=1):
        output["M40200_MISSING_" + str(index)] = path
    last_code, last_doc = guarded(fetch, HEALTH)
    if last_code != 200 or classify_health(last_doc) != "FR_FINANCE_ONLINE":
        output["M40200_STATUS"] = "BLOCKED_HEALTH_CHANGED_DURING_INVENTORY"
    elif missing:
        output["M40200_STATUS"] = "BLOCKED_FEATURE_ROUTES_INCOMPLETE"
    else:
        output["M40200_STATUS"] = "PASS_DOCUMENTED_FEATURE_ROUTES_ONLY"
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="FR Finance M40200 route documentation only")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40200 — ROLE FEATURE ROUTE INVENTORY READ ONLY ===")
    if args.source_only:
        print("M40200_SOURCE_ONLY=PASS_ROUTE_CATALOG")
        print("M40200_EXPECTED_METHOD_PATH_PAIRS=" + str(EXPECTED_COUNT))
        print("M40200_LIVE_API=NOT_QUERIED")
        return 0
    if not native_termux():
        print("M40200_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        output = report()
        for key, value in output.items():
            print(key + "=" + value)
        return 0 if output.get("M40200_STATUS") == (
            "PASS_DOCUMENTED_FEATURE_ROUTES_ONLY") else 2
    finally:
        print("M40200_HTTP=GET_FIXED_LOOPBACK_PUBLIC_METADATA_ONLY")
        print("M40200_TENANT_ROUTES_REQUESTED=NONE")
        print("M40200_ADMIN_POST_REQUESTS=NONE")
        print("M40200_MEMBER_POST_REQUESTS=NONE")
        print("M40200_CREDENTIALS_TOKENS_PIDS=NOT_READ")
        print("M40200_LOGIN_SESSIONS_CREATED=NONE")
        print("M40200_TERMINAL_SQL_CONNECTIONS=NONE")
        print("M40200_DATABASE_WRITES=NONE_FROM_TERMINAL_PROBE")
        print("M40200_MIGRATIONS=NONE")
        print("M40200_FASTAPI_RESTART=NONE")
        print("M40200_POSTGRESQL_RESTART=NONE")
        print("M40200_PIX_REAL=OFF")
        print("M40200_PAGAMENTOS_REAIS=OFF")
        print("M40200_ATIVACAO_REAL=OFF")
        print("M40200_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
