"""M40190: synthetic local readiness independent of protected Android /proc."""
from pathlib import Path

import pytest

from backend.scripts import frfinance_m40190_operational_readonly_checkpoint as m
from backend.app.m39700_runtime_contract import (
    checkpoint_payload, EXPECTED_GET,
)

ROOT = Path(__file__).resolve().parents[2]


def fake_hashes():
    return {key: "a" * 64 for key in (
        "main_py_sha256_at_import",
        "review_router_sha256_at_import",
        "marker_py_sha256_at_import",
    )}


def good_documents():
    return {
        m.HEALTH: (200, {"app": "FR Finance", "status": "ONLINE"}),
        m.CHECKPOINT: (200, checkpoint_payload()),
        m.MARKER: (200, {
            "product": "FR Finance",
            "workstream": "AI_STUDIO",
            "contract": "FR_FINANCE_M40080_LOADED_SOURCE_V1",
            "source_fingerprints_captured_on_import": True,
            **fake_hashes(),
            "git_commit_verified": False,
            "executable_bytecode_attested": False,
            "process_owner_verified": False,
            "real_session_revocation_attested": False,
            "review_policy_ratified": False,
            "financial_approval_enabled": False,
            "pix_real_enabled": False,
            "production_authorized": False,
        }),
        m.ROUTES: (200, {"paths": {path: {"get": {}} for path in EXPECTED_GET}}),
        m.READY: (200, {"status": "READY_FOR_TEST_AUTH",
                        "scope": "LOCAL_HOMOLOGATION_ONLY"}),
    }


def run_probe(override=None, hashes=fake_hashes):
    docs = good_documents()
    docs.update(override or {})
    return m.report(fetch=lambda path: docs[path], hashes=hashes)


def test_success_does_not_prove_process_owner_or_real_finances():
    r = run_probe()
    assert r["M40190_STATUS"] == "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"
    assert r["M40190_EXPECTED_GET_ROUTES"] == "SIX_OF_SIX_PRESENT"
    assert r["M40190_TEST_AUTH_READINESS"] == "LOCAL_TEST_AUTH_READY"
    assert r["M40190_PROCESS_OWNER"] == "NOT_ATTESTED_ANDROID_OR_UNKNOWN"
    assert r["M40190_GIT_SHA_IN_RUNNING_PROCESS"] == "NOT_ATTESTED"
    assert r["M40190_EXECUTED_BYTECODE"] == "NOT_ATTESTED"
    assert r["M40190_REAL_PAYMENTS"] == "OFF"


@pytest.mark.parametrize("changes,state", [
    ({m.HEALTH: (0, None)}, "BLOCKED_HEALTH_IDENTITY"),
    ({m.HEALTH: (200, {"app": "other", "status": "ONLINE"})},
     "BLOCKED_HEALTH_IDENTITY"),
    ({m.CHECKPOINT: (404, None)}, "BLOCKED_RUNTIME_CONTRACT"),
    ({m.MARKER: (404, None)}, "BLOCKED_LOADED_SOURCE_UNVERIFIED"),
    ({m.READY: (503, None)}, "BLOCKED_TEST_AUTH_READINESS"),
    ({m.ROUTES: (200, {"paths": {}})}, "BLOCKED_EXPECTED_GET_ROUTES"),
])
def test_refuse_incomplete_readiness(changes, state):
    assert run_probe(changes)["M40190_STATUS"] == state


def test_fingerprint_mismatch_not_equivalent_to_pid_failure():
    docs = good_documents()
    docs[m.MARKER][1]["main_py_sha256_at_import"] = "b" * 64
    r = m.report(fetch=lambda path: docs[path], hashes=fake_hashes)
    assert r["M40190_STATUS"] == "BLOCKED_LOADED_SOURCE_UNVERIFIED"


def test_final_health_change_blocked():
    calls = []
    docs = good_documents()
    def fetch(path):
        calls.append(path)
        if path == m.HEALTH and calls.count(m.HEALTH) == 2:
            return 0, None
        return docs[path]
    r = m.report(fetch=fetch, hashes=fake_hashes)
    assert r["M40190_STATUS"] == "BLOCKED_HEALTH_CHANGED_DURING_CHECK"


def test_wrong_health_never_probes_readiness():
    calls = []
    def fetch(path):
        calls.append(path)
        return 200, {"app": "wrong"}
    r = m.report(fetch=fetch, hashes=fake_hashes)
    assert r["M40190_STATUS"] == "BLOCKED_HEALTH_IDENTITY"
    assert calls == [m.HEALTH]


def test_unavailable_local_hashes_blocks_http():
    def no_fetch(_):
        pytest.fail("Must not connect to unknown API without local sources")
    r = m.report(fetch=no_fetch, hashes=lambda: {})
    assert r["M40190_STATUS"] == "BLOCKED_LOCAL_SOURCE_NOT_ATTESTED"


def test_http_path_guard_and_no_other_network_targets():
    with pytest.raises(ValueError):
        m.safe_get("http://example.org")
    with pytest.raises(ValueError):
        m.guarded(lambda _: (200, {}), "/api/v1/users")
    assert m.HOST == "http://127.0.0.1:8000"
    assert m.ALLOWLIST == {m.HEALTH, m.CHECKPOINT, m.MARKER, m.ROUTES, m.READY}


def test_malformed_status_fails_closed():
    assert m.guarded(lambda _: ("200", {}), m.HEALTH) == (0, None)
    assert m.guarded(lambda _: None, m.HEALTH) == (0, None)


def test_source_only_and_termux_gate(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40190_RUNTIME=NOT_ATTESTED" in capsys.readouterr().out
    assert m.main([]) == 2


def test_no_process_or_database_writes_in_script():
    code=(ROOT / "backend/scripts/frfinance_m40190_operational_readonly_checkpoint.py"
         ).read_text(encoding="utf-8")
    for tag in ("M40190_HTTP_POST=NONE", "M40190_LOGIN_SESSIONS_CREATED=NONE",
                "M40190_FASTAPI_START_STOP=NONE", "M40190_MIGRATIONS=NONE",
                "M40190_PRODUCTION=BLOCKED"):
        assert tag in code
    for unsafe in ("subprocess.Popen(", "os.kill(", "psycopg.connect(",
                   "asyncpg.connect(", "shell=True", "postmaster.pid",
                   "pg_ctl start", "pg_ctl stop"):
        assert unsafe not in code
