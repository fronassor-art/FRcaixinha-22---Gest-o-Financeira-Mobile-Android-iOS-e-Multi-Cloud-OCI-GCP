"""M40220: synthesize anonymous denial, including hidden M40060 endpoints.

No live DB, no tokens or logged-in sessions, no POST, external delivery or Pix.
"""
import ast
from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app import dependencies as deps
import pytest

from backend.scripts import frfinance_m40220_anonymous_role_boundaries_readonly as m

ROOT = Path(__file__).resolve().parents[2]


def test_anon_source_rejects_before_postgres_connect():
    assert m.anonymous_guard_source() == "PASS_NO_TOKEN_REJECTED_BEFORE_DB"


def test_source_guard_fails_when_token_checked_after_connect(tmp_path):
    original = ROOT.joinpath("backend/app/dependencies.py").read_text()
    block = original.replace("raw_token = bearer_token(request)",
                             "raw_token = bearer_token(request)", 1)
    # Remove the fail-closed call from the ASGI source function.
    block = block.replace("raw_token = bearer_token(request)",
                          "raw_token = request.headers.get('Authorization', '')", 1)
    altered = tmp_path / "deps.py"
    altered.write_text(block)
    assert m.anonymous_guard_source(altered) == "BLOCKED_AUTH_SOURCE_UNVERIFIED"


def test_no_arbitrary_http_targets():
    with pytest.raises(ValueError):
        m.anonymous_http_status("/api/health")
    with pytest.raises(ValueError):
        m.guarded_status(lambda _: 401, "/api/v1/auth/logout")
    assert m.HOST == "http://127.0.0.1:8000"
    assert len(m.ALLOWED) == len(m.PROBES) == 12


@pytest.mark.parametrize("key", tuple(m.PROBES.keys()))
def test_all_routes_reject_anonymous_in_synthetic_app(key, monkeypatch):
    async def no_db(*args, **kwargs):
        raise AssertionError("NO DB allowed for anonymous requests")
    monkeypatch.setattr(deps.asyncpg, "connect", no_db)
    monkeypatch.setattr("app.database.get_db_pool", no_db)
    app.dependency_overrides.clear()
    try:
        with TestClient(app) as client:
            response = client.get(m.PROBES[key], follow_redirects=False)
        assert response.status_code == 401, key
    finally:
        app.dependency_overrides.clear()


def default_report(**kwargs):
    params = {
        "preflight": lambda: {"M40190_STATUS": "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"},
        "hidden": lambda: "PASS_TWO_HIDDEN_SOURCE_DECLARATIONS_NOT_RUNTIME_TESTED",
        "auth": lambda: "PASS_NO_TOKEN_REJECTED_BEFORE_DB",
        "fetch": lambda path: 401,
        "health_fetch": lambda path: (
            200, {"app": "FR Finance", "status": "ONLINE"}),
    }
    params.update(kwargs)
    return m.report(**params)


def test_all_anonymous_guards_pass_without_claiming_role_rls():
    result = default_report()
    assert result["M40220_STATUS"] == "PASS_ANONYMOUS_401_BOUNDARIES_ONLY"
    assert result["M40220_ANONYMOUS_401_COUNT"] == "12"
    assert result["M40220_LIVE_ROLE_RBAC"] == "NOT_TESTED"
    assert result["M40220_POSTGRESQL_RLS"] == "NOT_TESTED"
    assert result["M40220_MEMBER_SESSIONS"] == "NOT_CREATED_BY_THIS_PROBE"


@pytest.mark.parametrize("status", (0, 200, 302, 403, 404, 500, 503))
def test_unexpected_http_denied_as_insufficient_evidence(status):
    r = default_report(fetch=lambda _: status)
    assert r["M40220_STATUS"] == "BLOCKED_ANONYMOUS_ROUTE_GUARD"
    assert r["M40220_ANONYMOUS_401_COUNT"] == "0"


def test_preflight_fail_never_calls_protected_routes():
    r = default_report(
        preflight=lambda: {"M40190_STATUS": "BLOCKED_UNEXPECTED"},
        fetch=lambda _: pytest.fail("Protected HTTP should not be called"),
    )
    assert r["M40220_STATUS"] == "BLOCKED_M40190_READINESS"


def test_hidden_router_change_never_calls_routes():
    r = default_report(hidden=lambda: "BLOCKED_HIDDEN_CONFIG",
                       fetch=lambda _: pytest.fail("No calls when hidden drift"))
    assert r["M40220_STATUS"] == "BLOCKED_HIDDEN_ROUTE_SOURCE"


def test_auth_source_change_never_calls_routes():
    r = default_report(auth=lambda: "BLOCKED_AUTH_GUARD",
                       fetch=lambda _: pytest.fail("No calls when auth drift"))
    assert r["M40220_STATUS"] == "BLOCKED_SESSION_GUARD_SOURCE"


def test_last_health_changed_fails_closed():
    r = default_report(health_fetch=lambda _: (0, None))
    assert r["M40220_STATUS"] == "BLOCKED_HEALTH_CHANGED"


def test_unexpected_single_route_fails_closed_without_other_calls():
    routes = []
    def fetch(path):
        routes.append(path)
        return 404 if len(routes) == 2 else 401
    result = default_report(fetch=fetch)
    assert result["M40220_STATUS"] == "BLOCKED_ANONYMOUS_ROUTE_GUARD"
    assert result["M40220_ANONYMOUS_401_COUNT"] == "1"
    assert len(routes) == 2


def test_source_and_live_guard(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40220_LIVE_ENDPOINTS=NOT_QUERIED" in capsys.readouterr().out
    assert m.main([]) == 2


def test_probe_has_no_mutating_or_other_network_implementation():
    source=(ROOT / "backend/scripts/frfinance_m40220_anonymous_role_boundaries_readonly.py"
            ).read_text(encoding="utf-8")
    assert "ProxyHandler({})" in source and "NoRedirect()" in source
    assert 'method="GET"' in source
    for unsafe in ("requests.post(", "Request(HOST + path, method=\"POST\"",
                   "psycopg.connect(", "subprocess.Popen(",
                   "os.kill(", "pg_ctl start", "pg_ctl stop", "shell=True"):
        assert unsafe not in source

# A literal string used to check auth-before-DB is NOT a connection call.
def test_no_actual_asyncpg_connect_call_in_probe_source_ast():
    source = (
        ROOT / "backend/scripts/frfinance_m40220_anonymous_role_boundaries_readonly.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "asyncpg"
        and node.func.attr == "connect"
        for node in ast.walk(tree)
    )
