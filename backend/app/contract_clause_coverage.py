"""FR Finance M29900–M30300: explicit verification register for every clause.

THIS IS NOT A COMPLIANCE CERTIFICATE. It reads the unchanged historical
M24000 contract backlog and checks only source/test *candidate presence*.
No CI result, syntax check, generated report, source path or user-supplied
assertion can promote a clause, enable Pix, or authorize production.
"""
from __future__ import annotations
from collections import Counter
from pathlib import Path
import json
import re
from typing import Mapping

from .release_evidence_matrix import PRIORITY_ORDER, PROVIDER_GATES

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = Path("docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json")
EXPECTED_COUNTS = {
    "PARCIAL": 58, "BLOQUEADO": 50,
    "NÃO VERIFICADO": 34, "DIVERGENTE": 5,
}

# Each workstream has explicit source/test REVIEW CANDIDATES, never proof.
# These paths are stable, repository-relative, static and do not include
# secrets, uploaded data, credentials, or operator-controlled paths.
WORKSTREAMS: dict[str, dict] = {
    "FUNCTIONAL_COVERAGE": {
        "src": "backend/app/dependencies.py",
        "test": "backend/tests/test_rls_isolation_ci.py",
        "gates": ("AUTH_PRODUCTION", "TENANT_RLS"),
        "external": "E2E_ROLE_TENANT_HUMAN_ATTESTATION",
    },
    "FINANCIAL_INTEGRATION": {
        "src": "backend/app/financial_three_source_preflight.py",
        "test": "backend/tests/test_m2200_three_source_preflight_ci.py",
        "gates": ("FINANCIAL_RECONCILIATION", "PIX_INBOUND"),
        "external": "PROVIDER_SETTLEMENT_AND_INDEPENDENT_RECONCILIATION",
    },
    "GOVERNANCE_DECISION": {
        "src": "docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md",
        "test": "backend/tests/test_m29810_fr_finance_identity_ci.py",
        "gates": (),
        "external": "OWNER_SIGNED_VERSIONED_DECISION",
    },
    "DOCUMENTARY_VERIFY": {
        "src": "docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md",
        "test": "backend/tests/test_m24000_contract_gap_147_ci.py",
        "gates": (),
        "external": "CLAUSE_BY_CLAUSE_DOCUMENTARY_ATTESTATION",
    },
    "GOVERNANCE_LEGAL_OWNER": {
        "src": "docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md",
        "test": "backend/tests/test_m24000_contract_gap_147_ci.py",
        "gates": (),
        "external": "OWNER_AND_LEGAL_FORMAL_APPROVAL",
    },
    "CONSENT_AUTHORIZATION": {
        "src": "backend/app/annual_consent.py",
        "test": "backend/tests/test_annual_consent.py",
        "gates": ("DUAL_CONTROL", "CONTRACT_CONSENT"),
        "external": "SIGNED_CONSENT_AND_APPROVER_PERSISTED_STAGING",
    },
    "SAAS_ENROLLMENT_BILLING": {
        "src": "backend/app/saas_billing_ci.py",
        "test": "backend/tests/test_master_saas_portfolio_ci.py",
        "gates": ("AUTH_PRODUCTION", "INVITE_TRANSACTION", "CONTRACT_CONSENT"),
        "external": "LIVE_BILLING_LICENSE_AND_USER_ONBOARDING_E2E",
    },
    "LEDGER_CLOSING_AND_RATEIO": {
        "src": "backend/app/closing_contract_oracle.py",
        "test": "backend/tests/test_annual_closing_contract_ci.py",
        "gates": ("FINANCIAL_RECONCILIATION", "ANNUAL_CLOSING"),
        "external": "RECONCILED_TENANT_LEDGER_ANNUAL_CYCLE",
    },
    "SUPPORT_SECURITY": {
        "src": "backend/app/audit_readiness.py",
        "test": "backend/tests/test_security_guards.py",
        "gates": ("AUTH_PRODUCTION", "TENANT_RLS"),
        "external": "PRODUCTION_RBAC_AUDIT_AND_INCIDENT_RESPONSE",
    },
    "MEMBER_LIFECYCLE": {
        "src": "backend/app/member_cycle_rules.py",
        "test": "backend/tests/test_member_cycle_contract_ci.py",
        "gates": ("INVITE_TRANSACTION", "CONTRACT_CONSENT"),
        "external": "MEMBER_ENTER_EXIT_REVOCATION_STAGING",
    },
    "LOAN_PAYOUT_SETTLEMENT": {
        "src": "backend/app/mp_money_out_policy.py",
        "test": "backend/tests/test_m4300_money_out_gate_ci.py",
        "gates": ("PIX_OUTBOUND", "FINANCIAL_RECONCILIATION"),
        "external": "MONEY_OUT_PROVIDER_COMMERCIAL_ENABLEMENT_AND_E2E",
    },
    "PAYMENT_PROVIDER_AND_RECONCILIATION": {
        "src": "backend/app/mp_orders_webhook.py",
        "test": "backend/tests/test_m4400_orders_webhook_ci.py",
        "gates": ("MP_CONNECT", "PIX_INBOUND", "FINANCIAL_RECONCILIATION"),
        "external": "MP_OAUTH_ORDERS_WEBHOOK_AND_THREE_SOURCE_PROOF",
    },
    "FUTURE_SCOPE_EXCLUSION": {
        "src": "backend/app/launch_readiness.py",
        "test": "backend/tests/test_m25600_launch_readiness_ci.py",
        "gates": (),
        "external": "OWNER_SCOPING_NO_REAL_RAFFLES_OR_UNAPPROVED_MODULES",
    },
    "LEGAL_OR_REGULATORY_GATE": {
        "src": "docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md",
        "test": "backend/tests/test_m24000_contract_gap_147_ci.py",
        "gates": (),
        "external": "INDEPENDENT_LEGAL_REGULATORY_REVIEW",
    },
    "ACCEPTANCE_TEST_EVIDENCE": {
        "src": "backend/app/launch_readiness.py",
        "test": "backend/tests/test_m28700_m29000_release_matrix_ci.py",
        "gates": ("MIGRATION_PARITY", "ANDROID_RELEASE"),
        "external": "EVIDENCE_ID_AND_REPRODUCIBLE_E2E_LOG",
    },
    "E2E_ACCEPTANCE_AT_01_50": {
        "src": "backend/app/launch_readiness.py",
        "test": "backend/tests/test_m28700_m29000_release_matrix_ci.py",
        "gates": ("AUTH_PRODUCTION", "TENANT_RLS", "ANNUAL_CLOSING"),
        "external": "FIFTY_INDEPENDENT_END_TO_END_ACCEPTANCE_ATTESTATIONS",
    },
}

STATUS = {
    "PARCIAL": "ENGINEERING_PARTIAL_E2E_REQUIRED",
    "BLOQUEADO": "BLOCKED_INTEGRATION_OR_EXTERNAL_GATE",
    "NÃO VERIFICADO": "NO_CLAUSE_SPECIFIC_ATTESTATION",
    "DIVERGENTE": "OWNER_DECISION_REQUIRED",
}
CLAUSE_ID = re.compile(r"^[0-9]+(?:\.[0-9]+)?(?:-[A-Z0-9.]+)?$")


def _load_and_validate(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if (type(raw) is not dict
            or raw.get("schema") != "FR_FINANCE_AI_STUDIO_CONTRACT_BACKLOG_M24000_V1"
            or raw.get("source_product") != "FR_FINANCE_AI_STUDIO_ONLY"
            or raw.get("kind") != "HISTORICAL_BASELINE_NOT_CURRENT_COMPLIANCE"
            or raw.get("production_release_authorized") is not False
            or type(raw.get("clauses")) is not list):
        raise ValueError("M29900_BASELINE_SCHEMA_INVALID")
    clauses = raw["clauses"]
    if len(clauses) != 147 or raw.get("counts") != EXPECTED_COUNTS:
        raise ValueError("M29900_BASELINE_COUNT_INVALID")
    ids: set[str] = set()
    counts: Counter = Counter()
    for c in clauses:
        if type(c) is not dict:
            raise ValueError("M29900_MALFORMED_CLAUSE")
        cid, state, workstream = (c.get("id"), c.get("baseline_status"), c.get("workstream"))
        if (type(cid) is not str or not CLAUSE_ID.fullmatch(cid)
                or cid in ids or state not in EXPECTED_COUNTS
                or workstream not in WORKSTREAMS
                or c.get("review_state") != "AWAITING_CLAUSE_EVIDENCE"
                or c.get("production_verified") is not False):
            raise ValueError("M29900_CLAUSE_FORGED_OR_INCOMPLETE")
        for field in ("name", "next_action", "required_evidence"):
            if type(c.get(field)) is not str or not c[field].strip():
                raise ValueError("M29900_REQUIRED_FIELD_MISSING")
        ids.add(cid)
        counts[state] += 1
    if dict(counts) != EXPECTED_COUNTS or set(WORKSTREAMS) != {
            c["workstream"] for c in clauses}:
        raise ValueError("M29900_WORKSTREAM_DRIFT")
    allowed = set(PRIORITY_ORDER)
    for spec in WORKSTREAMS.values():
        if any(gate not in allowed for gate in spec["gates"]):
            raise ValueError("M29900_UNKNOWN_TECH_GATE")
    return clauses


def build_inventory(root: Path = ROOT, *, baseline_path: Path | None = None) -> dict:
    """Returns 147 individual review records. Presence of a file is NOT proof.

    Does not read files listed in clause source_hint or traverse untrusted
    paths: only static workstream candidate paths are checked.
    """
    clauses = _load_and_validate(
        root / BASELINE_PATH if baseline_path is None else baseline_path
    )
    rows = []
    for c in clauses:
        spec = WORKSTREAMS[c["workstream"]]
        source_present = (root / spec["src"]).is_file()
        test_present = (root / spec["test"]).is_file()
        rows.append({
            "clause_id": c["id"],
            "clause_name": c["name"],
            "baseline_status": c["baseline_status"],
            "workstream": c["workstream"],
            "next_action": c["next_action"],
            "source_candidate": spec["src"],
            "source_candidate_present": source_present,
            "test_candidate": spec["test"],
            "test_candidate_present": test_present,
            "source_is_clausal_proof": False,
            "unit_test_is_e2e_proof": False,
            "engineering_state": (
                "SOURCE_AND_TEST_CANDIDATES_UNVERIFIED"
                if source_present and test_present else
                "MISSING_SOURCE_OR_TEST_CANDIDATE"
            ),
            "historical_review": STATUS[c["baseline_status"]],
            "required_technical_gates": list(spec["gates"]),
            "required_external_proof": spec["external"],
            "external_proof_attested": False,
            "clause_e2e_passed": False,
            "production_verified": False,
            "production_authorized": False,
        })
    counts = Counter(row["baseline_status"] for row in rows)
    if len(rows) != len({r["clause_id"] for r in rows}) or dict(counts) != EXPECTED_COUNTS:
        raise ValueError("M29900_CLAUSE_COVERAGE_MISMATCH")
    missing = [r["clause_id"] for r in rows if r["engineering_state"] ==
               "MISSING_SOURCE_OR_TEST_CANDIDATE"]
    return {
        "project": "FR_FINANCE_AI_STUDIO",
        "package": "M29900_M30300",
        "mode": "READ_ONLY_CLAUSE_CANDIDATE_INVENTORY",
        "scope": "147_CLAUSES_INDIVIDUALLY_LISTED",
        "total_clauses": 147,
        "individual_rows": len(rows),
        "baseline_counts": dict(counts),
        "historical_priority_count": counts["BLOQUEADO"] + counts["NÃO VERIFICADO"],
        "missing_candidate_clause_ids": missing,
        "clause_specific_e2e_confirmed": 0,
        "clause_specific_production_verified": 0,
        "technical_gates_verified": 0,
        "technical_gates_total": len(PRIORITY_ORDER),
        "provider_gates_verified": 0,
        "provider_gates_total": len(PROVIDER_GATES),
        "external_approvals_inferred": False,
        "local_db_5433_touched": False,
        "oci_vm_touched": False,
        "migrations_applied": False,
        "real_users_enabled": False,
        "real_pix_enabled": False,
        "production_authorized": False,
        "rows": rows,
    }


def build_at_programme(inventory: Mapping) -> dict:
    """AT-01..AT-50 are *unverified requirements*, NOT 50 executed tests."""
    if (type(inventory) is not dict or inventory.get("total_clauses") != 147
            or not any(r["clause_id"] == "16.4" and
                       r["baseline_status"] == "BLOQUEADO"
                       for r in inventory.get("rows", ()))):
        raise ValueError("M30300_AT_BASELINE_MISSING")
    steps = [{
        "acceptance_id": f"AT-{number:02d}",
        "clause_anchor": "16.4",
        "scenario_definition": "REFERENCE_SOURCE_REVIEW_REQUIRED",
        "execution_status": "NOT_EXECUTED_IN_REAL_STAGING",
        "independent_evidence": "MISSING",
        "production_authorized": False,
    } for number in range(1, 51)]
    return {
        "project": "FR_FINANCE_AI_STUDIO", "status": "50_ACCEPTANCE_PROOFS_OUTSTANDING",
        "scenario_titles_derived_from_signed_contract": False,
        "total": len(steps), "passed": 0, "steps": steps,
    }


def priority_rows(inventory: Mapping) -> list[dict]:
    rows = [r for r in inventory["rows"] if r["baseline_status"] in
            ("BLOQUEADO", "NÃO VERIFICADO")]
    if len(rows) != 84:
        raise ValueError("M30000_PRIORITY_DRIFT")
    return rows
