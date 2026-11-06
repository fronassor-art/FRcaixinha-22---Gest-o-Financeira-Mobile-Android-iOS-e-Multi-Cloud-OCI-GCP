"""M22300 cookie Origin anti-CSRF; no database required."""
import pytest
from fastapi.testclient import TestClient
from app.cookie_origin_guard import allow_cookie_request
from app.main import app


@pytest.mark.parametrize("method",["POST","PUT","PATCH","DELETE","PROPFIND"])
def test_cookie_write_rejects_missing_or_foreign_origin(method):
    for origin in ([],["null"],["https://outside.example"],
                   ["http://localhost:3000","http://localhost:3000"],
                   ["http://localhost:3000 "]):
        assert not allow_cookie_request(
            method=method,session_cookie_present=True,origins=origin,
            allowed_origins=["http://localhost:3000"])


def test_single_exact_origin_is_permitted_only_when_configured():
    assert allow_cookie_request(
        method="POST",session_cookie_present=True,
        origins=["https://app.frfinance.com.br"],
        allowed_origins=["https://app.frfinance.com.br"])
    assert not allow_cookie_request(
        method="POST",session_cookie_present=True,
        origins=["http://app.frfinance.com.br"],
        allowed_origins=["https://app.frfinance.com.br"])


def test_mobile_bearer_without_cookie_is_unaffected():
    assert allow_cookie_request(
        method="POST",session_cookie_present=False,
        origins=[],allowed_origins=[])


def test_safe_reads_and_options_do_not_require_origin():
    for method in ("GET","HEAD","OPTIONS"):
        assert allow_cookie_request(
            method=method,session_cookie_present=True,
            origins=[],allowed_origins=[])


def test_integration_fails_before_post_route_for_cookie_cross_origin():
    with TestClient(app) as c:
        response=c.post(
            "/api/v1/auth/forgot-password",
            json={"email":"synthetic@example.invalid"},
            cookies={"frcaixinha_session":"synthetic"},
        )
        assert response.status_code==403
        assert response.headers["cache-control"]=="no-store"
        assert response.headers["referrer-policy"]=="no-referrer"
        assert "token" not in response.text.lower()


def test_integration_cookie_allowed_origin_uses_ordinary_route_policy():
    with TestClient(app) as c:
        r=c.post("/api/v1/auth/forgot-password",
                 json={"email":"synthetic@example.invalid"},
                 cookies={"frcaixinha_session":"synthetic"},
                 headers={"Origin":"http://localhost:3000"})
        # The missing email provider/backend is correctly still unavailable.
        assert r.status_code==503
        assert r.headers["cache-control"]=="no-store"
        assert r.headers["x-frame-options"]=="DENY"


def test_no_cookie_post_still_hits_normal_endpoint():
    with TestClient(app) as c:
        r=c.post("/api/v1/auth/forgot-password",
                 json={"email":"synthetic@example.invalid"})
        assert r.status_code==503
