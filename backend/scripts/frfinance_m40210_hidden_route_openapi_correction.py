#!/usr/bin/env python3
"""M40210: distinguish 33 OpenAPI-visible endpoints from 2 hidden M40060 GETs.

Never call protected endpoints. Inspect local source AST for intentionally
hidden, authenticated route declarations and registrations; verify the 33
visible method-path pairs via the already running API's public OpenAPI.
A static hidden declaration is NOT proof that its endpoint executes or
that authorization, RLS, reviewer mandate, or financial operations work.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.app.m39700_runtime_contract import classify_health
from backend.scripts.frfinance_m39700_termux_runtime_check import native_termux
from backend.scripts.frfinance_m40190_operational_readonly_checkpoint import (
    HEALTH, ROUTES, guarded, report as operational_report, safe_get,
)
from backend.scripts.frfinance_m40200_feature_routes_readonly import (
    GROUPS, TENANT, MASTER,
)

HIDDEN_SOURCE = ROOT / "backend/app/routers/exclusive_cashbox_review_gaps.py"
MAIN_SOURCE = ROOT / "backend/app/main.py"

HIDDEN = {
    "ADMIN_READ": (
        "tenant_router", "/admin-exclusive-cashbox/review-policy-gaps",
        TENANT + "/admin-exclusive-cashbox/review-policy-gaps",
        "get_current_session", "get_rls_db_connection",
    ),
    "MASTER_READ": (
        "master_router", "/exclusive-cashbox/review-policy-gaps",
        MASTER + "/exclusive-cashbox/review-policy-gaps",
        "require_master", None,
    ),
}
HIDDEN_COUNT = len(HIDDEN)
EXPECTED_COUNT = sum(len(paths) for _, paths in GROUPS.values())
PUBLIC_EXPECTED = EXPECTED_COUNT - HIDDEN_COUNT


def _router_declarations(tree):
    """Find literal hidden router declarations; no app import/initialization."""
    declared = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Name) or call.func.id != "APIRouter":
            continue
        prefix = next((k.value.value for k in call.keywords
                       if k.arg == "prefix" and isinstance(k.value, ast.Constant)
                       and type(k.value.value) is str), None)
        flag = next((k.value for k in call.keywords
                     if k.arg == "include_in_schema"), None)
        hidden = (isinstance(flag, ast.Constant) and flag.value is False)
        for target in node.targets:
            if isinstance(target, ast.Name):
                declared[target.id] = (prefix, hidden)
    return declared


def _uses_dependency(node, dependency_name):
    for item in ast.walk(node):
        if (isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
                and item.func.id == "Depends" and len(item.args) == 1
                and isinstance(item.args[0], ast.Name)
                and item.args[0].id == dependency_name):
            return True
    return False


def _registered(main_tree, router):
    """Static registration to the normal /api/v1 prefix, not live attestation."""
    for node in ast.walk(main_tree):
        if not isinstance(node, ast.Call):
            continue
        call = node.func
        if (not isinstance(call, ast.Attribute) or call.attr != "include_router"
                or not isinstance(call.value, ast.Name) or call.value.id != "app"
                or not node.args):
            continue
        arg = node.args[0]
        if (not isinstance(arg, ast.Attribute)
                or not isinstance(arg.value, ast.Name)
                or arg.value.id != "_review_policy_gaps"
                or arg.attr != router):
            continue
        for kw in node.keywords:
            if (kw.arg == "prefix" and isinstance(kw.value, ast.Attribute)
                    and kw.value.attr == "API_V1_STR"
                    and isinstance(kw.value.value, ast.Name)
                    and kw.value.value.id == "settings"):
                return True
    return False


def hidden_source_check(module_path=HIDDEN_SOURCE, main_path=MAIN_SOURCE):
    try:
        if (not module_path.is_file() or module_path.is_symlink()
                or not main_path.is_file() or main_path.is_symlink()):
            return "BLOCKED_HIDDEN_SOURCE_MISSING"
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
        app = ast.parse(main_path.read_text(encoding="utf-8"))
        decl = _router_declarations(tree)
        for name, (router, suffix, template, auth, db_auth) in HIDDEN.items():
            method, paths = GROUPS[name]
            if method != "get" or template not in paths:
                return "BLOCKED_HIDDEN_CATALOG_DRIFT"
            expected_prefix = "/master" if router == "master_router" else "/tenants/{tenant_id}"
            if decl.get(router) != (expected_prefix, True):
                return "BLOCKED_HIDDEN_ROUTER_CONFIGURATION"
            if not _registered(app, router):
                return "BLOCKED_HIDDEN_ROUTER_NOT_REGISTERED_IN_SOURCE"
            found = False
            for node in tree.body:
                if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                    continue
                for dec in node.decorator_list:
                    if (not isinstance(dec, ast.Call)
                            or not isinstance(dec.func, ast.Attribute)
                            or not isinstance(dec.func.value, ast.Name)
                            or dec.func.value.id != router or dec.func.attr != "get"
                            or len(dec.args) != 1 or not isinstance(dec.args[0], ast.Constant)
                            or dec.args[0].value != suffix):
                        continue
                    if _uses_dependency(node, auth) and (
                            db_auth is None or _uses_dependency(node, db_auth)):
                        found = True
            if not found:
                return "BLOCKED_HIDDEN_AUTH_OR_DECORATOR"
        return "PASS_TWO_HIDDEN_SOURCE_DECLARATIONS_NOT_RUNTIME_TESTED"
    except (OSError, UnicodeError, SyntaxError, ValueError, TypeError):
        return "BLOCKED_HIDDEN_SOURCE_UNVERIFIED"


def visible_schema(document):
    if type(document) is not dict or type(document.get("paths")) is not dict:
        return None
    paths = document["paths"]
    group_counts = {}
    missing = []
    visible = 0
    for name, (method, required) in GROUPS.items():
        hidden_path = HIDDEN[name][2] if name in HIDDEN else None
        yes = 0
        expected_visible = 0
        for path in required:
            if path == hidden_path:
                # Explicitly excluded: include_in_schema=False in M40060.
                continue
            expected_visible += 1
            match = paths.get(path)
            if type(match) is dict and type(match.get(method)) is dict:
                yes += 1
                visible += 1
            else:
                missing.append(method.upper() + " " + path)
        group_counts[name] = f"{yes}_OF_{expected_visible}"
    return group_counts, tuple(missing), visible


def report(source=hidden_source_check, preflight=operational_report, fetch=safe_get):
    result = {
        "M40210_CORRECTION": "M40200_OPENAPI_HIDDEN_ROUTES_CLASSIFICATION",
        "M40210_TOTAL_SOURCE_CONTRACTS": str(EXPECTED_COUNT),
        "M40210_PUBLIC_OPENAPI_EXPECTED": str(PUBLIC_EXPECTED),
        "M40210_HIDDEN_SOURCE_EXPECTED": str(HIDDEN_COUNT),
        "M40210_HIDDEN_SOURCE": "NOT_ATTESTED",
        "M40210_RUNTIME": "NOT_ATTESTED",
        "M40210_PUBLIC_VISIBLE_FOUND": "NOT_ATTESTED",
        "M40210_PUBLIC_MISSING_COUNT": "NOT_ATTESTED",
        "M40210_HIDDEN_RUNTIME_REACHABILITY": "NOT_TESTED",
        "M40210_ADMIN_AUTHENTICATED_RLS": "NOT_TESTED",
        "M40210_FINANCIAL_REVIEW_APPROVAL": "FALSE",
        "M40210_PROCESS_OWNER": "NOT_ATTESTED_ANDROID_OR_UNKNOWN",
        "M40210_PRODUCTION": "BLOCKED",
    }
    hidden = source()
    result["M40210_HIDDEN_SOURCE"] = hidden
    if hidden != "PASS_TWO_HIDDEN_SOURCE_DECLARATIONS_NOT_RUNTIME_TESTED":
        result["M40210_STATUS"] = "BLOCKED_HIDDEN_ROUTE_STATIC_DECLARATIONS"
        return result
    runtime = preflight()
    if (type(runtime) is not dict or runtime.get("M40190_STATUS")
            != "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"):
        result["M40210_STATUS"] = "BLOCKED_M40190_OPERATIONAL_READINESS"
        return result
    result["M40210_RUNTIME"] = "PASS_M40190_READONLY"
    code, document = guarded(fetch, ROUTES)
    if code != 200:
        result["M40210_STATUS"] = "BLOCKED_OPENAPI_UNAVAILABLE"
        return result
    checked = visible_schema(document)
    if checked is None:
        result["M40210_STATUS"] = "BLOCKED_OPENAPI_INVALID"
        return result
    groups, missing, count = checked
    for name, value in groups.items():
        result["M40210_" + name] = value
    result["M40210_PUBLIC_VISIBLE_FOUND"] = str(count)
    result["M40210_PUBLIC_MISSING_COUNT"] = str(len(missing))
    for i, entry in enumerate(missing[:12], start=1):
        result["M40210_MISSING_" + str(i)] = entry

    final_status, final_document = guarded(fetch, HEALTH)
    if final_status != 200 or classify_health(final_document) != "FR_FINANCE_ONLINE":
        status = "BLOCKED_HEALTH_CHANGED_DURING_CHECK"
    elif missing or count != PUBLIC_EXPECTED:
        status = "BLOCKED_VISIBLE_ROUTE_MISMATCH"
    else:
        status = "PASS_33_PUBLIC_AND_2_HIDDEN_SOURCE_ONLY"
    result["M40210_STATUS"] = status
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description="FR Finance M40210 hidden route classification")
    parser.add_argument("--source-only", action="store_true")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M40210 — OPENAPI HIDDEN ROUTE CORRECTION ===")
    if args.source_only:
        state = hidden_source_check()
        print("M40210_HIDDEN_SOURCE=" + state)
        print("M40210_PUBLIC_OPENAPI_EXPECTED=" + str(PUBLIC_EXPECTED))
        print("M40210_LIVE_API=NOT_QUERIED")
        return 0 if state.startswith("PASS_") else 2
    if not native_termux():
        print("M40210_STATUS=BLOCKED_NOT_NATIVE_TERMUX")
        return 2
    try:
        result = report()
        for key, value in result.items():
            print(key + "=" + value)
        return 0 if result["M40210_STATUS"] == (
            "PASS_33_PUBLIC_AND_2_HIDDEN_SOURCE_ONLY") else 2
    finally:
        print("M40210_PROTECTED_ENDPOINT_CALLS=NONE")
        print("M40210_HTTP=GET_FIXED_PUBLIC_LOOPBACK_ONLY")
        print("M40210_LOGIN_SESSIONS_CREATED=NONE")
        print("M40210_POST_REQUESTS=NONE")
        print("M40210_DATABASE_WRITES=NONE_FROM_TERMINAL_PROBE")
        print("M40210_MIGRATIONS=NONE")
        print("M40210_POSTGRESQL_RESTART=NONE")
        print("M40210_FASTAPI_RESTART=NONE")
        print("M40210_PIX_REAL=OFF")
        print("M40210_PAGAMENTOS_REAIS=OFF")
        print("M40210_ATIVACAO_REAL=OFF")
        print("M40210_PRODUCTION=BLOCKED")


if __name__ == "__main__":
    raise SystemExit(main())
