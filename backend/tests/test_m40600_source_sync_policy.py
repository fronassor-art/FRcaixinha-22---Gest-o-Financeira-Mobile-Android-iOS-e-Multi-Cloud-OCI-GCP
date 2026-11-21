"""M40600: no runtime attestation invented by a source-only sync."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from backend.scripts.frfinance_m40600_source_sync_only import classify_probe

HEALTH = {"M39800_HEALTH": "FR_FINANCE_ONLINE"}
RESTRICTED = {
    **HEALTH,
    "M39800_STATUS": "BLOCKED_NO_PROCESS_PROOF",
    "M39800_PROC": "ANDROID_PROC_RESTRICTED",
    "M39800_PROCESS_ORIGIN": "AMBIGUOUS_OR_NOT_VISIBLE",
}
ATTESTED = {
    **HEALTH,
    "M39800_STATUS": "PASS_ORIGINAL_FASTAPI_OWNER_IDENTIFIED",
    "M39800_PROCESS_ORIGIN": "ORIGINAL_FR_FINANCE_UVICORN_PROCESS",
}


def test_original_android_restriction_is_advisory_for_source_only():
    assert classify_probe(2, RESTRICTED) == "SOURCE_SYNC_ALLOWED_RUNTIME_OWNER_NOT_ATTESTED"


def test_attested_probe_does_not_attest_runtime_after_sync():
    assert classify_probe(0, ATTESTED) == "SOURCE_SYNC_ALLOWED_RUNTIME_OWNER_ATTESTED_AT_PROBE"


def test_unexpected_error_code_fails_closed():
    assert classify_probe(1, RESTRICTED).startswith("BLOCKED_")


def test_wrong_health_fails_closed():
    assert classify_probe(2, {**RESTRICTED, "M39800_HEALTH": "NOT_ATTESTED"}).startswith("BLOCKED_")


def test_unknown_proc_fails_closed():
    assert classify_probe(2, {**RESTRICTED, "M39800_PROC": "WRONG_WORKTREE"}).startswith("BLOCKED_")


def test_wrong_process_origin_fails_closed():
    assert classify_probe(2, {**RESTRICTED, "M39800_PROCESS_ORIGIN": "WRONG_WORKTREE"}).startswith("BLOCKED_")


def test_mismatched_success_fails_closed():
    assert classify_probe(0, RESTRICTED).startswith("BLOCKED_")


def test_missing_markers_fail_closed():
    assert classify_probe(0, {}).startswith("BLOCKED_")


def test_source_sync_is_only_explicit_git_fast_forward():
    s=(ROOT/"backend/scripts/frfinance_m40600_source_sync_only.py").read_text()
    for marker in ('"merge", "--ff-only", "FETCH_HEAD"', '"core.hooksPath=/dev/null"',
                   '"rev-parse", "FETCH_HEAD"', '"--untracked-files=no"',
                   '"merge-base", "--is-ancestor"', 'PYTHONDONTWRITEBYTECODE'):
        assert marker in s
    assert 'os.system(' not in s
    assert 'shell=True' not in s
    assert '"reset", "--hard"' not in s


def test_real_operations_are_never_performed():
    s=(ROOT/"backend/scripts/frfinance_m40600_source_sync_only.py").read_text()
    for marker in ("M40600_PROCESS_RESTART=NONE", "M40600_RUNTIME_RELOAD=NONE",
                   "M40600_DB_CONNECTIONS=NONE", "M40600_DB_WRITES=NONE",
                   "M40600_MIGRATIONS=NONE", "M40600_PRODUCTION=BLOCKED"):
        assert marker in s
