"""M41150/M41160 offline contract checks for the FastAPI/SQL capability boundary."""
from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.m41150_fastapi_rls_context import (
    InvalidSessionTicket,
    validate_signed_session_ticket,
)

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "backend/app/m41150_fastapi_rls_context.py"
ROUTER = ROOT / "backend/app/routers/ledger.py"
RUNNER = ROOT / "backend/tests/m41150_fastapi_rls_context_pg18_disposable.py"
WORKFLOW = ROOT / ".github/workflows/frfinance-m41150-fastapi-rls-context-pg18.yml"
DOC = ROOT / "docs/FR_FINANCE_M41150_FASTAPI_SQL_CONTEXT_NO_GO.md"
DOC_M41160 = ROOT / "docs/FR_FINANCE_M41160_LEDGER_READ_CAPABILITY_NO_GO.md"
DOC_M41170 = ROOT / "docs/FR_FINANCE_M41170_LEDGER_PROVIDER_ABSENT_FAIL_CLOSED_NO_GO.md"


def test_ticket_is_opaque_fixed_length_and_never_echoed():
    assert validate_signed_session_ticket("a" * 64) == "a" * 64
    for value in (None, "", "A" * 64, "g" * 64, "a" * 63, "a" * 65, 123):
        with pytest.raises(InvalidSessionTicket):
            validate_signed_session_ticket(value)


def test_capability_route_uses_transaction_local_context_and_read_only_transaction():
    source = MODULE.read_text(encoding="utf-8")
    for marker in (
        "require_verified_rls_session(session)",
        "require_nonproduction_financial_sql(os.environ)",
        '"issue_ticket"',
        '"bind_ticket"',
        "async with connection.transaction(readonly=True)",
        "install_session_capability(connection, capability)",
        "RESET ALL; DISCARD TEMP;",
        "connection.terminate()",
        "PROVIDER_STATE_ATTRIBUTE",
        "READ_SCOPE = \"READ_ENTRIES\"",
    ):
        assert marker in source
    for forbidden in (
        "set_config('app.current_user_id'",
        "set_config('app.current_role'",
        "set_config('app.current_tenant_id'",
        "raw_token",
        "DATABASE_URL",
        "PIX_REAL = \"ON\"",
        "PAGAMENTOS_REAIS = \"ON\"",
        "ATIVACAO_REAL = \"ON\"",
    ):
        assert forbidden not in source


def test_all_read_only_ledger_routes_use_optional_capability_dependency():
    source = ROUTER.read_text(encoding="utf-8")
    assert (
        "from ..m41150_fastapi_rls_context import "
        "get_ledger_readonly_db_connection"
    ) in source
    for function_name in (
        "get_ledger_integrity_preview",
        "list_ledger_account_directory",
        "list_ledger_accounts",
        "list_ledger_transactions",
        "list_ledger_account_entries",
        "list_ledger_account_entries_keyset",
    ):
        start = source.index(f"async def {function_name}(")
        end = source.find("\n\n@", start)
        route = source[start:] if end < 0 else source[start:end]
        assert "Depends(get_ledger_readonly_db_connection)" in route
        assert "Depends(get_rls_db_connection)" not in route
    assert "Depends(get_rls_db_connection)" not in source


def test_m41170_provider_absence_fails_closed_without_legacy_guc_fallback():
    source = MODULE.read_text(encoding="utf-8")
    assert "get_rls_db_connection" not in source
    branch = source.split("if provider is None:", 1)[1].split("\n\n    try:", 1)[0]
    assert "status_code=status.HTTP_503_SERVICE_UNAVAILABLE" in branch
    assert "Acesso ao livro-razão indisponível." in branch
    assert "yield" not in branch


def test_m41170_document_records_scope_and_keeps_no_go():
    doc = DOC_M41170.read_text(encoding="utf-8")
    for marker in (
        "M41170", "CP26-0061", "CP26-0062", "CTM-07", "CTM-08",
        "seis rotas GET de leitura do ledger",
        "M41170_PROVIDER_ABSENT=HTTP_503",
        "M41170_LEGACY_GUC_FALLBACK=REMOVED",
        "M41170_DATABASE_CONNECTIONS_WITHOUT_PROVIDER=NONE",
        "M40570", "M40730", "M40840", "M40930",
        "330 IDs", "2.310 etapas", "PENDING_INDEPENDENT_EVIDENCE",
        "ORIGINAL_DATABASE=NOT_ACCESSED", "MIGRATIONS=NONE",
        "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF", "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED",
    ):
        assert marker in doc
    assert "PRODUCTION=GO" not in doc


def test_m41160_document_preserves_independent_evidence_and_production_gates():
    doc = DOC_M41160.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "CTM-07", "CTM-08",
        "330 IDs", "2.310 etapas", "M40570", "M40730", "M40840",
        "M40930", "M41160_AUTHENTICATION=OVERRIDDEN_SYNTHETIC",
        "M41160_PROVIDER=CUSTODY_NOT_CONFIGURED",
        "ORIGINAL_DATABASE=NOT_ACCESSED", "MIGRATIONS=NONE",
        "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF", "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED", "NO-GO",
    ):
        assert marker in doc
    assert "PRODUCTION=GO" not in doc


def test_runner_preflights_exact_disposable_postgres_before_driver_imports():
    source = RUNNER.read_text(encoding="utf-8")
    main = source.split("def main()", 1)[1]
    assert main.index("dsn = require_disposable()") < main.index("asyncio.run(exercise(dsn))")
    exercise = source.split("async def exercise", 1)[1].split("\ndef main()", 1)[0]
    assert "import asyncpg" in exercise and "import psycopg" in exercise
    assert 'SHOW server_version_num' in exercise
    for marker in (
        "fr_m40700_disposable_ci",
        "55439",
        "CI_M41150_DISPOSABLE",
        "CI_M41150_DATABASE_URL",
        "ORIGINAL_DATABASE=NOT_ACCESSED",
        "MIGRATIONS=NONE",
        "PIX_REAL=OFF",
        "PAGAMENTOS_REAIS=OFF",
        "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED",
        "M41150_FASTAPI_LEDGER_DIRECTORY=PASS",
        "M41150_FORGED_LEGACY_GUC_DENIED=PASS",
        "M41160_FORGED_LEGACY_GUC_DENIED=PASS",
        "M41150_TICKET_REPLAY_DENIED=PASS",
        "M41150_REVOKED_CAPABILITY_DENIED=PASS",
        "M41160_FASTAPI_LEDGER_READ_ROUTES=6_OF_6_PASS",
        "M41160_TENANT_ROLE_NEGATIVE=PASS",
        "M41160_CONCURRENT_READS=PASS",
        "M41160_RLS_TENANT_ISOLATION=PASS",
        "M41170_PROVIDER_ABSENT_FAIL_CLOSED=PASS",
        "M41170_DATABASE_POOL_CALLS_WITHOUT_PROVIDER=0",
        "M41170_STATUS=PASS_FAIL_CLOSED_DISPOSABLE_ONLY",
        "M41170_LEGACY_GUC_FALLBACK=REMOVED",
        "M41170_DATABASE_CONNECTIONS_WITHOUT_PROVIDER=NONE",
    ):
        assert marker in source
    for forbidden in ("127.0.0.1:5433", "backend/migrations/", "pg_ctl",
                      "PIX_REAL=ON", "PAGAMENTOS_REAIS=ON", "ATIVACAO_REAL=ON"):
        assert forbidden not in source


def test_ci_workflow_uses_pg18_service_and_only_fixture_database():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    for marker in (
        "postgres:18",
        "55439:5432",
        "fr_m40700_disposable_ci",
        "CI_M41150_DISPOSABLE: '1'",
        "CI_M41160_DISPOSABLE: '1'",
        "CI_M41170_DISPOSABLE: '1'",
        "CI_M41150_DATABASE_URL:",
        "docs/FR_FINANCE_M41170_LEDGER_PROVIDER_ABSENT_FAIL_CLOSED_NO_GO.md",
        "CI_M41160_DATABASE_URL:",
        "PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "backend/tests/m41050_sql_sealed_context_pg18_disposable.py",
        "backend/tests/m41150_fastapi_rls_context_pg18_disposable.py",
        "backend/requirements.txt",
        "contents: read",
    ):
        assert marker in workflow
    for forbidden in ("127.0.0.1:5433", "backend/migrations/", "pg_ctl", "ssh "):
        assert forbidden not in workflow


def test_document_keeps_external_evidence_and_production_gates_open():
    doc = DOC.read_text(encoding="utf-8")
    for marker in (
        "CP26-0061", "CP26-0062", "CTM-07", "CTM-08",
        "PENDING_INDEPENDENT_EVIDENCE", "Issue #5",
        "M41150_AUTHENTICATION=OVERRIDDEN_SYNTHETIC",
        "M41150_PROVIDER=CUSTODY_NOT_CONFIGURED",
        "ORIGINAL_DATABASE=NOT_ACCESSED", "MIGRATIONS=NONE",
        "PIX_REAL=OFF", "PAGAMENTOS_REAIS=OFF", "ATIVACAO_REAL=OFF",
        "PRODUCTION=BLOCKED",
    ):
        assert marker in doc
    assert "PRODUCTION=GO" not in doc


@pytest.mark.asyncio
async def test_m41190_readback_compares_all_claims_and_rejects_ambiguous_results():
    from uuid import uuid4
    from fastapi import HTTPException
    from backend.app.m41150_fastapi_rls_context import _require_bound_read_claims

    user, tenant, session_id, request_nonce = uuid4(), uuid4(), uuid4(), uuid4()
    expected = (user, "TENANT_ADMIN", tenant, "READ_ENTRIES", session_id, request_nonce)
    valid = dict(zip(("user_id", "role_name", "tenant_id", "scope_name", "session_id", "request_nonce"), expected))

    class Connection:
        def __init__(self, rows):
            self.rows = rows
        async def fetch(self, sql):
            assert sql == (
                "SELECT user_id, role_name, tenant_id, scope_name, session_id, request_nonce "
                "FROM m41050.current_claims_v4()"
            )
            if isinstance(self.rows, Exception):
                raise self.rows
            return self.rows

    await _require_bound_read_claims(Connection([valid]), expected)
    for rows in ([], [valid, valid], [{**valid, "user_id": uuid4()}],
                 [{**valid, "tenant_id": uuid4()}],
                 [{**valid, "role_name": "TENANT_MEMBER"}],
                 [{**valid, "scope_name": "WRITE_ENTRIES"}],
                 [{**valid, "session_id": uuid4()}],
                 [{**valid, "session_id": None}],
                 [{**valid, "request_nonce": uuid4()}],
                 [{**valid, "request_nonce": None}]):
        with pytest.raises(HTTPException) as exc:
            await _require_bound_read_claims(Connection(rows), expected)
        assert exc.value.status_code == 401
    for rows in (None, [{}], [{k: v for k, v in valid.items() if k != "session_id"}],
                 [{k: v for k, v in valid.items() if k != "request_nonce"}],
                 RuntimeError("sensitive fixture error")):
        with pytest.raises(HTTPException) as exc:
            await _require_bound_read_claims(Connection(rows), expected)
        assert exc.value.status_code == 503
        assert "sensitive fixture error" not in str(exc.value.detail)


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["route", "cancel_route", "reset", "cancel_reset"])
@pytest.mark.parametrize("target_bound", [False, True])
async def test_m41190_transaction_exit_and_pool_cleanup(monkeypatch, failure, target_bound):
    import hashlib
    import asyncio
    from contextlib import asynccontextmanager
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from uuid import UUID, uuid4
    from fastapi import HTTPException
    from backend.app import m41150_fastapi_rls_context as gateway

    now = datetime.now(timezone.utc)
    user, tenant = uuid4(), uuid4()
    session = SimpleNamespace(
        user_id=str(user), role="TENANT_ADMIN", tenant_id=str(tenant),
        is_master=False, verified_session_id=str(uuid4()),
        verified_session_at=now, verified_session_expires_at=now + timedelta(minutes=1),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    events = []
    issued_nonces = []

    class Connection:
        @asynccontextmanager
        async def transaction(self, *, readonly):
            assert readonly is True
            events.append("begin")
            try:
                yield
            except BaseException:
                events.append("rollback")
                raise
            else:
                events.append("commit")

        async def fetchrow(self, sql):
            assert "pg_catalog.pg_locks" in sql
            events.append("identity")
            return {"backend_pid": 123, "virtual_xid": "5/42",
                    "transaction_started_at": now}

        async def fetchval(self, sql, ticket, tenant_id):
            assert sql == "SELECT m41050.read_target_challenge($1,$2)"
            assert tenant_id == tenant
            if ticket != "a" * 64:
                assert target_bound
                events.append(("pre_challenge", ticket))
                return "d" * 64
            events.append("challenge")
            return "c" * 64

        async def fetch(self, sql):
            events.append("claims")
            return [{"user_id": user, "role_name": "TENANT_ADMIN",
                     "tenant_id": tenant, "scope_name": "READ_ENTRIES",
                     "session_id": UUID(session.verified_session_id),
                     "request_nonce": issued_nonces[-1]}]

        async def execute(self, sql):
            assert sql == "RESET ALL; DISCARD TEMP;"
            events.append("reset")
            if failure == "reset":
                raise RuntimeError("sensitive fixture error")
            if failure == "cancel_reset":
                raise asyncio.CancelledError()

        def terminate(self):
            events.append("terminate")

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            events.append("acquire")
            try:
                yield Connection()
            finally:
                events.append("release")

    async def get_pool():
        return Pool()

    async def install(connection, capability):
        assert capability == "b" * 64
        events.append("install")

    class Provider:
        capability_protocol = gateway.TARGET_BOUND_PROTOCOL if target_bound else None

        async def issue_target_ticket(self, session, *, scope, request_nonce, tenant_id,
                                      backend_pid, virtual_xid, transaction_started_at, target_challenge):
            assert target_bound and scope == "READ_ENTRIES"
            assert tenant_id == tenant and target_challenge == "d" * 64
            assert (backend_pid, virtual_xid, transaction_started_at) == (123, "5/42", now)
            expected_seed = hashlib.sha256(
                ("FRF-M41630-SEED|v1|" + str(request_nonce)).encode("ascii")
            ).hexdigest()
            assert events[-1] == ("pre_challenge", expected_seed)
            issued_nonces.append(request_nonce)
            events[-1] = "pre_challenge"
            events.append("target_issue")
            return "a" * 64

        async def issue_ticket(self, session, *, scope, request_nonce):
            assert not target_bound
            assert scope == "READ_ENTRIES"
            assert isinstance(request_nonce, UUID) and request_nonce.version == 4
            issued_nonces.append(request_nonce)
            return "a" * 64
        async def bind_ticket(self, ticket, *, tenant_id, backend_pid,
                              virtual_xid, transaction_started_at, target_challenge):
            assert target_challenge == "c" * 64
            assert tenant_id == tenant
            assert (backend_pid, virtual_xid, transaction_started_at) == (123, "5/42", now)
            events.append("bind")
            return "b" * 64

    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in ("PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL"):
        monkeypatch.setenv(key, "OFF")
    monkeypatch.setattr(gateway, "get_db_pool", get_pool)
    monkeypatch.setattr(gateway, "install_session_capability", install)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(
            frfinance_session_capability_provider=Provider())),
        path_params={"tenant_id": str(tenant)},
    )
    dependency = gateway.get_ledger_readonly_db_connection(request, session)
    await anext(dependency)
    assert events == (["acquire", "begin", "identity"]
                      + (["pre_challenge", "target_issue"] if target_bound else [])
                      + ["challenge", "bind", "install", "claims"])

    if failure == "route":
        with pytest.raises(ValueError, match="route failure"):
            await dependency.athrow(ValueError("route failure"))
        assert events[-3:] == ["rollback", "reset", "release"]
    elif failure == "cancel_route":
        with pytest.raises(asyncio.CancelledError):
            await dependency.athrow(asyncio.CancelledError())
        assert events[-3:] == ["rollback", "reset", "release"]
    elif failure == "reset":
        with pytest.raises(HTTPException) as exc:
            await anext(dependency)
        assert exc.value.status_code == 503
        assert "sensitive fixture error" not in str(exc.value.detail)
        assert events[-4:] == ["commit", "reset", "terminate", "release"]
    else:
        with pytest.raises(asyncio.CancelledError):
            await anext(dependency)
        assert events[-4:] == ["commit", "reset", "terminate", "release"]


@pytest.mark.asyncio
@pytest.mark.parametrize("row", [None, {}, {"backend_pid": 0, "virtual_xid": "1/2", "transaction_started_at": None}, {"backend_pid": 1, "virtual_xid": "forged", "transaction_started_at": None}])
async def test_m41220_invalid_transaction_identity_fails_closed(row):
    from fastapi import HTTPException
    from backend.app.m41150_fastapi_rls_context import _read_transaction_identity
    class Connection:
        async def fetchrow(self, sql):
            return row
    with pytest.raises(HTTPException) as exc:
        await _read_transaction_identity(Connection())
    assert exc.value.status_code == 503


def test_m41230_signed_transaction_target_contract():
    fixture = (ROOT / "backend/tests/m41050_sql_sealed_context_pg18_disposable.py").read_text(encoding="utf-8")
    binding = fixture.split("CREATE FUNCTION m41050.bind_read_transaction(", 1)[1].split("CREATE FUNCTION m41050.current_claims_v4()", 1)[0]
    assert "FRF-M41270|v1|" in binding
    assert binding.index("p_proof<>v_expected") < binding.index("v_cap:=m41050.bind_ticket")
    assert "EXTRACT(EPOCH FROM p_started)*1000000" in binding
    assert "M41230_TICKET_ONLY_AND_TARGET_SUBSTITUTION_DENIED=PASS" in RUNNER.read_text(encoding="utf-8")


def test_m41240_target_key_and_worker_contract():
    source = (ROOT / "backend/tests/m41050_sql_sealed_context_pg18_disposable.py").read_text(encoding="utf-8")
    binding = source.split("CREATE FUNCTION m41050.bind_read_transaction(", 1)[1].split("CREATE FUNCTION m41050.current_claims_v4()", 1)[0]
    assert "FROM m41050.target_verifier_secret" in binding
    assert "FROM m40700.verifier_secret" not in binding
    assert "REVOKE ALL ON m41050.target_verifier_secret FROM PUBLIC,m40680_auth,m40650_app" in source
    runner = RUNNER.read_text(encoding="utf-8")
    for marker in ("M41240_DISTINCT_TARGET_KEY_AND_SQL_ACL=PASS",
                   "M41240_ISSUER_KEY_CANNOT_BIND_TARGET=PASS",
                   "M41240_MISSING_TARGET_KEY_FAILS_CLOSED=PASS",
                   "M41240_SIGNER_UNAVAILABLE_HTTP503_POOL_CLEAN=PASS"):
        assert marker in runner


def test_m41240_worker_protocol_and_fail_closed(monkeypatch):
    import hmac
    import importlib.util
    import sys
    from datetime import datetime, timezone
    from uuid import uuid4
    from hashlib import sha256

    if sys.platform != "linux":
        pytest.skip("Linux CI process boundary")
    path = ROOT / "backend/tests/m41240_target_signer_disposable.py"
    spec = importlib.util.spec_from_file_location("m41240_worker_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.delenv("CI_M41150_DISPOSABLE", raising=False)
    with pytest.raises(RuntimeError):
        module.TargetSigner(challenge_key=b"c" * 32)
    for k, v in module.GATE.items():
        monkeypatch.setenv(k, v)
    signer = module.TargetSigner(challenge_key=b"c" * 32)
    try:
        key = signer.take_bootstrap_key()
        with pytest.raises(RuntimeError):
            signer.take_bootstrap_key()
        tenant = uuid4()
        started = datetime(2026, 1, 1, tzinfo=timezone.utc)
        ticket = "a" * 64
        base = f"{sha256(ticket.encode()).hexdigest()}|{tenant}|123|1/2|1767225600000000"
        challenge = hmac.new(b"c" * 32, ("FRF-M41260|v1|" + base).encode(), sha256).hexdigest()
        message = f"FRF-M41270|v1|{base}|{challenge}"
        assert signer.sign(ticket, tenant, 123, "1/2", started, challenge=challenge) == hmac.new(
            key, message.encode(), sha256
        ).hexdigest()
        with pytest.raises(ValueError):
            signer.sign(ticket, tenant, 0, "1/2", started, challenge=challenge)
    finally:
        signer.close()
    with pytest.raises(RuntimeError):
        signer.sign(ticket, tenant, 123, "1/2", started, challenge="c" * 64)


def test_m41250_same_uid_inherited_descriptor_denied(monkeypatch):
    import importlib.util
    import json
    import hmac
    import os
    import subprocess
    import sys
    from datetime import datetime, timezone
    from hashlib import sha256
    from uuid import uuid4

    if sys.platform != "linux":
        pytest.skip("Linux per-message credentials")
    path = ROOT / "backend/tests/m41240_target_signer_disposable.py"
    spec = importlib.util.spec_from_file_location("m41250_worker_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for k, v in module.GATE.items():
        monkeypatch.setenv(k, v)
    signer = module.TargetSigner(challenge_key=b"c" * 32)
    try:
        signer.take_bootstrap_key()
        tenant, ticket = uuid4(), "b" * 64
        started = datetime(2026, 1, 1, tzinfo=timezone.utc)
        base = f"{sha256(ticket.encode()).hexdigest()}|{tenant}|123|1/2|1767225600000000"
        challenge = hmac.new(b"c" * 32, ("FRF-M41260|v1|" + base).encode(), sha256).hexdigest()
        packet = {"digest": sha256(ticket.encode()).hexdigest(), "tenant": str(tenant),
                  "pid": 123, "vxid": "1/2", "micros": 1767225600000000, "challenge": challenge}
        fd = signer._channel.fileno()
        # Deliberately pass the real descriptor to an unrelated same-UID child.
        # The kernel identifies the actual writer, not the owner of the socket.
        script = (
            "import os,socket,sys;"
            "assert os.getuid()==int(sys.argv[3]);"
            "s=socket.socket(fileno=int(sys.argv[1]));s.settimeout(4);"
            "s.sendall(sys.argv[2].encode('ascii'));"
            "assert s.recv(64)==b'DENIED'"
        )
        subprocess.run(
            [sys.executable, "-B", "-c", script, str(fd), json.dumps(packet), str(os.getuid())],
            pass_fds=(fd,), env={"PYTHONDONTWRITEBYTECODE": "1"},
            timeout=8, check=True,
        )
        expected = signer.sign(ticket, tenant, 123, "1/2", started, challenge=challenge)
        assert len(expected) == 64
        # A valid parent still works after malformed and oversized packets.
        for invalid in (b"{}", b"x" * (module.MAX_FRAME + 1)):
            signer._channel.sendall(invalid)
            response, cred = module.receive_frame(signer._channel, 64)
            assert response == b"DENIED"
            assert cred == module.process_credentials(signer._proc.pid)
        assert signer.sign(ticket, tenant, 123, "1/2", started, challenge=challenge) == expected
        print("M41250_SAME_UID_INHERITED_DESCRIPTOR_DENIED=PASS")
    finally:
        signer.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [None, "", "g"*64, "A"*64, 123])
async def test_m41260_invalid_sql_target_challenge_fails_closed(value):
    from fastapi import HTTPException
    from uuid import uuid4
    from backend.app.m41150_fastapi_rls_context import _read_target_challenge

    class Connection:
        async def fetchval(self, sql, ticket, tenant):
            return value

    with pytest.raises(HTTPException) as exc:
        await _read_target_challenge(Connection(), "a"*64, uuid4())
    assert exc.value.status_code == 503


def test_m41260_challenge_checked_before_ticket_consumption():
    source = (ROOT / "backend/tests/m41050_sql_sealed_context_pg18_disposable.py").read_text(encoding="utf-8")
    binding = source.split("CREATE FUNCTION m41050.bind_read_transaction(", 1)[1].split("CREATE FUNCTION m41050.current_claims_v4()", 1)[0]
    assert "FROM m41050.target_challenge_secret" in binding
    assert binding.index("p_challenge<>v_challenge_expected") < binding.index("v_cap:=m41050.bind_ticket")
    assert "FRF-M41260|v1|" in source
    assert "M41260_SQL_CHALLENGE_TARGET_SUBSTITUTION_DENIED=PASS" in RUNNER.read_text(encoding="utf-8")


def test_m41270_challenge_is_signed_and_legacy_domain_rejected(monkeypatch):
    import importlib.util
    import hmac
    import sys
    from datetime import datetime, timezone
    from hashlib import sha256
    from uuid import uuid4

    if sys.platform != "linux":
        pytest.skip("Linux CI process boundary")
    path = ROOT / "backend/tests/m41240_target_signer_disposable.py"
    spec = importlib.util.spec_from_file_location("m41270_worker_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for k, v in module.GATE.items():
        monkeypatch.setenv(k, v)
    signer = module.TargetSigner(challenge_key=b"c" * 32)
    try:
        key = signer.take_bootstrap_key()
        tenant, ticket = uuid4(), "a" * 64
        started = datetime(2026, 1, 1, tzinfo=timezone.utc)
        base = f"{sha256(ticket.encode()).hexdigest()}|{tenant}|123|1/2|1767225600000000"
        challenge = hmac.new(b"c" * 32, ("FRF-M41260|v1|" + base).encode(), sha256).hexdigest()
        a = signer.sign(ticket, tenant, 123, "1/2", started, challenge=challenge)
        wrong = "0" * 64 if challenge != "0" * 64 else "1" * 64
        with pytest.raises(module.TargetProofDenied):
            signer.sign(ticket, tenant, 123, "1/2", started, challenge=wrong)
        assert a == hmac.new(key, ("FRF-M41270|v1|" + base + "|" + challenge).encode(), sha256).hexdigest()
        assert a != hmac.new(key, ("FRF-M41230|v1|" + base).encode(), sha256).hexdigest()
        for invalid in (None, "", "A" * 64, "g" * 64, 123):
            with pytest.raises(ValueError):
                signer.sign(ticket, tenant, 123, "1/2", started, challenge=invalid)
        assert signer.sign(ticket, tenant, 123, "1/2", started, challenge=challenge) == a
    finally:
        signer.close()
    source = (ROOT / "backend/tests/m41050_sql_sealed_context_pg18_disposable.py").read_text(encoding="utf-8")
    binding = source.split("CREATE FUNCTION m41050.bind_read_transaction(", 1)[1].split("CREATE FUNCTION m41050.current_claims_v4()", 1)[0]
    assert "'FRF-M41270|v1|'||v_payload||'|'||p_challenge" in binding
    assert "FRF-M41230|v1|" not in binding
    assert "M41270_LEGACY_AND_MIXED_PROOFS_DENIED=PASS" in RUNNER.read_text(encoding="utf-8")



def test_m41280_worker_target_pin_concurrent_and_bounded(monkeypatch):
    import importlib.util
    import hmac
    import sys
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone
    from hashlib import sha256
    from uuid import uuid4

    if sys.platform != "linux":
        pytest.skip("Linux CI process boundary")
    path = ROOT / "backend/tests/m41240_target_signer_disposable.py"
    spec = importlib.util.spec_from_file_location("m41280_worker_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for k, v in module.GATE.items():
        monkeypatch.setenv(k, v)
    key = b"q" * 32
    tenant, ticket = uuid4(), "a" * 64
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def packet(ticket, tenant, pid):
        digest = sha256(ticket.encode()).hexdigest()
        base = f"{digest}|{tenant}|{pid}|1/2|1767225600000000"
        challenge = hmac.new(key, ("FRF-M41260|v1|" + base).encode(), sha256).hexdigest()
        return dict(digest=digest, tenant=str(tenant), pid=pid, vxid="1/2",
                    micros=1767225600000000, challenge=challenge)

    policy = module.TargetPolicy(key, limit=1)
    first = packet(ticket, tenant, 123)
    bad = dict(first, challenge="0" * 64)
    with pytest.raises(module.TargetProofDenied):
        policy.authorize(bad)
    expected = policy.authorize(first)
    assert policy.authorize(first) == expected
    for denied in (packet(ticket, tenant, 124), packet(ticket, uuid4(), 123),
                   packet("b" * 64, tenant, 123)):
        with pytest.raises(module.TargetProofDenied):
            policy.authorize(denied)
    assert policy.authorize(first) == expected
    signer = module.TargetSigner(challenge_key=key)
    try:
        signer.take_bootstrap_key()
        def attempt(pid):
            p = packet(ticket, tenant, pid)
            try:
                return pid, signer.sign(ticket, tenant, pid, "1/2", started, challenge=p["challenge"])
            except module.TargetProofDenied:
                return pid, None
        with ThreadPoolExecutor(max_workers=2) as executor:
            result = list(executor.map(attempt, (123, 124)))
        approved = [(pid, proof) for pid, proof in result if proof is not None]
        assert len(approved) == 1
        pid, proof = approved[0]
        assert attempt(pid) == (pid, proof)
        assert attempt(247 - pid) == (247 - pid, None)
        assert signer.sign("b" * 64, tenant, 123, "1/2", started,
                           challenge=packet("b" * 64, tenant, 123)["challenge"])
    finally:
        signer.close()


def test_m41280_integrated_worker_regression_contract():
    runner = RUNNER.read_text(encoding="utf-8")
    assert "M41280_WORKER_AUTHENTICATES_SQL_CHALLENGE=PASS" in runner
    assert "M41280_SECOND_AUTHENTIC_TARGET_DENIED=PASS" in runner
    assert "other_challenge = await gateway._read_target_challenge(second, ticket, tenant_a)" in runner



def test_m41290_reservation_acl_and_consumption_order():
    source = (ROOT / "backend/tests/m41050_sql_sealed_context_pg18_disposable.py").read_text(encoding="utf-8")
    reserve = source.split("CREATE FUNCTION m40700.reserve_read_target(", 1)[1].split(
        "CREATE FUNCTION m41050.bind_read_transaction(", 1)[0]
    bind = source.split("CREATE FUNCTION m41050.bind_read_transaction(", 1)[1].split(
        "CREATE FUNCTION m41050.current_claims_v4()", 1)[0]
    assert "session_user <> 'm40680_auth_login'" in reserve
    assert "t.used_at IS NULL" in reserve
    assert "s.context_generation=c.context_generation" in reserve
    assert "FOR UPDATE OF t" in reserve
    assert reserve.index("p_challenge<>v_expected") < reserve.index("INSERT INTO m41050.read_target_reservations")
    assert "ON CONFLICT(ticket_digest) DO NOTHING" in reserve
    assert "GRANT EXECUTE ON FUNCTION "+'"'+"+reservation_sig+"+'"'+" TO m40680_auth" in reserve
    assert "REVOKE ALL ON m41050.read_target_reservations FROM PUBLIC,m40680_auth,m40650_app" in source
    assert bind.index("FROM m41050.read_target_reservations") < bind.index("v_cap:=m41050.bind_ticket")
    runner = RUNNER.read_text(encoding="utf-8")
    assert runner.index("if not reserve_read(ticket") < runner.index("proof = signer.sign(ticket")
    for marker in ("M41290_RESERVATION_ACL=PASS", "M41290_UNRESERVED_PROOF_DENIED=PASS",
                   "M41290_ALTERNATE_VALID_PROOF_DENIED=PASS",
                   "M41290_CONCURRENT_RESERVATIONS_ONE_WINNER=PASS"):
        assert marker in runner


def test_m41610_dual_identity_fixture_retains_legacy_checks_and_no_go():
    source=(RUNNER.parent/"m41610_identity_authorization_disposable.py").read_text(encoding="utf-8")
    for marker in (
        "CREATE FUNCTION m40700.issue_bound_v3", "m40700.identity_authorization_secret",
        "session_user<>'m40680_auth_login'", "FRF-M41610|v1|",
        "s.id=p_session AND s.token_digest=p_digest",
        "s.context_generation=p_generation AND s.revoked_at IS NULL",
        "RETURN m40700.issue_bound_v2", "REVOKE EXECUTE ON FUNCTION "+'"+V2',
        "M41610_DUAL_KEY_ACL_LEGACY_ISSUER_DENIED=PASS",
        "M41610_DUAL_PROOF_SCOPE_EXPIRY_REVOCATION_REPLAY=PASS",
        "M41610_DUAL_PROOF_FASTAPI_SIX_READS_AND_KEY_LOSS=PASS",
    ):
        assert marker in source
    assert "exercise_dual_identity" in RUNNER.read_text(encoding="utf-8")
    assert "issue_bound_v3" not in MODULE.read_text(encoding="utf-8")


def test_m41620_commitment_fixture_preserves_protected_sql_boundary():
    source=(RUNNER.parent/"m41620_identity_commitment_disposable.py").read_text(encoding="utf-8")
    for marker in ("CREATE FUNCTION m40700.issue_bound_v4", "FRF-M41620|v1|",
                   "secrets.token_hex(32)", "pending.pop(nonce)", "SOCK_SEQPACKET",
                   "process_credentials(parent_pid)", "m40700.identity_commitments",
                   "consumed_at IS NULL FOR UPDATE", "RETURN v_ticket",
                   "M41620_NO_SHARED_SECOND_KEY_LEGACY_AND_ACL=PASS",
                   "M41620_BOUND_SINGLE_RELEASE_CONCURRENT_SQL_CONSUMPTION=PASS",
                   "M41620_COMMITMENT_EXPIRY_AND_SIX_READS=PASS"):
        assert marker in source
    assert "M41620_AUTHORITY_LOSS_NO_NEW_COMMITMENT=PASS" in RUNNER.read_text(encoding="utf-8")
    assert "issue_bound_v4" not in MODULE.read_text(encoding="utf-8")


def test_m41630_disposable_target_commitment_has_atomic_reservation_boundary():
    """Source contract, not a substitute for the adversarial PG18 execution."""
    source = RUNNER.read_text(encoding="utf-8")
    compile(source, str(RUNNER), "exec")
    assert source.count("def main() -> int:") == 1
    section = source.split("async def exercise_m41630_target_commitment(", 1)[1].split("\ndef main()", 1)[0]
    definition = section.split("CREATE FUNCTION m40700.issue_bound_v5(", 1)[1]
    header, sql, remainder = definition.split('$body$', 2)
    assert "LANGUAGE plpgsql SECURITY DEFINER" in header
    assert "SET search_path=pg_catalog,pg_temp" in header
    assert remainder.lstrip().startswith('""")')
    for marker in (
        "FRF-M41630-SEED|v1|", "FRF-M41630|v1|", "FRF-M41620|v1|",
        "p_digest !~ '^[0-9a-f]{64}$'",
        "p_token !~ '^[0-9a-f]{64}$'",
        "p_vxid !~ '^[0-9]+/[0-9]+$'",
        "p_challenge !~ '^[0-9a-f]{64}$'",
        "session_user <> 'm40680_auth_login'",
        "consumed_at IS NULL FOR UPDATE", "s.revoked_at IS NULL",
        "FOR SHARE OF s", "m40700.issue_bound_v2(",
        "m40700.reserve_read_target(", "M41630_TARGET_RESERVATION_FAILED",
    ):
        assert marker in sql
    assert sql.index("consumed_at IS NULL FOR UPDATE") < sql.index("m40700.issue_bound_v2(")
    assert sql.index("m40700.issue_bound_v2(") < sql.index("m40700.reserve_read_target(")
    assert sql.index("m40700.reserve_read_target(") < sql.index("SET consumed_at=")
    assert sql.index("SET consumed_at=") < sql.index("RETURN v_ticket;")
    for marker in (
        "M41630_DISPOSABLE_ONLY", "owner.info.port != PORT",
        'REVOKE EXECUTE ON FUNCTION " + V4',
        'REVOKE EXECUTE ON FUNCTION " + reservation',
        "submit(p, token, wrong, wrong_challenge) is None",
        "rollback=True", "sum(t is not None for t in results) == 1",
        "bind_read(ticket,tenant_a,*wrong,challenge=bad,proof=bad_proof) is None",
        "await gateway.install_session_capability(other,cap)",
        "M41630_TRANSACTION_END_REPLAY_DENIED=PASS",
        "M41630_REAL_PROVIDER=NOT_INTEGRATED", "M41630_PRODUCTION=BLOCKED",
    ):
        assert marker in section
    assert "await exercise_m41630_target_commitment(" in source
    assert "backend/tests/m41150_fastapi_rls_context_pg18_disposable.py" in WORKFLOW.read_text(encoding="utf-8")

def test_m41636_disposable_lifecycle_checks_cover_each_v5_boundary():
    source = RUNNER.read_text(encoding="utf-8")
    compile(source, str(RUNNER), "exec")
    section = source.split("# M41636: prove lifecycle invalidation", 1)[1].split(
        "    finally:\n        new_signer.close()", 1
    )[0]
    for marker in (
        "async def fresh_commitment(connection):",
        "def assert_unissued(request):",
        "context_generation=context_generation+1",
        "assert submit(*stale) is None",
        "assert_unissued(stale[0])",
        "unbound_ticket = submit(*issued)",
        "active_cap = bind_read(active_ticket",
        "await gateway.install_session_capability(dest,active_cap)",
        "SET revoked_at=pg_catalog.clock_timestamp()",
        "assert submit(*pending) is None",
        "assert_unissued(pending[0])",
        "assert bind_read(unbound_ticket",
        "SELECT revoked_at IS NOT NULL FROM m41050.session_caps",
        "assert not dest.is_in_transaction()",
        "M41636_STALE_GENERATION_NO_ISSUANCE=PASS_DISPOSABLE_ONLY",
        "M41636_REVOKED_PENDING_RESERVED_AND_ACTIVE_DENIED=PASS_DISPOSABLE_ONLY",
        "M41636_POST_REVOCATION_POOL_CLEAN=PASS_DISPOSABLE_ONLY",
    ):
        assert marker in section
    assert section.index("active_cap = bind_read(active_ticket") < section.index(
        "SET revoked_at=pg_catalog.clock_timestamp()"
    ) < section.index("assert bind_read(unbound_ticket")
    assert "SET revoked_at=NULL" not in section

@pytest.mark.asyncio
@pytest.mark.parametrize("mode,expected", [
    ("unsupported", 503), ("missing", 503), ("refused", 401),
    ("malformed", 401), ("issuer_error", 503), ("challenge_error", 503),
])
async def test_m41639_target_protocol_never_downgrades(monkeypatch, mode, expected):
    from contextlib import asynccontextmanager
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from uuid import uuid4
    from fastapi import HTTPException
    from backend.app import m41150_fastapi_rls_context as gateway

    now = datetime.now(timezone.utc)
    tenant = uuid4()
    session = SimpleNamespace(
        user_id=str(uuid4()), role="TENANT_ADMIN", tenant_id=str(tenant),
        is_master=False, verified_session_id=str(uuid4()),
        verified_session_at=now, verified_session_expires_at=now + timedelta(minutes=1),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    events = []

    class Connection:
        @asynccontextmanager
        async def transaction(self, *, readonly):
            assert readonly
            events.append("begin")
            try:
                yield
            except BaseException:
                events.append("rollback")
                raise

        async def fetchrow(self, sql):
            return dict(backend_pid=123, virtual_xid="1/2", transaction_started_at=now)

        async def fetchval(self, sql, seed, tenant_id):
            events.append("challenge")
            return None if mode == "challenge_error" else "c" * 64

        async def execute(self, sql):
            assert sql == "RESET ALL; DISCARD TEMP;"
            events.append("reset")

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            events.append("acquire")
            try:
                yield Connection()
            finally:
                events.append("release")

    async def pool():
        return Pool()

    class Provider:
        capability_protocol = ("unsupported-version" if mode == "unsupported"
                               else gateway.TARGET_BOUND_PROTOCOL)

        async def issue_ticket(self, *args, **kwargs):
            events.append("legacy")
            return "a" * 64

        async def issue_target_ticket(self, *args, **kwargs):
            events.append("target")
            if mode == "issuer_error":
                raise RuntimeError("private issuer failure")
            return "invalid" if mode == "malformed" else None

        async def bind_ticket(self, *args, **kwargs):
            events.append("bind")
            return "b" * 64

    provider = Provider()
    if mode == "missing":
        provider.issue_target_ticket = None
    monkeypatch.setenv("ENVIRONMENT", "development")
    for key in ("PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL"):
        monkeypatch.setenv(key, "OFF")
    monkeypatch.setattr(gateway, "get_db_pool", pool)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(frfinance_session_capability_provider=provider)),
        path_params={"tenant_id": str(tenant)},
    )
    with pytest.raises(HTTPException) as exc:
        await anext(gateway.get_ledger_readonly_db_connection(request, session))
    assert exc.value.status_code == expected
    assert "private issuer failure" not in str(exc.value.detail)
    assert "legacy" not in events and "bind" not in events
    if mode in ("unsupported", "missing"):
        assert events == []
    else:
        assert events == (["acquire", "begin", "challenge"]
                          + ([] if mode == "challenge_error" else ["target"])
                          + ["rollback", "reset", "release"])

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "live_flag", "unset_flag"),
    [
        ("production", None, None),
        ("staging", "PIX_REAL", None),
        ("development", "PAGAMENTOS_REAIS", None),
        ("test", "ATIVACAO_REAL", None),
        ("unrecognized", None, None),
        (None, None, None),
        ("staging", None, "PIX_REAL"),
    ],
)
async def test_m41644_m40840_blocks_injected_target_provider_before_database_pool(
    monkeypatch, mode, live_flag, unset_flag
):
    """A configured target-first provider cannot bypass the production SQL NO-GO."""
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from uuid import uuid4

    from fastapi import HTTPException
    from backend.app import m41150_fastapi_rls_context as gateway

    now = datetime.now(timezone.utc)
    tenant = uuid4()
    session = SimpleNamespace(
        user_id=str(uuid4()),
        role="TENANT_ADMIN",
        tenant_id=str(tenant),
        is_master=False,
        verified_session_id=str(uuid4()),
        verified_session_at=now,
        verified_session_expires_at=now + timedelta(minutes=1),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    calls = {"provider": 0, "pool": 0}

    class InjectedTargetProvider:
        capability_protocol = gateway.TARGET_BOUND_PROTOCOL

        async def issue_target_ticket(self, *args, **kwargs):
            calls["provider"] += 1
            return "a" * 64

        async def bind_ticket(self, *args, **kwargs):
            calls["provider"] += 1
            return "b" * 64

    async def forbidden_pool():
        calls["pool"] += 1
        raise AssertionError("M41644_DATABASE_POOL_MUST_NOT_OPEN")

    monkeypatch.setattr(gateway, "get_db_pool", forbidden_pool)
    if mode is None:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
    else:
        monkeypatch.setenv("ENVIRONMENT", mode)
    for flag in ("PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL"):
        if flag == live_flag:
            monkeypatch.setenv(flag, "ON")
        elif flag == unset_flag:
            monkeypatch.delenv(flag, raising=False)
        else:
            monkeypatch.setenv(flag, "OFF")

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                frfinance_session_capability_provider=InjectedTargetProvider()
            )
        ),
        path_params={"tenant_id": str(tenant)},
    )
    dependency = gateway.get_ledger_readonly_db_connection(request, session)

    with pytest.raises(HTTPException) as exc:
        await anext(dependency)

    assert exc.value.status_code == 503
    assert exc.value.detail == "Acesso financeiro bloqueado até revisão da fronteira SQL."
    assert calls == {"provider": 0, "pool": 0}



@pytest.mark.asyncio
async def test_m41646_target_bound_success_uses_the_same_sql_destination_end_to_end(monkeypatch):
    """CP26-0061/0062/0257, TEC-09/12: fixture the exact target-first call order."""
    from contextlib import asynccontextmanager
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace
    from uuid import UUID, uuid4

    from backend.app import m41150_fastapi_rls_context as gateway

    now = datetime.now(timezone.utc)
    tenant = uuid4()
    session = SimpleNamespace(
        user_id=str(uuid4()),
        role="TENANT_ADMIN",
        tenant_id=str(tenant),
        is_master=False,
        verified_session_id=str(uuid4()),
        verified_session_at=now,
        verified_session_expires_at=now + timedelta(minutes=1),
        verification_source="POSTGRES_TOKEN_HASH_REFRESH",
    )
    events = []
    provider_calls = {}
    claims = {}

    class Connection:
        def __init__(self):
            self.challenge_count = 0
            self.reset_count = 0

        @asynccontextmanager
        async def transaction(self, *, readonly):
            assert readonly is True
            events.append("transaction_begin")
            try:
                yield
            except BaseException:
                events.append("transaction_rollback")
                raise
            else:
                events.append("transaction_end")

        async def fetchrow(self, sql):
            assert "pg_backend_pid()" in sql and "virtualxid" in sql
            events.append("read_sql_identity")
            return {
                "backend_pid": 2468,
                "virtual_xid": "7/19",
                "transaction_started_at": now,
            }

        async def fetchval(self, sql, ticket_or_seed, tenant_id):
            assert "read_target_challenge" in sql
            assert tenant_id == tenant
            self.challenge_count += 1
            events.append("pre_ticket_challenge" if self.challenge_count == 1
                          else "ticket_challenge")
            return "c" * 64 if self.challenge_count == 1 else "d" * 64

        async def execute(self, sql):
            assert sql == "RESET ALL; DISCARD TEMP;"
            self.reset_count += 1
            events.append("pool_reset")

    connection = Connection()

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            events.append("pool_acquire")
            yield connection
            events.append("pool_release")

    async def get_pool():
        events.append("pool_open")
        return Pool()

    class TargetProvider:
        capability_protocol = gateway.TARGET_BOUND_PROTOCOL

        async def issue_target_ticket(
            self, supplied_session, *, scope, request_nonce, tenant_id,
            backend_pid, virtual_xid, transaction_started_at, target_challenge,
        ):
            events.append("issue_target_ticket")
            provider_calls["issue"] = {
                "session": supplied_session,
                "scope": scope,
                "nonce": request_nonce,
                "tenant": tenant_id,
                "pid": backend_pid,
                "vxid": virtual_xid,
                "started": transaction_started_at,
                "challenge": target_challenge,
            }
            return "a" * 64

        async def issue_ticket(self, *args, **kwargs):
            events.append("legacy_issue_ticket")
            raise AssertionError("M41646_LEGACY_PROTOCOL_MUST_NOT_RUN")

        async def bind_ticket(
            self, ticket, *, tenant_id, backend_pid, virtual_xid,
            transaction_started_at, target_challenge,
        ):
            events.append("bind_ticket")
            provider_calls["bind"] = {
                "ticket": ticket,
                "tenant": tenant_id,
                "pid": backend_pid,
                "vxid": virtual_xid,
                "started": transaction_started_at,
                "challenge": target_challenge,
            }
            return "b" * 64

    async def record_claims(_connection, expected):
        events.append("verify_sql_claims")
        claims["expected"] = expected

    async def install_capability(_connection, capability):
        events.append("install_capability")
        assert capability == "b" * 64

    monkeypatch.setenv("ENVIRONMENT", "development")
    for flag in ("PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL"):
        monkeypatch.setenv(flag, "OFF")
    monkeypatch.setattr(gateway, "get_db_pool", get_pool)
    monkeypatch.setattr(gateway, "_require_bound_read_claims", record_claims)
    monkeypatch.setattr(gateway, "install_session_capability", install_capability)

    async with gateway._capability_db_connection(
        SimpleNamespace(), session, TargetProvider(), tenant
    ) as yielded:
        events.append("yield_connection")
        assert yielded is connection

    issued = provider_calls["issue"]
    bound = provider_calls["bind"]
    destination = (tenant, 2468, "7/19", now)
    assert issued["session"] is session
    assert issued["scope"] == gateway.READ_SCOPE
    assert isinstance(issued["nonce"], UUID)
    assert (issued["tenant"], issued["pid"], issued["vxid"], issued["started"]) == destination
    assert issued["challenge"] == "c" * 64
    assert bound == {
        "ticket": "a" * 64,
        "tenant": tenant,
        "pid": 2468,
        "vxid": "7/19",
        "started": now,
        "challenge": "d" * 64,
    }
    expected = claims["expected"]
    assert expected == (
        UUID(session.user_id), session.role, tenant, gateway.READ_SCOPE,
        UUID(session.verified_session_id), issued["nonce"],
    )
    assert events.index("pre_ticket_challenge") < events.index("issue_target_ticket")
    assert events.index("issue_target_ticket") < events.index("ticket_challenge")
    assert events.index("ticket_challenge") < events.index("bind_ticket")
    assert events.index("bind_ticket") < events.index("install_capability")
    assert events.index("install_capability") < events.index("verify_sql_claims")
    assert "legacy_issue_ticket" not in events
    assert connection.reset_count == 1
    assert events[-1] == "pool_release"



def test_m41647_target_first_fastapi_concurrency_is_confined_to_pg18_fixture():
    runner = RUNNER.read_text(encoding="utf-8")
    section = runner.split(
        "# M41641: the actual six FastAPI GET handlers use v5 through an explicit",
        1,
    )[1].split("\n        finally:\n            setattr(app.state", 1)[0]
    assert "assert len(read_paths) == 6" in section
    assert "concurrent_responses = await asyncio.gather" in section
    assert "len(target_provider.issued) == len({entry[0] for entry in target_provider.issued}) == 18" in section
    assert "len(target_provider.bound) == 18" in section
    assert "M41648_CROSS_TENANT_FASTAPI_CONCURRENT_READS=12_OF_12_PASS_DISPOSABLE_ONLY" in section
    assert "ORIGINAL_DATABASE=NOT_ACCESSED" in runner
    assert "MIGRATIONS=NONE" in runner
    assert "PRODUCTION=BLOCKED" in runner



def test_m41648_target_first_concurrent_reads_cover_both_tenants_in_pg18_fixture():
    runner = RUNNER.read_text(encoding="utf-8")
    section = runner.split(
        "# M41641: the actual six FastAPI GET handlers use v5 through an explicit",
        1,
    )[1].split("\n        finally:\n            setattr(app.state", 1)[0]
    for marker in (
        "admin_b_session_id = session_id_for(admin_b_digest)",
        "Bearer m41648-admin-b",
        "tenant_b_paths = [path.replace(str(tenant_a), str(tenant_b), 1)",
        "client.get(path, headers=headers) for path, headers in concurrent_requests",
        "len(target_provider.issued) == len({entry[0] for entry in target_provider.issued}) == 18",
        "M41648_CROSS_TENANT_FASTAPI_CONCURRENT_READS=12_OF_12_PASS_DISPOSABLE_ONLY",
        '"A-CASH", "A-OFFSET"',
        '"B-CASH", "B-OFFSET"',
    ):
        assert marker in runner
    assert "ORIGINAL_DATABASE=NOT_ACCESSED" in runner
    assert "MIGRATIONS=NONE" in runner
    assert "PRODUCTION=BLOCKED" in runner
