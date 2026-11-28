"""M41180 offline proof for the legacy GUC-backed GET/HEAD read guard."""
from __future__ import annotations

import ast
import asyncio
import datetime as dt
import importlib
from pathlib import Path
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


def _configure_disposable_ci_fixture(
    monkeypatch,
    *,
    profile,
    database_name,
    app_user,
    app_password,
    auth_user,
    auth_password,
    guc,
    verifier=None,
):
    app_dsn = (
        f"postgresql://{app_user}:{app_password}"
        f"@127.0.0.1:5432/{database_name}"
    )
    auth_dsn = (
        f"postgresql://{auth_user}:{auth_password}"
        f"@127.0.0.1:5432/{database_name}"
    )
    for key, value in {
        "GITHUB_ACTIONS": "true",
        f"CI_{profile}_DISPOSABLE": "1",
        "ENVIRONMENT": "development",
        "FRCAIXINHA_TEST_AUTH": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
        "FR_FINANCE_PIX_REAL": "OFF",
        "FR_FINANCE_REAL_PAYMENTS": "OFF",
        "FR_FINANCE_REAL_USER_ACTIVATION": "OFF",
        "PGOPTIONS": f"-c frfinance.{guc}=DISPOSABLE_ONLY",
        "DATABASE_URL": app_dsn,
        "AUTH_DATABASE_URL": auth_dsn,
    }.items():
        monkeypatch.setenv(key, value)
    if verifier is None:
        monkeypatch.delenv("AUTH_VERIFIER_DATABASE_URL", raising=False)
    else:
        verifier_user, verifier_password = verifier
        monkeypatch.setenv(
            "AUTH_VERIFIER_DATABASE_URL",
            f"postgresql://{verifier_user}:{verifier_password}"
            f"@127.0.0.1:5432/{database_name}",
        )
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=app_dsn))
    state = SimpleNamespace(frfinance_ci_disposable_read_test=True)
    return app_dsn, auth_dsn, SimpleNamespace(
        app=SimpleNamespace(state=state)
    )


def test_ci_disposable_exception_accepts_only_marked_fixture_profiles(monkeypatch):
    profiles = (
        {
            "profile": "M40070",
            "database_name": "frcaixinha_ci",
            "app_user": "fr_m40070_app",
            "app_password": "m40070-app-ci-only",
            "auth_user": "fr_m40070_auth",
            "auth_password": "m40070-auth-ci-only",
            "guc": "m40070_ci",
        },
        {
            "profile": "M40360",
            "database_name": "frcaixinha_ci",
            "app_user": "fr_m40360_app",
            "app_password": "m40360-app-ci-only",
            "auth_user": "fr_m40360_auth",
            "auth_password": "m40360-auth-ci-only",
            "guc": "m40360_ci",
            "verifier": ("fr_m40360_verifier", "m40360-verifier-ci-only"),
        },
        {
            "profile": "M40340",
            "database_name": "frfinance_ci_credit",
            "app_user": "frc_ai_app",
            "app_password": "m40340-app-ci-only",
            "auth_user": "fr_m40340_auth",
            "auth_password": "m40340-auth-ci-only",
            "guc": "m40340_ci",
        },
        {
            "profile": "M40380",
            "database_name": "frfinance_ci_credit",
            "app_user": "frc_ai_app",
            "app_password": "m40380-app-ci-only",
            "auth_user": "fr_m40380_auth",
            "auth_password": "m40380-auth-ci-only",
            "guc": "m40380_ci",
            "verifier": ("fr_m40380_verifier", "m40380-verifier-ci-only"),
        },
    )
    for profile in profiles:
        _, _, request = _configure_disposable_ci_fixture(monkeypatch, **profile)
        assert database._m41180_ci_disposable_read_exception(request) is True


def test_ci_disposable_exception_rejects_missing_marker_and_unsafe_context(monkeypatch):
    app_dsn, auth_dsn, request = _configure_disposable_ci_fixture(
        monkeypatch,
        profile="M40070",
        database_name="frcaixinha_ci",
        app_user="fr_m40070_app",
        app_password="m40070-app-ci-only",
        auth_user="fr_m40070_auth",
        auth_password="m40070-auth-ci-only",
        guc="m40070_ci",
    )
    state = request.app.state
    state.frfinance_ci_disposable_read_test = False
    assert database._m41180_ci_disposable_read_exception(request) is False
    state.frfinance_ci_disposable_read_test = True

    monkeypatch.delenv("CI_M40070_DISPOSABLE")
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv("CI_M41180_DISPOSABLE", "1")
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.delenv("CI_M41180_DISPOSABLE")
    monkeypatch.setenv("CI_M40070_DISPOSABLE", "1")

    monkeypatch.setenv("ENVIRONMENT", "production")
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv("ENVIRONMENT", "homologation")
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv("ENVIRONMENT", "development")

    for flag in (
        "PIX_REAL",
        "PAGAMENTOS_REAIS",
        "ATIVACAO_REAL",
        "FR_FINANCE_PIX_REAL",
        "FR_FINANCE_REAL_PAYMENTS",
        "FR_FINANCE_REAL_USER_ACTIVATION",
    ):
        monkeypatch.setenv(flag, "ON")
        assert database._m41180_ci_disposable_read_exception(request) is False
        monkeypatch.setenv(flag, "OFF")

    monkeypatch.setenv("PGOPTIONS", "")
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv(
        "PGOPTIONS", "-c frfinance.m40070_ci=DISPOSABLE_ONLY"
    )

    wrong_dsn = "postgresql://fr_m40070_app:ci-only@10.0.0.2:5432/frcaixinha_ci"
    monkeypatch.setenv("DATABASE_URL", wrong_dsn)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=wrong_dsn))
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv("DATABASE_URL", app_dsn)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=app_dsn))

    unsafe_dsn = "postgresql://fr_m40070_app:ci-only@127.0.0.1:5432/production"
    monkeypatch.setenv("DATABASE_URL", unsafe_dsn)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=unsafe_dsn))
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv("DATABASE_URL", app_dsn)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=app_dsn))

    privileged_dsn = "postgresql://postgres:ci-only@127.0.0.1:5432/frcaixinha_ci"
    monkeypatch.setenv("DATABASE_URL", privileged_dsn)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=privileged_dsn))
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv("DATABASE_URL", app_dsn)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=app_dsn))

    no_password = "postgresql://fr_m40070_app@127.0.0.1:5432/frcaixinha_ci"
    monkeypatch.setenv("DATABASE_URL", no_password)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=no_password))
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv("DATABASE_URL", app_dsn)
    monkeypatch.setattr(database, "settings", SimpleNamespace(DATABASE_URL=app_dsn))

    bad_auth_dsn = auth_dsn.replace("127.0.0.1", "10.0.0.3")
    monkeypatch.setenv("AUTH_DATABASE_URL", bad_auth_dsn)
    assert database._m41180_ci_disposable_read_exception(request) is False
    monkeypatch.setenv("AUTH_DATABASE_URL", auth_dsn)
    monkeypatch.delenv("AUTH_DATABASE_URL")
    assert database._m41180_ci_disposable_read_exception(request) is False


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



def test_existing_rls_http_harness_marks_only_after_disposable_database_preflight():
    repo_root = Path(__file__).resolve().parents[2]
    rls_path = repo_root / "backend" / "tests" / "test_rls_isolation_ci.py"
    rls_source = rls_path.read_text(encoding="utf-8")
    rls_tree = ast.parse(rls_source, filename=str(rls_path))
    fixture = next(
        node
        for node in rls_tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "isolated_rows"
    )
    fixture_source = ast.get_source_segment(rls_source, fixture)
    assert fixture_source is not None
    assert "monkeypatch" in {arg.arg for arg in fixture.args.args}
    assert "current_database()" in fixture_source
    assert "inet_server_port()" in fixture_source
    assert "server_version_num" in fixture_source
    assert (
        fixture_source.index("identity = await app.fetchrow")
        < fixture_source.index("_mark_preflighted_disposable_read_app(monkeypatch)")
        < fixture_source.index("yield app, ids")
    )

    marker = next(
        node
        for node in rls_tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_mark_preflighted_disposable_read_app"
    )
    marker_source = ast.get_source_segment(rls_source, marker)
    assert marker_source is not None
    assert "frfinance_ci_disposable_read_test" in marker_source
    assert "database._m41180_ci_disposable_read_exception(request)" in marker_source

    workflow_path = repo_root / ".github" / "workflows" / "validacao-atualizacao.yml"
    workflow_source = workflow_path.read_text(encoding="utf-8")

    def step_block(name: str) -> str:
        start = workflow_source.index(f"      - name: {name}")
        end = workflow_source.find("\n      - name:", start + 1)
        return workflow_source[start:] if end < 0 else workflow_source[start:end]

    for name in (
        "Testar isolamento com registros sintéticos",
        "M40360/M40370 — login original, Crédito Especial e dados RLS de duas caixinhas",
    ):
        block = step_block(name)
        assert "CI_M40360_DISPOSABLE: '1'" in block
        assert "PGOPTIONS: '-c frfinance.m40360_ci=DISPOSABLE_ONLY'" in block
        for flag in (
            "PIX_REAL",
            "PAGAMENTOS_REAIS",
            "ATIVACAO_REAL",
            "FR_FINANCE_PIX_REAL",
            "FR_FINANCE_REAL_PAYMENTS",
            "FR_FINANCE_REAL_USER_ACTIVATION",
        ):
            assert f"{flag}: 'OFF'" in block

    trigger_paths = workflow_source[
        workflow_source.index("    paths:") : workflow_source.index("  pull_request:")
    ]
    assert "'backend/tests/test_rls_isolation_ci.py'" in trigger_paths
    assert "'backend/tests/test_aistudio_roles_e2e_ci.py'" in trigger_paths


def test_three_role_e2e_harness_marks_only_its_preflighted_disposable_database():
    repo_root = Path(__file__).resolve().parents[2]
    roles_path = repo_root / "backend" / "tests" / "test_aistudio_roles_e2e_ci.py"
    roles_source = roles_path.read_text(encoding="utf-8")
    roles_tree = ast.parse(roles_source, filename=str(roles_path))
    test = next(
        node
        for node in roles_tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "test_local_onboarding_three_roles_and_auth"
    )
    test_source = ast.get_source_segment(roles_source, test)
    assert test_source is not None
    assert 'monkeypatch.setenv("ENVIRONMENT", "development")' in test_source
    assert "current_database()" in test_source
    assert "inet_server_port()" in test_source
    assert "server_version_num" in test_source
    assert (
        test_source.index("identity = db.execute")
        < test_source.index("frfinance_ci_disposable_read_test")
        < test_source.index("async with AsyncClient")
    )
    assert "database._m41180_ci_disposable_read_exception(request) is True" in test_source
