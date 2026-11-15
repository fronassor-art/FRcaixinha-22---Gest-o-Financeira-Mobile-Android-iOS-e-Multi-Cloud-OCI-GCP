"""FR Finance M40120: HTTP-only double-check, no process or DB touch."""
from pathlib import Path
import pytest

from backend.scripts import frfinance_m40120_http_health_disambiguation_readonly as m

GOOD = {"app": "FR Finance", "status": "ONLINE"}
FOREIGN = {"app": "Other app", "status": "ONLINE"}


def fake_fetch(healths, checkpoint=(404, None), marker=(404, None)):
    queue = list(healths)
    calls = []
    def fetch(path):
        calls.append(path)
        if path == m.HEALTH:
            assert queue, "Unexpected health request"
            return queue.pop(0)
        if path == m.CHECKPOINT:
            return checkpoint
        if path == m.MARKER:
            return marker
        pytest.fail("Unexpected or non-loopback endpoint")
    return fetch, calls


@pytest.mark.parametrize("code,expected", [
    (0, "BLOCKED_HEALTH_NO_RESPONSE"),
    (404, "BLOCKED_HEALTH_ROUTE_NOT_FOUND"),
    (401, "BLOCKED_HEALTH_ACCESS_RESTRICTED"),
    (403, "BLOCKED_HEALTH_ACCESS_RESTRICTED"),
    (500, "BLOCKED_HEALTH_SERVER_ERROR"),
    (503, "BLOCKED_HEALTH_SERVER_ERROR"),
    (429, "BLOCKED_HEALTH_HTTP_UNVERIFIED"),
])
def test_two_identical_http_failures_skip_markers(code, expected):
    fetch, calls = fake_fetch([(code, None), (code, None)])
    answer = m.report(fetch)
    assert answer["M40120_STATUS"] == expected
    assert calls == [m.HEALTH, m.HEALTH]
    assert answer["M40120_PROCESS_OWNER"] == "NOT_ATTESTED"
    assert answer["M40120_RESTART_AUTHORIZED"] == "FALSE"


def test_status_flap_blocks_without_followup_requests():
    fetch, calls = fake_fetch([(200, GOOD), (404, None)])
    result = m.report(fetch)
    assert result["M40120_STATUS"] == "BLOCKED_HEALTH_HTTP_CHANGED_BETWEEN_PROBES"
    assert calls == [m.HEALTH, m.HEALTH]


@pytest.mark.parametrize("healths, expected", [
    ([(200, GOOD), (200, FOREIGN)], "BLOCKED_HEALTH_IDENTITY_CHANGED_BETWEEN_PROBES"),
    ([(200, FOREIGN), (200, FOREIGN)], "BLOCKED_HEALTH_APP_IDENTITY_UNVERIFIED"),
    ([(200, None), (200, None)], "BLOCKED_HEALTH_APP_IDENTITY_UNVERIFIED"),
])
def test_wrong_or_changed_identity_never_inspects_process(healths, expected):
    fetch, calls = fake_fetch(healths)
    answer = m.report(fetch)
    assert answer["M40120_STATUS"] == expected
    assert calls == [m.HEALTH, m.HEALTH]


def test_known_app_missing_both_markers_is_not_upgrade_permission():
    fetch, calls = fake_fetch([(200, GOOD), (200, GOOD), (200, GOOD)])
    r = m.report(fetch)
    assert calls == [m.HEALTH, m.HEALTH, m.CHECKPOINT, m.MARKER, m.HEALTH]
    assert r["M40120_CHECKPOINT_HTTP"] == "HTTP_404"
    assert r["M40120_MARKER_HTTP"] == "HTTP_404"
    assert r["M40120_STATUS"] == "BLOCKED_BOTH_RUNTIME_MARKERS_404_OWNER_UNVERIFIED"
    assert r["M40120_LOADED_CODE"] == "NOT_ATTESTED"


def test_even_successful_marker_statuses_do_not_prove_code():
    fetch, _ = fake_fetch([(200, GOOD), (200, GOOD), (200, GOOD)],
                          checkpoint=(200, {"some": "json"}),
                          marker=(200, {"some": "json"}))
    r = m.report(fetch)
    assert r["M40120_STATUS"] == "BLOCKED_RUNTIME_OWNER_AND_LOADED_CODE_UNVERIFIED"
    assert r["M40120_MARKER_HTTP"] == "HTTP_200"
    assert r["M40120_RESTART_AUTHORIZED"] == "FALSE"


def test_health_changes_after_marker_probe_fails_closed():
    fetch, _ = fake_fetch([(200, GOOD), (200, GOOD), (503, None)])
    r = m.report(fetch)
    assert r["M40120_STATUS"] == "BLOCKED_HEALTH_CHANGED_DURING_MARKER_PROBES"
    assert r["M40120_HEALTH_FINAL_HTTP"] == "HTTP_503"


def test_bad_fetcher_result_and_exception_fails_closed():
    assert m.guarded_get(lambda _: ("200", None), m.HEALTH) == (0, None)
    assert m.guarded_get(lambda _: (200,), m.HEALTH) == (0, None)
    def err(_):
        raise OSError("do not expose details")
    fetch, calls = fake_fetch([(200, GOOD), (200, GOOD)])
    # Guarded wrapper never exposes exceptions, raw payload or tracebacks.
    assert m.guarded_get(err, m.HEALTH) == (0, None)
    with pytest.raises(ValueError):
        m.guarded_get(err, "/not-in-allowlist")
    assert calls == []


def test_native_termux_gate_and_source_only(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40120_RUNTIME=NOT_ATTESTED" in capsys.readouterr().out
    assert m.main([]) == 2


def test_no_unsafe_calls_or_secrets_in_source():
    source = (Path(__file__).resolve().parents[2] /
              "backend/scripts/frfinance_m40120_http_health_disambiguation_readonly.py"
              ).read_text(encoding="utf-8")
    for expected in ("M40120_FASTAPI_RESTART=NONE",
                     "M40120_DATABASE_CONNECTIONS=NONE",
                     "M40120_LOCAL_DB_WRITES=NONE",
                     "M40120_MIGRATIONS=NONE",
                     "M40120_PIX_REAL=OFF",
                     "M40120_PRODUCTION=BLOCKED"):
        assert expected in source
    for unsafe in ("os.kill(", "subprocess.run(", "subprocess.Popen(",
                   "psycopg.connect(", "asyncpg.connect(", "shell=True",
                   "pg_ctl", "uvicorn.run(", "print(document)",
                   "print(first_doc)", "print(second_doc)"):
        assert unsafe not in source
