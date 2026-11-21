"""CP20261117: synthetic only; never original PostgreSQL, Android or OCI."""
import json
import pytest
from backend.scripts import frfinance_cp20261117_offline_checkpoint as m

@pytest.fixture
def matrix():
    return json.loads((m.ROOT / m.MATRIX).read_text(encoding="utf-8"))

def test_complete_330_no_go(matrix):
    assert m.check_matrix(matrix) == "PASS_330_ITEM_DOCUMENTARY_MATRIX_NO_GO"
    assert sum(m.FAMILIES.values()) == 330

@pytest.mark.parametrize("field,value,expected", [
    ("count", None, "BLOCKED_MATRIX_TOTAL"),
    ("approval", True, "BLOCKED_UNATTESTED_PRODUCTION_APPROVAL"),
    ("duplicate", None, "BLOCKED_ITEM_COUNTS_OR_DUPLICATES"),
    ("category", "UNAUTHORIZED", "BLOCKED_ITEM_FAMILY"),
    ("live", 1, "BLOCKED_UNVERIFIED_GATES_PROMOTED"),
    ("provider", 1, "BLOCKED_UNVERIFIED_GATES_PROMOTED"),
    ("e2e", 1, "BLOCKED_UNVERIFIED_GATES_PROMOTED"),
    ("go", None, "BLOCKED_RELEASE_DECISION"),
])
def test_fails_closed_when_evidence_changes(matrix, field, value, expected):
    if field == "count":
        matrix["items"].pop()
    elif field == "approval":
        matrix["items"][0]["production_verified"] = value
    elif field == "duplicate":
        matrix["items"][0]["check_id"] = matrix["items"][1]["check_id"]
    elif field == "category":
        matrix["items"][0]["family"] = value
    elif field == "live":
        matrix["evidence_status"]["live_release_gates_verified"] = value
    elif field == "provider":
        matrix["evidence_status"]["external_provider_gates_verified"] = value
    elif field == "e2e":
        matrix["evidence_status"]["AT_scenarios_e2e_verified"] = value
    else:
        matrix["release_decision"] = "GO"
    assert m.check_matrix(matrix) == expected

def test_source_guards_pass_static():
    assert m.check_sources() == "PASS_STATIC_SOURCE_GUARDS_NOT_RUNTIME_ATTESTED"

@pytest.mark.parametrize("name", sorted(m.REQUIRED_SOURCE_GATES))
def test_missing_source_fail_closed(tmp_path, name):
    assert m.check_sources(tmp_path, {name: ("absent.py", ("needle",))}) == (
        "BLOCKED_" + name + "_MISSING")

def test_drift_source_fail_closed(tmp_path):
    f=tmp_path/"x.py"
    f.write_text("wrong", encoding="utf-8")
    assert m.check_sources(tmp_path, {"TEST": ("x.py", ("required",))}) == (
        "BLOCKED_TEST_SOURCE_DRIFT")

def test_runtime_not_attested_by_offline_report(matrix):
    r=m.report(matrix=matrix)
    assert r["CP20261117_STATUS"] == "PASS_OFFLINE_GITHUB_CHECKPOINT_NO_GO"
    assert r["CP20261117_OCI_VM"] == "NOT_ATTESTED_BY_OFFLINE_CI"
    assert r["CP20261117_POSTGRESQL_LIVE_RLS"] == "NOT_ATTESTED_BY_OFFLINE_CI"
    assert r["CP20261117_PRODUCTION"] == "BLOCKED"

def test_missing_json_blocks(tmp_path):
    assert m.report(root=tmp_path)["CP20261117_STATUS"] == "BLOCKED_MATRIX_UNREADABLE"

def test_script_has_no_network_db_or_oci_calls():
    s=(m.ROOT/"backend/scripts/frfinance_cp20261117_offline_checkpoint.py").read_text()
    for unsafe in ("requests.get(", "psycopg.connect(", "asyncpg.connect(",
                   "launch_instance(", "subprocess.run(", "subprocess.Popen(",
                   "os.kill(", "shutil.rmtree("):
        assert unsafe not in s
