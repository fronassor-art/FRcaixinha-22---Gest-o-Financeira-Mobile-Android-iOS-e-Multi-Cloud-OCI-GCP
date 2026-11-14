"""M37693: exhaustive 281-item offline inventory and negative authorization tests."""
import json
import subprocess
import sys
from pathlib import Path

import pytest
from app.m37693_contract_release_audit import (
    ROOT, TOTAL, audit_checkpoint, checklist_markdown
)


@pytest.fixture(scope="module")
def result():
    return audit_checkpoint()


def test_all_sources_and_counts(result):
    assert result["project"] == "FR_FINANCE_AI_STUDIO_ONLY"
    assert result["new_review_tasks_planned"] == 281
    assert result["historical_clauses_pending"] == 147
    assert result["current_document_requirements_pending"] == 57
    assert result["live_release_gates_total"] == 20
    assert result["provider_gates_total"] == 7
    assert result["acceptance_scenarios_total"] == 50
    assert result["previous_plan_tasks_planned"] == 192
    assert sum(x["requirements"] for x in result["current_documents"]) == 57


def test_historical_counts_and_divergences_are_not_promoted(result):
    assert result["historical_baseline_counts"] == {
        "BLOQUEADO": 50, "DIVERGENTE": 5, "NÃO VERIFICADO": 34, "PARCIAL": 58
    }
    assert result["historical_divergent_ids"] == ["1.6", "1.8", "4.1", "5.3", "8.2"]


@pytest.mark.parametrize("idx", range(281))
def test_each_task_is_pending_and_unique(result, idx):
    task = result["tasks"][idx]
    assert task["task_id"] == "M" + str(37693 + idx)
    assert task["review_status"] == "PENDING_INDEPENDENT_EVIDENCE"
    assert task["production_verified"] is False
    assert task["source_id"] and task["title"] and task["source_path"]


def test_task_sources_are_exhaustive(result):
    kinds = {}
    for item in result["tasks"]:
        kinds[item["kind"]] = kinds.get(item["kind"], 0) + 1
    assert kinds == {
        "CURRENT_DOCUMENT_REQUIREMENT": 57,
        "HISTORICAL_CLAUSE_REVIEW": 147,
        "LIVE_RELEASE_GATE": 20,
        "EXTERNAL_PROVIDER_GATE": 7,
        "ACCEPTANCE_SCENARIO": 50,
    }
    assert len({x["task_id"] for x in result["tasks"]}) == TOTAL


def test_never_claims_authorization(result):
    assert result["status"] == "PRODUCTION_NOT_AUTHORIZED"
    for name in (
        "production_ready", "real_user_activation_authorized",
        "real_pix_authorized", "real_payment_authorized",
        "real_loan_authorized", "cloud_mutations_performed",
        "postgresql_original_accessed", "sql_migrations_applied",
        "operational_proof_fetched",
    ):
        assert result[name] is False
    assert result["live_release_gates_verified"] == 0
    assert result["provider_gates_verified"] == 0
    assert result["acceptance_scenarios_real_attested"] == 0


def test_markdown_is_full_and_unchecked(result):
    markdown = checklist_markdown(result)
    assert markdown.count("- [ ] M") == 281
    assert "M37693" in markdown and "M37973" in markdown
    assert "- [x]" not in markdown


def test_bad_checklist_input_fails_closed():
    with pytest.raises(ValueError):
        checklist_markdown({"status": "PRODUCTION_AUTHORIZED", "tasks": []})


def test_cli_summary_and_json_do_not_enable_live_work():
    script = ROOT / "backend/scripts/aistudio_m37693_contract_release_checkpoint.py"
    p = subprocess.run([sys.executable, str(script), "summary"], capture_output=True, text=True, check=True)
    assert "PRODUCTION_RELEASE=BLOCKED" in p.stdout
    assert "NEW_TASKS_M37693_M37973=281_PLANNED" in p.stdout
    j = subprocess.run([sys.executable, str(script), "json"], capture_output=True, text=True, check=True)
    assert json.loads(j.stdout)["real_pix_authorized"] is False


def test_inventory_contains_no_live_private_values(result):
    snapshot = json.dumps(result, ensure_ascii=False)
    for fragment in ("ocid1.", "sk_test_", "sk_live_", "Bearer eyJ", "postgres://", "SMTP_PASSWORD="):
        assert fragment not in snapshot
