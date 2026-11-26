"""M41180 offline proof for the legacy GUC-backed GET/HEAD read guard."""
from __future__ import annotations

import asyncio
import datetime as dt
import importlib
from types import SimpleNamespace
from uuid import uuid4

from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from backend.app import database
from backend.app.dependencies import AuthenticatedSession, get_current_session


def _verified_test_session() -> AuthenticatedSession:
    now = dt.datetime.now(dt.timezone.utc)
    return AuthenticatedSession(
        user_id=str(uuid4()),
        role="TENANT_ADMIN",
        tenant_id=str(uuid4()),
        email="m41180@example.invalid",
        name="M41180 synthetic session",
        is_master=False,
        verified_session_id=str(uuid4()),
        verified_session_at=now,
        verified_session_expires_at=now + dt.timedelta(minutes=5),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )


def _app() -> FastAPI:
    app = FastAPI()
    app.dependency_overrides[get_current_session] = lambda: _verified_test_session()

    @app.api_route("/legacy-read", methods=["GET", "HEAD"])
    async def legacy_read(connection=Depends(database.get_rls_db_connection)):
        return {"reached": True}

    @app.post("/legacy-post")
    async def legacy_post(connection=Depends(database.get_rls_db_connection)):
        return {"dependency": "reached"}

    return app


def test_get_and_head_fail_closed_before_financial_pool_under_concurrency(monkeypatch):
    pool_calls: list[str] = []

    async def forbidden_financial_pool():
        pool_calls.append("called")
        raise AssertionError("M41180_FINANCIAL_POOL_MUST_NOT_BE_ACQUIRED")

    monkeypatch.setattr(database, "get_db_pool", forbidden_financial_pool)
    app = _app()

    async def exercise():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://m41180.test",
        ) as client:
            responses = await asyncio.gather(
                *(
                    client.request(method, "/legacy-read")
                    for _ in range(12)
                    for method in ("GET", "HEAD")
                )
            )
        assert len(responses) == 24
        assert all(response.status_code == 503 for response in responses)
        for response in responses:
            if response.request.method == "GET":
                assert (
                    response.json()["detail"]
                    == "Leitura financeira bloqueada até contexto SQL atestado."
                )

    asyncio.run(exercise())
    assert pool_calls == []


def test_m40070_disposable_exception_requires_marker_and_exact_local_dsns(monkeypatch):
    app_dsn = (
        "postgresql://fr_m40070_app:m40070-app-ci-only"
        "@127.0.0.1:5432/frcaixinha_ci"
    )
    auth_dsn = (
        "postgresql://fr_m40070_auth:m40070-auth-ci-only"
        "@127.0.0.1:5432/frcaixinha_ci"
    )
    for key, value in {
        "GITHUB_ACTIONS": "true",
        "CI_M40070_DISPOSABLE": "1",
        "ENVIRONMENT": "development",
        "FRCAIXINHA_TEST_AUTH": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
        "FR_FINANCE_PIX_REAL": "OFF",
        "FR_FINANCE_REAL_PAYMENTS": "OFF",
        "FR_FINANCE_REAL_USER_ACTIVATION": "OFF",
        "PGOPTIONS": "-c frfinance.m40070_ci=DISPOSABLE_ONLY",
        "DATABASE_URL": app_dsn,
        "AUTH_DATABASE_URL": auth_dsn,
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=app_dsn))
    state = SimpleNamespace(frfinance_m40070_disposable_read_test=True)
    request = SimpleNamespace(app=SimpleNamespace(state=state))

    assert database._m41180_m40070_disposable_read_exception(request) is True
    state.frfinance_m40070_disposable_read_test = False
    assert database._m41180_m40070_disposable_read_exception(request) is False
    state.frfinance_m40070_disposable_read_test = True
    monkeypatch.setenv("PIX_REAL", "ON")
    assert database._m41180_m40070_disposable_read_exception(request) is False
    monkeypatch.setenv("PIX_REAL", "OFF")
    monkeypatch.setenv("PGOPTIONS", "")
    assert database._m41180_m40070_disposable_read_exception(request) is False
    monkeypatch.setenv("PGOPTIONS", "-c frfinance.m40070_ci=DISPOSABLE_ONLY")
    monkeypatch.setenv("ENVIRONMENT", "production")
    assert database._m41180_m40070_disposable_read_exception(request) is False
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("DATABASE_URL", "postgresql://attacker@10.0.0.2:5432/prod")
    assert database._m41180_m40070_disposable_read_exception(request) is False


def test_post_method_keeps_existing_dependency_path_with_only_fake_connection(monkeypatch):
    pool_calls: list[str] = []
    statements: list[str] = []
    transaction_events: list[str] = []

    class FakeTransaction:
        async def start(self):
            transaction_events.append("start")

        async def commit(self):
            transaction_events.append("commit")

        async def rollback(self):
            transaction_events.append("rollback")

    class FakeConnection:
        def transaction(self):
            return FakeTransaction()

        async def execute(self, query, *args):
            statements.append(query)
            return "OK"

    connection = FakeConnection()

    class FakeLease:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, exc_type, exc, traceback):
            return False

    class FakePool:
        def acquire(self):
            return FakeLease()

    async def fake_financial_pool():
        pool_calls.append("called")
        return FakePool()

    # These overrides exist only in this offline unit test. No real SQL driver,
    # database, release gate, or runtime is contacted.
    release_gate = importlib.import_module(
        "backend.app.m40840_financial_sql_release_no_go"
    )
    monkeypatch.setattr(
        release_gate, "require_nonproduction_financial_sql", lambda env: None
    )
    monkeypatch.setattr(
        database, "settings", SimpleNamespace(is_database_configured=True)
    )
    monkeypatch.setattr(database, "get_db_pool", fake_financial_pool)
    app = _app()

    async def exercise():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://m41180.test",
        ) as client:
            response = await client.post("/legacy-post")
        assert response.status_code == 200
        assert response.json() == {"dependency": "reached"}

    asyncio.run(exercise())
    assert pool_calls == ["called"]
    assert transaction_events == ["start", "commit"]
    assert sum("set_config('app.current_" in query for query in statements) == 3
    assert "RESET ALL; DISCARD TEMP;" in statements
