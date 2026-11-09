"""M29900-M30300: 147 individually checked clauses and 50 open AT slots."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from app.contract_clause_coverage import (
    ROOT, BASELINE_PATH, EXPECTED_COUNTS, WORKSTREAMS, build_inventory,
    build_at_programme, priority_rows, _load_and_validate,
)
from app.release_evidence_matrix import PRIORITY_ORDER, PROVIDER_GATES
from app.launch_readiness import readiness_manifest

INVENTORY = build_inventory()
CLAUSES = tuple(row["clause_id"] for row in INVENTORY["rows"])


@pytest.mark.parametrize("clause_id", CLAUSES)
def test_every_clause_has_explicit_unverified_evidence_position(clause_id):
    candidates = [row for row in INVENTORY["rows"] if row["clause_id"] == clause_id]
    assert len(candidates) == 1
    row, = candidates
    assert row["baseline_status"] in EXPECTED_COUNTS
    assert row["source_candidate"].startswith(("backend/", "docs/"))
    assert row["test_candidate"].startswith("backend/tests/")
    assert row["source_candidate_present"] is True
    assert row["test_candidate_present"] is True
    assert row["engineering_state"] == "SOURCE_AND_TEST_CANDIDATES_UNVERIFIED"
    assert not row["source_is_clausal_proof"]
    assert not row["unit_test_is_e2e_proof"]
    assert row["required_external_proof"]
    assert row["next_action"]
    assert not row["clause_e2e_passed"]
    assert not row["external_proof_attested"]
    assert not row["production_verified"]
    assert not row["production_authorized"]


def test_all_147_and_all_84_priority_clauses_accounted_for():
    assert len(CLAUSES) == len(set(CLAUSES)) == 147
    assert len(priority_rows(INVENTORY)) == 84
    assert INVENTORY["baseline_counts"] == EXPECTED_COUNTS
    assert not INVENTORY["missing_candidate_clause_ids"]
    assert INVENTORY["clause_specific_e2e_confirmed"] == 0
    assert INVENTORY["clause_specific_production_verified"] == 0
    assert INVENTORY["historical_priority_count"] == 84


def test_50_named_acceptance_slots_remain_unverified():
    p = build_at_programme(INVENTORY)
    assert p["total"] == 50 and p["passed"] == 0
    assert [step["acceptance_id"] for step in p["steps"]] == [
        f"AT-{i:02d}" for i in range(1, 51)
    ]
    assert all(step["independent_evidence"] == "MISSING"
               and not step["production_authorized"] for step in p["steps"])
    assert not p["scenario_titles_derived_from_signed_contract"]


def test_all_sixteen_workstreams_and_release_gates_included():
    assert len(WORKSTREAMS) == 16
    assert len(PRIORITY_ORDER) == INVENTORY["technical_gates_total"] == 20
    assert len(PROVIDER_GATES) == INVENTORY["provider_gates_total"] == 7
    assert not INVENTORY["technical_gates_verified"]
    assert not INVENTORY["provider_gates_verified"]
    assert not INVENTORY["production_authorized"]
    assert not INVENTORY["real_pix_enabled"]
    assert not INVENTORY["local_db_5433_touched"]
    assert not INVENTORY["oci_vm_touched"]
    assert not INVENTORY["migrations_applied"]
    assert not INVENTORY["real_users_enabled"]
    assert readiness_manifest({})["status"] == "BLOCKED"


@pytest.mark.parametrize("state", ["DIVERGENTE", "BLOQUEADO", "NÃO VERIFICADO", "PARCIAL"])
def test_no_historical_status_grants_release(state):
    selected = [r for r in INVENTORY["rows"] if r["baseline_status"] == state]
    assert len(selected) == EXPECTED_COUNTS[state]
    assert all(not row["production_authorized"] and not row["clause_e2e_passed"]
               for row in selected)


@pytest.mark.parametrize("tamper", ["duplicate", "promote", "delete", "extra",
                                   "missing_action", "unknown_stream", "empty_id"])
def test_baseline_tampering_blocks_audit(tmp_path, tamper):
    obj = json.loads((ROOT / BASELINE_PATH).read_text())
    rows = obj["clauses"]
    if tamper == "duplicate":
        rows[1]["id"] = rows[0]["id"]
    elif tamper == "promote":
        rows[0]["production_verified"] = True
    elif tamper == "delete":
        rows.pop()
    elif tamper == "extra":
        rows.append(deepcopy(rows[-1]))
    elif tamper == "missing_action":
        rows[0]["next_action"] = ""
    elif tamper == "unknown_stream":
        rows[0]["workstream"] = "UNKNOWN"
    else:
        rows[0]["id"] = "../escape"
    path = tmp_path / "forged.json"
    path.write_text(json.dumps(obj), encoding="utf8")
    with pytest.raises(ValueError, match="M29900"):
        _load_and_validate(path)


def test_missing_candidate_does_not_get_silent_approval(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json").write_text(
        (ROOT / BASELINE_PATH).read_text(), encoding="utf8"
    )
    result = build_inventory(tmp_path)
    assert len(result["missing_candidate_clause_ids"]) == 147
    assert not result["production_authorized"]


def test_untrusted_inventory_cannot_claim_at_acceptance():
    fake = deepcopy(INVENTORY)
    fake["rows"] = []
    with pytest.raises(ValueError, match="M30300_AT_BASELINE_MISSING"):
        build_at_programme(fake)


def test_no_remote_or_mutating_service_in_audit_module():
    s = (ROOT / "backend/app/contract_clause_coverage.py").read_text()
    for forbidden in ("asyncpg.connect(", "psycopg.connect(", "requests.post(",
                      "oci.core", "psql -", "subprocess.run", "open_url(",
                      "INSERT INTO ", "UPDATE public.", "DELETE FROM"):
        assert forbidden not in s
