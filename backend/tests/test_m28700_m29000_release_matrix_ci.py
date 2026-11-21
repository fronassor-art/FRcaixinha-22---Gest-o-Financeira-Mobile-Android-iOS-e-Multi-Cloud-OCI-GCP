"""M28700–M29000: regression tests for fail-closed release decisions."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from app.admin_onboarding_workflow import preview_transition
from app.annual_allocation_preview import annual_allocation_preview
from app.provider_intake_schema import new_manifest, validate_field, IntakeBlocked
from app.release_evidence_matrix import (
    ACCEPTANCE_PROOFS, PRIORITY_ORDER, PROVIDER_GATES, build_release_matrix,
)

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json"
CLI = ROOT / "backend/scripts/aistudio_release_evidence_matrix.py"


def test_27_distinct_gates_never_auto_enable_any_real_operation():
    report = build_release_matrix()
    assert report["project"] == "FR_FINANCE_AI_STUDIO"
    assert report["mode"] == "READ_ONLY_REPORT_NO_ACTIVATION"
    assert report["status"] == "PRODUCTION_NOT_AUTHORIZED"
    assert report["gate_count"] == report["gates_unverified"] == 20
    assert report["provider_gate_count"] == 7
    assert report["provider_gates_verified"] == 0
    assert set(report["authorizations"].values()) == {False}
    assert report["offline_tests_are_production_evidence"] is False
    assert report["ci_green_enables_user_activation"] is False
    assert report["writes_performed"] is False
    assert report["oci_vm_created_by_this_audit"] is False


def test_every_gate_has_unique_proof_and_priority_sequence():
    report = build_release_matrix()
    assert tuple(x["id"] for x in report["gates"]) == PRIORITY_ORDER
    assert set(ACCEPTANCE_PROOFS) == set(PRIORITY_ORDER)
    assert [g["priority"] for g in report["gates"]] == list(range(1, 21))
    assert all(g["acceptance_proof"] and g["operationally_verified"] is False
               for g in report["gates"])
    assert tuple(x["id"] for x in report["provider_gates"]) == PROVIDER_GATES


def test_source_presence_does_not_become_approval():
    report = build_release_matrix()
    assert any(item["engineering_source_present"] for item in report["gates"])
    assert all("UNVERIFIED" in item["status"] for item in report["gates"])
    assert len(report["staging_acceptance_queue"]) == 20


def test_valid_public_provider_field_does_not_unlock_provider_gate():
    manifest = new_manifest()
    manifest["public_inputs"]["OCI_REGION"] = validate_field(
        "OCI_REGION", "sa-saopaulo-1"
    )
    report = build_release_matrix(manifest)
    assert len(report["public_fields_absent"]) == 12
    assert all(not x["provider_test_approved"] and not x["live_provider_authorized"]
               for x in report["provider_gates"])
    assert all(v is False for v in report["authorizations"].values())


@pytest.mark.parametrize("field,value", [
    ("APP_URL", "http://app.frfinance.com.br"),
    ("OCI_REGION", "somewhere"),
    ("MP_WEBHOOK_URL", "http://127.0.0.1:8080/hook"),
])
def test_malicious_or_invalid_provider_fields_rejected(field, value):
    manifest = new_manifest()
    manifest["public_inputs"][field] = value
    with pytest.raises(IntakeBlocked):
        build_release_matrix(manifest)


def test_147_historical_clauses_are_not_production_attestation():
    baseline = json.loads(BASELINE.read_text())
    report = build_release_matrix(contract_baseline=baseline)
    historical = report["historical_contract_baseline"]
    assert historical["total"] == 147
    assert historical["counts"] == {
        "BLOQUEADO": 50, "DIVERGENTE": 5, "NÃO VERIFICADO": 34, "PARCIAL": 58
    }
    assert historical["promoted_to_verified"] == 0
    assert historical["live_compliance_claimed"] is False


def test_reject_any_forged_contract_clause_promotion():
    baseline = json.loads(BASELINE.read_text())
    baseline["clauses"][0]["production_verified"] = True
    with pytest.raises(ValueError, match="UNTRUSTED_CLAUSE_PROMOTION"):
        build_release_matrix(contract_baseline=baseline)


def test_reject_duplicate_baseline_clause_identity():
    baseline = json.loads(BASELINE.read_text())
    baseline["clauses"][1]["id"] = baseline["clauses"][0]["id"]
    with pytest.raises(ValueError, match="INVALID_147_BASELINE"):
        build_release_matrix(contract_baseline=baseline)


def test_master_onboarding_fully_approved_synthetic_case_still_never_activates():
    result = preview_transition(
        current="REQUESTED", proposed="EMAIL_VERIFIED", actor_role="MASTER",
        candidate_is_actor=False, email_verified=True, tenant_active=True,
        independent_approval=True, token_valid=True, expected_revision=1,
        observed_revision=1, idempotency_key=uuid4(), previously_used_keys=[],
    )
    assert result["result"] == "EXECUTION_DENIED"
    assert "RUNTIME_OPERATIONS_DISABLED" in result["reasons"]
    assert result["allowed_for_real_execution"] is False
    assert result["audit_persisted"] is False
    assert result["invitation_created"] is False


def test_master_self_approval_and_replay_are_rejected():
    key = uuid4()
    result = preview_transition(
        current="REQUESTED", proposed="EMAIL_VERIFIED", actor_role="MASTER",
        candidate_is_actor=True, email_verified=True, tenant_active=True,
        independent_approval=False, token_valid=True, expected_revision=2,
        observed_revision=1, idempotency_key=key, previously_used_keys=[key],
    )
    for reason in ("SELF_APPROVAL_PROHIBITED", "INDEPENDENT_APPROVAL_REQUIRED",
                   "REVISION_CONFLICT", "IDEMPOTENCY_REPLAY"):
        assert reason in result["reasons"]
    assert result["account_changed"] is False


def test_annual_15_85_preview_preserves_centavos_without_disbursement():
    result = annual_allocation_preview("1000.00", {"member-a": 1, "member-b": 1})
    assert result["state"] == "PREVIEW_NOT_SETTLED"
    assert result["admin_provisional_cents"] == 15000
    assert result["member_pool_cents"] == 85000
    assert sum(result["member_shares_cents"].values()) == 85000
    assert result["segregated_undistributed_cents"] == 0


def test_no_members_keep_85_percent_undistributed():
    result = annual_allocation_preview("1.00", {})
    assert result["admin_provisional_cents"] == 15
    assert result["member_pool_cents"] == 85
    assert result["segregated_undistributed_cents"] == 85


def test_cli_reports_read_only_no_activation_or_credentials(tmp_path):
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["PYTHONPATH"] = str(ROOT / "backend")
    result = subprocess.run(
        [sys.executable, str(CLI), "audit"], env=env, text=True,
        capture_output=True, timeout=25,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    for part in (
        "RELEASE_GATES_UNVERIFIED=20", "PROVIDER_GATES_UNVERIFIED=7",
        "HISTORICAL_147_CLAUSES=147", "PUBLIC_FIELDS_MISSING=13",
        "REAL_USERS=OFF", "REAL_PIX=OFF", "MIGRATIONS_APPLIED=NO",
        "FR_FINANCE_M29000_AUDIT=PASS",
        "PRODUCTION_AUTHORIZATION=NOT_GRANTED",
    ):
        assert part in result.stdout


def test_cli_json_preserves_security_sentinels(tmp_path):
    env = dict(os.environ)
    env["HOME"] = str(tmp_path)
    env["PYTHONPATH"] = str(ROOT / "backend")
    r = subprocess.run(
        [sys.executable, str(CLI), "json"], env=env,
        text=True, capture_output=True, timeout=25,
    )
    assert r.returncode == 0, (r.stdout, r.stderr)
    data = json.loads(r.stdout)
    assert data["status"] == "PRODUCTION_NOT_AUTHORIZED"
    assert data["historical_contract_baseline"]["total"] == 147
    assert all(value is False for value in data["authorizations"].values())


def test_no_db_oci_or_provider_sdk_in_audit_implementation():
    source = (ROOT / "backend/app/release_evidence_matrix.py").read_text()
    cli_source = CLI.read_text()
    for needle in ("psycopg.connect(", "launch_instance(", "send_message(",
                   "requests.post(", "subprocess.run(", "INSERT INTO ",
                   "UPDATE public.", "DELETE FROM public."):
        assert needle not in source
        assert needle not in cli_source
