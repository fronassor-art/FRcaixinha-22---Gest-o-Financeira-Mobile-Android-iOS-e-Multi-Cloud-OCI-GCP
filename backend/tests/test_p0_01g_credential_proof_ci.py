"""P0-01g: concorrência e rotação, APENAS PostgreSQL descartável do CI."""
import asyncio
import hashlib
import os
import uuid
from urllib.parse import urlparse

import asyncpg
import pytest


def ci_dsn(key: str) -> str:
    if os.environ.get("FRCAIXINHA_CI_ISOLATED") != "1":
        pytest.skip("Somente CI descartável")
    url = os.environ[key]
    p = urlparse(url)
    if p.hostname not in ("127.0.0.1", "localhost") or p.port != 5432 or p.path != "/frcaixinha_ci":
        raise RuntimeError("DSN não é o PostgreSQL isolado de CI")
    return url


def digest(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@pytest.mark.asyncio
async def test_p0_01g_single_use_expiry_user_binding_and_password_rotation():
    admin = await asyncpg.connect(ci_dsn("CI_ADMIN_DATABASE_URL"))
    verifier = await asyncpg.connect(ci_dsn("CI_VERIFIER_DATABASE_URL"))
    auth = await asyncpg.connect(ci_dsn("CI_AUTH_DATABASE_URL"))
    actor, outsider = uuid.uuid4(), uuid.uuid4()
    try:
        for person in (actor, outsider):
            await admin.execute(
                "INSERT INTO public.users(id,email,full_name,cpf,phone) "
                "VALUES($1,$2,'Pessoa sintética P0-01g',$3,'00000000000')",
                person, f"{person}@example.invalid", person.hex[:14],
            )
            await admin.execute(
                "INSERT INTO public.credentials(user_id,password_hash) VALUES($1,$2)",
                person, "ci-original-" + person.hex,
            )
        assert not await auth.fetchval(
            "SELECT has_column_privilege(current_user,'public.credentials',"
            "'password_hash','SELECT')")
        assert not await verifier.fetchval(
            "SELECT has_table_privilege(current_user,'public.sessions','INSERT')")
        assert not await verifier.fetchval(
            "SELECT has_table_privilege(current_user,'public.auth_login_proofs','SELECT')")
        assert not await auth.fetchval(
            "SELECT has_table_privilege(current_user,'public.auth_login_proofs','SELECT')")
        assert not await auth.fetchval(
            "SELECT has_table_privilege(current_user,'public.sessions','INSERT')")

        fingerprint = digest("ci-original-" + actor.hex)

        async def insert_proof(label: str, seconds: int = 60, user=actor, fp=fingerprint):
            raw = f"ci-proof-{label}-{uuid.uuid4().hex}"
            await verifier.execute(
                "INSERT INTO public.auth_login_proofs("
                "proof_hash,user_id,credential_fingerprint,expires_at)"
                " VALUES($1,$2,$3,NOW()+($4::int * INTERVAL '1 second'))",
                digest(raw), user, fp, seconds,
            )
            return raw

        valid = await insert_proof("valid")
        token = "ci-session-" + uuid.uuid4().hex
        assert await auth.fetchval(
            "SELECT public.auth_issue_pending_session($1::uuid,$2::text,$3::text)",
            actor, token, valid,
        ) is True
        assert await auth.fetchval(
            "SELECT public.auth_issue_pending_session($1::uuid,$2::text,$3::text)",
            actor, "ci-replay-" + uuid.uuid4().hex, valid,
        ) is False
        assert await admin.fetchval(
            "SELECT count(*) FROM public.sessions WHERE token_hash=$1", digest(token),
        ) == 1

        wrong_user = await insert_proof("wrong-user")
        assert await auth.fetchval(
            "SELECT public.auth_issue_pending_session($1::uuid,$2::text,$3::text)",
            outsider, "ci-wrong-" + uuid.uuid4().hex, wrong_user,
        ) is False

        expired = await insert_proof("expired")
        await admin.execute(
            "UPDATE public.auth_login_proofs "
            "SET created_at=NOW()-INTERVAL '120 seconds', "
            "expires_at=NOW()-INTERVAL '60 seconds' "
            "WHERE proof_hash=$1", digest(expired),
        )
        assert await auth.fetchval(
            "SELECT public.auth_issue_pending_session($1::uuid,$2::text,$3::text)",
            actor, "ci-expired-" + uuid.uuid4().hex, expired,
        ) is False

        stale = await insert_proof("stale")
        await admin.execute(
            "UPDATE public.credentials SET password_hash=$2 WHERE user_id=$1",
            actor, "ci-rotated-" + actor.hex,
        )
        assert await admin.fetchval(
            "SELECT revoked_at IS NOT NULL FROM public.sessions WHERE token_hash=$1",
            digest(token),
        ) is True
        assert await auth.fetchval(
            "SELECT public.auth_issue_pending_session($1::uuid,$2::text,$3::text)",
            actor, "ci-stale-" + uuid.uuid4().hex, stale,
        ) is False

        fresh = await insert_proof("fresh", fp=digest("ci-rotated-" + actor.hex))
        fresh_token = "ci-new-session-" + uuid.uuid4().hex
        assert await auth.fetchval(
            "SELECT public.auth_issue_pending_session($1::uuid,$2::text,$3::text)",
            actor, fresh_token, fresh,
        ) is True
        await admin.execute("DELETE FROM public.credentials WHERE user_id=$1", actor)
        assert await admin.fetchval(
            "SELECT revoked_at IS NOT NULL FROM public.sessions WHERE token_hash=$1",
            digest(fresh_token),
        ) is True
        assert await auth.fetchval(
            "SELECT public.auth_issue_pending_session($1::uuid,$2::text,$3::text)",
            actor, "ci-missing-cred-" + uuid.uuid4().hex, fresh,
        ) is False
    finally:
        await auth.close()
        await verifier.close()
        await admin.execute(
            "DELETE FROM public.users WHERE id=ANY($1::uuid[])", [actor, outsider],
        )
        await admin.close()


@pytest.mark.asyncio
async def test_p0_01g_two_independent_auth_connections_race_for_one_proof():
    admin = await asyncpg.connect(ci_dsn("CI_ADMIN_DATABASE_URL"))
    verifier = await asyncpg.connect(ci_dsn("CI_VERIFIER_DATABASE_URL"))
    first = await asyncpg.connect(ci_dsn("CI_AUTH_DATABASE_URL"))
    second = await asyncpg.connect(ci_dsn("CI_AUTH_DATABASE_URL"))
    actor = uuid.uuid4()
    try:
        await admin.execute(
            "INSERT INTO public.users(id,email,full_name,cpf,phone) "
            "VALUES($1,$2,'CI concorrência',$3,'00000000000')",
            actor, f"{actor}@example.invalid", actor.hex[:14],
        )
        password_hash = "ci-secret-" + actor.hex
        await admin.execute(
            "INSERT INTO public.credentials(user_id,password_hash) VALUES($1,$2)",
            actor, password_hash,
        )
        raw_proof = "ci-concurrent-proof-" + uuid.uuid4().hex
        await verifier.execute(
            "INSERT INTO public.auth_login_proofs("
            "proof_hash,user_id,credential_fingerprint,expires_at)"
            " VALUES($1,$2,$3,NOW()+INTERVAL '60 seconds')",
            digest(raw_proof), actor, digest(password_hash),
        )
        raw_tokens = ["ci-race-a-" + uuid.uuid4().hex, "ci-race-b-" + uuid.uuid4().hex]
        gate = asyncio.Event()

        async def issue(connection, token):
            await gate.wait()
            return await connection.fetchval(
                "SELECT public.auth_issue_pending_session($1::uuid,$2::text,$3::text)",
                actor, token, raw_proof,
            )

        attempts = [
            asyncio.create_task(issue(first, raw_tokens[0])),
            asyncio.create_task(issue(second, raw_tokens[1])),
        ]
        gate.set()
        results = await asyncio.wait_for(asyncio.gather(*attempts), timeout=10)
        assert sorted(results) == [False, True], results
        assert await admin.fetchval(
            "SELECT count(*) FROM public.sessions "
            "WHERE token_hash=ANY($1::text[])",
            [digest(x) for x in raw_tokens],
        ) == 1, "Concorrência gerou duas sessões a partir da mesma prova"
    finally:
        await first.close()
        await second.close()
        await verifier.close()
        await admin.execute("DELETE FROM public.users WHERE id=$1", actor)
        await admin.close()
