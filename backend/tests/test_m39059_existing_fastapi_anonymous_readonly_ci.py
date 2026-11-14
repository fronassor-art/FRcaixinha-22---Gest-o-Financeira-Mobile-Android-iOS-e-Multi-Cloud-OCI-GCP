"""M39059 — testes sintéticos da sondagem de API existente, sem rede real."""
from pathlib import Path
import pytest
from backend.scripts import frfinance_m39059_existing_fastapi_anonymous_readonly as m


def responses(mode="TEST_MODE", ready=200, me=401, credit=401, cors=True, health=True):
    return {
        ("/api/health", "GET"): (200, {"app": "FR Finance", "status": "ONLINE"})
            if health else (200, {"app": "FR Caixinha 2.2", "status": "ONLINE"}),
        ("/api/v1/auth/status", "GET"): (
            200, {"status": mode, "requires_authentication": True}
        ),
        ("/api/v1/auth/me", "GET"): (me, {}),
        (m.CREDIT, "GET"): (credit, {}),
        ("/api/v1/auth/status", "OPTIONS"): (
            200 if cors else 403,
            {"origin": "http://localhost" if cors else None,
             "credentials": "true" if cors else None},
        ),
        ("/api/health/ready", "GET"): (
            ready, {"status": "READY_FOR_TEST_AUTH", "scope": "LOCAL_HOMOLOGATION_ONLY"}
            if ready == 200 else {},
        ),
    }


def run_probe(monkeypatch, **kwargs):
    calls = []
    samples = responses(**kwargs)
    def fake(path, method="GET"):
        calls.append((path, method))
        return samples[(path, method)]
    monkeypatch.setattr(m, "request_local", fake)
    return m.probe(), calls


def test_safe_ready_local_homologation(monkeypatch):
    out, calls = run_probe(monkeypatch)
    assert out["M39059_STATUS"] == "PASS_LOCAL_TEST_READINESS"
    assert out["M39059_ANONYMOUS_ME"] == "DENIED_401"
    assert out["M39059_ANONYMOUS_SPECIAL_CREDIT"] == "DENIED_401"
    assert out["M39059_ANDROID_CORS"] == "PASS"
    assert calls == [
        ("/api/health", "GET"),
        ("/api/v1/auth/status", "GET"),
        ("/api/v1/auth/me", "GET"),
        (m.CREDIT, "GET"),
        ("/api/v1/auth/status", "OPTIONS"),
        ("/api/health/ready", "GET"),
    ]


@pytest.mark.parametrize("kwargs", [
    {"ready": 503}, {"me": 200}, {"credit": 200}, {"cors": False},
    {"mode": "BLOCKED_PENDING_CONFIG"}, {"mode": "BLOCKED_PENDING_IMPLEMENTATION"},
])
def test_fail_closed_when_not_ready_or_anonymous_allowed(monkeypatch, kwargs):
    out, _ = run_probe(monkeypatch, **kwargs)
    assert out["M39059_STATUS"] == "BLOCKED_API_CONFIGURATION_OR_GUARDS"


def test_block_other_application_immediately(monkeypatch):
    out, calls = run_probe(monkeypatch, health=False)
    assert out["M39059_STATUS"] == "BLOCKED_FASTAPI_NOT_IDENTIFIED"
    assert calls == [("/api/health", "GET")]


def test_never_call_unknown_url_or_post():
    with pytest.raises(ValueError, match="UNAPPROVED"):
        m.request_local("/api/v1/auth/login")
    with pytest.raises(ValueError, match="UNAPPROVED"):
        m.request_local("/api/health", "POST")
    with pytest.raises(ValueError, match="UNAPPROVED"):
        m.request_local("/api/v1/auth/me", "OPTIONS")
    assert m.NoRedirects().redirect_request(None, None, 302, "Found", {}, "https://example.com") is None


def test_main_offline_fake_not_e2e(monkeypatch, capsys):
    monkeypatch.setattr(m, "verify_original", lambda: None)
    monkeypatch.setattr(m, "probe", lambda: {"M39059_STATUS": "PASS_LOCAL_TEST_READINESS"})
    assert m.main() == 0
    out = capsys.readouterr().out
    assert "M39059_REAL_LOGIN=NOT_ATTEMPTED" in out
    assert "M39059_PRODUCTION=BLOCKED" in out


def test_source_guards():
    source = (Path(__file__).resolve().parents[1] /
              "scripts/frfinance_m39059_existing_fastapi_anonymous_readonly.py").read_text()
    assert 'urllib.request.ProxyHandler({})' in source
    assert 'NoRedirects()' in source
    assert 'verify_original()' in source
    assert '"/api/health/ready"' in source
    assert '"OPTIONS"' in source
    for forbidden in ('"POST"', '"PUT"', '"DELETE"', "ALTER ROLE",
                      "INSERT INTO", "uvicorn.run(", "subprocess.Popen(",
                      "print(json.dumps(ready))"):
        assert forbidden not in source
