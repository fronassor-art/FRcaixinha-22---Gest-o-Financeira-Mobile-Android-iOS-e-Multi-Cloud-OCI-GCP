#!/usr/bin/env python3
"""CP20261117: source-only audit; NEVER OCI, database, network or runtime proof."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = "docs/FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330.json"
FAMILIES = {
    "CURRENT_ORIGINAL_REQUIREMENT": 57,
    "CURRENT_ANNEX_REQUIREMENT": 49,
    "HISTORICAL_LEGACY_CLAUSE": 147,
    "LIVE_RELEASE_GATE": 20,
    "EXTERNAL_PROVIDER_GATE": 7,
    "ACCEPTANCE_SCENARIO": 50,
}
REQUIRED_SOURCE_GATES = {
    "AUTH_AND_ROLES": ("backend/app/dependencies.py",
                       ("get_current_session", "require_master", "require_tenant_access")),
    "RLS_CONNECTION": ("backend/app/database.py",
                       ("get_rls_db_connection", "app.current_tenant_id")),
    "CREDIT_SANDBOX": ("backend/app/routers/special_credit.py",
                       ("FR_FINANCE_SPECIAL_CREDIT_SANDBOX", "real_credit_enabled")),
    "RELEASE_NO_GO": ("backend/app/launch_readiness.py",
                       ("OCI_PUBLIC_HTTPS", '"production_verified": False')),
    "OCI_GUARDED_AUTOLAUNCH": (".github/workflows/frfinance-oci-a1-autolaunch.yml",
                       ("FR_FINANCE_OCI_CREATOR_ENABLED", "FR_FINANCE_OCI_LAUNCH_ENABLED",
                        "github.event_name == 'schedule'")),
    "ANDROID_RELEASE_SIGNATURE": ("android/app/build.gradle",
                       ("releaseRequested", "M21700: assinatura release separada obrigatoria.",
                        "Release requer HTTPS sem cleartext.")),
    "ANDROID_PROFILE": ("capacitor.config.ts",
                       ("FR_FINANCE_ANDROID_RELEASE_PROFILE", "M21700: release não aceita Termux.")),
    "SPECIAL_CREDIT_RLS": ("backend/migrations/110_fr_finance_special_credit_offline.sql",
                       ("ENABLE ROW LEVEL SECURITY", "FORCE ROW LEVEL SECURITY")),
    "PG18_READ_ONLY_CATALOG": ("backend/scripts/frfinance_m40240_pg18_rls_catalog_readonly.sql",
                       ("BEGIN READ ONLY;", "ROLLBACK;",
                        "M40240_AUTHENTICATED_RLS_DATA_PLANE=NOT_TESTED")),
    "TERMUX_FINANCE_GATES": ("backend/scripts/run_termux_fastapi.sh",
                       ("errno.ECONNREFUSED", "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF",
                        "ATIVACAO_REAL=OFF")),
}

def check_matrix(matrix):
    if type(matrix) is not dict or type(matrix.get("items")) is not list:
        return "BLOCKED_MATRIX_FORMAT"
    items = matrix["items"]
    counts = matrix.get("counts")
    evidence = matrix.get("evidence_status")
    if type(counts) is not dict or type(evidence) is not dict:
        return "BLOCKED_MATRIX_COUNTS"
    if len(items) != 330 or counts.get("expanded_total") != 330:
        return "BLOCKED_MATRIX_TOTAL"
    ids = []
    families = Counter()
    for item in items:
        if type(item) is not dict or item.get("family") not in FAMILIES:
            return "BLOCKED_ITEM_FAMILY"
        check_id = item.get("check_id")
        if type(check_id) is not str or not check_id.startswith("CP26-"):
            return "BLOCKED_ITEM_ID"
        ids.append(check_id)
        families[item["family"]] += 1
        if item.get("production_verified") is not False:
            return "BLOCKED_UNATTESTED_PRODUCTION_APPROVAL"
    if len(ids) != len(set(ids)) or families != Counter(FAMILIES):
        return "BLOCKED_ITEM_COUNTS_OR_DUPLICATES"
    if any(counts.get(key) != value for key, value in FAMILIES.items()):
        return "BLOCKED_REPORTED_FAMILY_COUNTS"
    if (evidence.get("live_release_gates_verified") != 0 or
        evidence.get("live_release_gates_total") != 20 or
        evidence.get("external_provider_gates_verified") != 0 or
        evidence.get("external_provider_gates_total") != 7 or
        evidence.get("AT_scenarios_e2e_verified") != 0 or
        evidence.get("AT_scenarios_total") != 50):
        return "BLOCKED_UNVERIFIED_GATES_PROMOTED"
    if matrix.get("release_decision") != "NO_GO_PRODUCTION_NOT_AUTHORIZED":
        return "BLOCKED_RELEASE_DECISION"
    return "PASS_330_ITEM_DOCUMENTARY_MATRIX_NO_GO"

def check_sources(root=ROOT, gates=REQUIRED_SOURCE_GATES):
    for name, (relative, markers) in gates.items():
        path = root / relative
        if not path.is_file() or path.is_symlink():
            return "BLOCKED_" + name + "_MISSING"
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return "BLOCKED_" + name + "_UNREADABLE"
        if any(marker not in content for marker in markers):
            return "BLOCKED_" + name + "_SOURCE_DRIFT"
    return "PASS_STATIC_SOURCE_GUARDS_NOT_RUNTIME_ATTESTED"

def report(root=ROOT, matrix=None):
    try:
        content = matrix if matrix is not None else json.loads(
            (root / MATRIX).read_text(encoding="utf-8"))
    except (ValueError, OSError, UnicodeError):
        return {"CP20261117_STATUS": "BLOCKED_MATRIX_UNREADABLE"}
    one = check_matrix(content)
    two = check_sources(root)
    result = {
        "CP20261117_MATRIX": one,
        "CP20261117_SOURCE_GUARDS": two,
        "CP20261117_ITEMS": "330",
        "CP20261117_LIVE_RELEASE_GATES": "0_OF_20_ATTESTED",
        "CP20261117_EXTERNAL_GATES": "0_OF_7_ATTESTED",
        "CP20261117_E2E_AT": "0_OF_50_ATTESTED",
        "CP20261117_OCI_VM": "NOT_ATTESTED_BY_OFFLINE_CI",
        "CP20261117_POSTGRESQL_LIVE_RLS": "NOT_ATTESTED_BY_OFFLINE_CI",
        "CP20261117_ANDROID_LIVE": "NOT_ATTESTED_BY_OFFLINE_CI",
        "CP20261117_PR_DRAFT": "NOT_ATTESTED_BY_OFFLINE_CI",
        "CP20261117_PRODUCTION": "BLOCKED",
    }
    result["CP20261117_STATUS"] = (
        "PASS_OFFLINE_GITHUB_CHECKPOINT_NO_GO"
        if one.startswith("PASS_") and two.startswith("PASS_")
        else "BLOCKED_CHECKPOINT_DRIFT"
    )
    return result

def main(argv=None):
    p = argparse.ArgumentParser(description="FR Finance audit offline (no VM)")
    p.add_argument("--offline", action="store_true")
    p.parse_args(argv)
    print("=== FR FINANCE CP20261117 — GITHUB CHECKPOINT SEM VM ===")
    result = report()
    for key, value in result.items():
        print(key + "=" + value)
    print("CP20261117_HTTP=NONE")
    print("CP20261117_DB_CONNECTIONS=NONE")
    print("CP20261117_VM_LAUNCH=NONE")
    print("CP20261117_MIGRATIONS=NONE")
    print("CP20261117_PIX_REAL=OFF")
    return 0 if result["CP20261117_STATUS"] == (
        "PASS_OFFLINE_GITHUB_CHECKPOINT_NO_GO") else 2

if __name__ == "__main__":
    raise SystemExit(main())
