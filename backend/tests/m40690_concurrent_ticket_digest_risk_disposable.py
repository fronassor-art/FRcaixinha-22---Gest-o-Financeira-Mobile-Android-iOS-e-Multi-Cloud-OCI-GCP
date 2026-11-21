#!/usr/bin/env python3
"""M40690: adversarial PG18 concurrent ticket consumption and digest replay proof.

Runs ONLY in a disposable GitHub Actions PG18 database. This is not a
migration, a real HTTP integration, or remediation of the legacy GUC flaw.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from threading import Barrier
from urllib.parse import urlsplit
from uuid import uuid4
import os
import secrets

DB = "fr_m40690_disposable_ci"
PORT = 55438


def require_isolated_ci() -> None:
    expected = {
        "GITHUB_ACTIONS": "true",
        "CI_M40690_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }
    if any(os.environ.get(k) != v for k, v in expected.items()):
        raise RuntimeError("M40690_DISPOSABLE_ONLY")
    try:
        u = urlsplit(os.environ.get("CI_M40690_DATABASE_URL", ""))
        if (u.scheme != "postgresql" or u.hostname != "127.0.0.1"
                or u.port != PORT or u.path != "/" + DB
                or u.username != "postgres" or not u.password
                or u.query or u.fragment):
            raise RuntimeError("M40690_WRONG_DATABASE_IDENTITY")
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("M40690_WRONG_DATABASE_IDENTITY") from exc


def proof(owner) -> None:
    # Import other fixture only after the identity gate in main().
    import psycopg
    from psycopg.conninfo import make_conninfo
    from m40680_digest_one_time_gateway_disposable import bootstrap

    bootstrap(owner)
    tenant_a, tenant_b = uuid4(), uuid4()
    member_a, member_b = uuid4(), uuid4()
    entry_a, entry_b = uuid4(), uuid4()

    for uid in (member_a, member_b):
        owner.execute("INSERT INTO m40650.users VALUES (%s,'ACTIVE',false)", (uid,))
    for uid, tenant in ((member_a, tenant_a), (member_a, tenant_b),
                        (member_b, tenant_a)):
        owner.execute(
            "INSERT INTO m40650.memberships VALUES (%s,%s,'TENANT_MEMBER','ATIVA')",
            (uid, tenant),
        )
    for eid, tenant, uid, amount in (
        (entry_a, tenant_a, member_a, 125),
        (entry_b, tenant_a, member_b, 250),
    ):
        owner.execute(
            "INSERT INTO m40650.entries VALUES (%s,%s,%s,%s)",
            (eid, tenant, uid, amount),
        )

    raw_a, raw_b = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    digest_a = sha256(raw_a.encode("utf-8")).hexdigest()
    digest_b = sha256(raw_b.encode("utf-8")).hexdigest()
    future = datetime.now(timezone.utc) + timedelta(hours=1)
    for digest, uid in ((digest_a, member_a), (digest_b, member_b)):
        owner.execute(
            "INSERT INTO m40650.sessions VALUES (%s,%s,'TENANT_MEMBER',%s,%s,NULL)",
            (digest, uid, tenant_a, future),
        )

    root_dsn = os.environ["CI_M40690_DATABASE_URL"]
    auth_dsn = make_conninfo(
        root_dsn, user="m40680_auth_login",
        password="m40680-fixture-auth-only-not-real",
    )
    app_dsn = make_conninfo(
        root_dsn, user="m40650_ci_login",
        password="synthetic-only-m40650-ci-not-a-real-credential",
    )

    def issue(digest: str, tenant):
        with psycopg.connect(auth_dsn, autocommit=True) as auth:
            auth.execute("SET ROLE m40680_auth")
            assert auth.execute("SELECT session_user").fetchone()[0] == "m40680_auth_login"
            return auth.execute(
                "SELECT m40650.m40680_issue(%s,%s)", (digest, tenant)
            ).fetchone()[0]

    def consume(ticket: str, tenant):
        with psycopg.connect(app_dsn, autocommit=True) as financial:
            financial.execute("SET ROLE m40650_app")
            assert financial.execute("SELECT session_user").fetchone()[0] == "m40650_ci_login"
            return financial.execute(
                "SELECT m40650.m40680_consume(%s,%s)", (ticket, tenant)
            ).fetchone()[0]

    # Real SQL role separation: not a superuser merely impersonating app.
    with psycopg.connect(auth_dsn, autocommit=True) as auth:
        auth.execute("SET ROLE m40680_auth")
        assert not auth.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40680_auth','m40650.m40680_consume(text,uuid)','EXECUTE')"
        ).fetchone()[0]
        assert not auth.execute(
            "SELECT pg_catalog.has_table_privilege("
            "'m40680_auth','m40650.sessions','SELECT')"
        ).fetchone()[0]
    with psycopg.connect(app_dsn, autocommit=True) as financial:
        financial.execute("SET ROLE m40650_app")
        assert not financial.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40650_app','m40650.m40680_issue(text,uuid)','EXECUTE')"
        ).fetchone()[0]
        assert not financial.execute(
            "SELECT pg_catalog.has_table_privilege("
            "'m40650_app','m40650.m40680_tickets','UPDATE')"
        ).fetchone()[0]
        assert not financial.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40650_app','m40650.read_entries(text,uuid)','EXECUTE')"
        ).fetchone()[0]
    print("M40690_AUTH_FINANCIAL_SQL_ROLE_SEPARATION=PASS")

    # Two truly concurrent app-role connections racing on the SAME ticket
    # should never both authorize. Repeat to catch common row-lock mistakes.
    for trial in range(3):
        ticket = issue(digest_a, tenant_a)
        assert ticket is not None and len(ticket) == 64
        workers = 8
        barrier = Barrier(workers, timeout=20)

        def race(_):
            with psycopg.connect(app_dsn, autocommit=True) as financial:
                financial.execute("SET ROLE m40650_app")
                barrier.wait(timeout=20)
                return financial.execute(
                    "SELECT m40650.m40680_consume(%s,%s)",
                    (ticket, tenant_a),
                ).fetchone()[0]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(race, range(workers)))
        wins = [r for r in results if r["authorized"] is True]
        losses = [r for r in results if r["authorized"] is False]
        assert len(wins) == 1 and len(losses) == workers - 1
        assert {e["id"] for e in wins[0]["entries"]} == {str(entry_a)}
        assert all("entries" not in denied for denied in losses)
    print("M40690_EIGHT_PARALLEL_CONSUMERS_SINGLE_SUCCESS=PASS")

    # Wrong-tenant guesses cannot consume a valid ticket or widen data.
    one = issue(digest_a, tenant_a)
    assert one
    assert consume(one, tenant_b)["authorized"] is False
    assert consume(one, tenant_a)["authorized"] is True
    assert consume(one, tenant_a)["authorized"] is False
    assert issue(digest_a, tenant_b) is None
    print("M40690_CROSS_TENANT_GUESS_NO_AUTHORIZATION=PASS")

    # An observed SHA-256 Bearer digest is sufficient to mint extra tickets
    # if the authentication SQL role is compromised. This is a failing
    # design property, not a risk we can mark remediated.
    stolen_digest = digest_b
    cap1 = issue(stolen_digest, tenant_a)
    cap2 = issue(stolen_digest, tenant_a)
    assert cap1 and cap2 and cap1 != cap2
    assert consume(cap1, tenant_a)["authorized"] is True
    assert consume(cap2, tenant_a)["authorized"] is True
    print("M40690_DIGEST_REPLAY_MINTS_MULTIPLE_TICKETS=CONFIRMED_NO_GO")

    # Revocation is checked again at consume time.
    late_ticket = issue(digest_a, tenant_a)
    assert late_ticket
    owner.execute(
        "UPDATE m40650.sessions SET revoked_at=pg_catalog.clock_timestamp() "
        "WHERE token_digest=%s", (digest_a,),
    )
    assert consume(late_ticket, tenant_a)["authorized"] is False
    assert issue(digest_a, tenant_a) is None
    print("M40690_REVOKED_SESSION_CANNOT_USE_PREISSUED_TICKET=PASS")

    # Membership suspension blocks already issued capabilities as well.
    pending = issue(digest_b, tenant_a)
    assert pending
    owner.execute(
        "UPDATE m40650.memberships SET status='DESLIGADA' "
        "WHERE user_id=%s AND tenant_id=%s",
        (member_b, tenant_a),
    )
    assert consume(pending, tenant_a)["authorized"] is False
    assert issue(digest_b, tenant_a) is None
    print("M40690_DISABLED_MEMBERSHIP_CANNOT_USE_PREISSUED_TICKET=PASS")

    print("M40690_HTTP_AND_REAL_SQL_ROUTES=NOT_MODIFIED")
    print("M40690_AUTH_DIGEST_CREDENTIAL_EQUIVALENCE=NOT_REMEDIATED")
    print("M40690_SQL_LOG_LEAKAGE_AND_TELEMETRY=NOT_ATTESTED")
    print("M40690_EXISTING_GUC_SPOOF=NOT_REMEDIATED")


def main() -> int:
    print("=== FR FINANCE M40690 — CONCURRENT TICKET / DIGEST REPLAY ===")
    try:
        require_isolated_ci()
        # Neither importing a DB driver nor connecting precedes the CI gate.
        import psycopg
        with psycopg.connect(os.environ["CI_M40690_DATABASE_URL"],
                             autocommit=True) as owner:
            proof(owner)
    except Exception as exc:
        import traceback
        frames = traceback.extract_tb(exc.__traceback__)
        if frames:
            last = frames[-1]
            print("M40690_FAILURE_SITE=" + last.name + ":" + str(last.lineno))
        print("M40690_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40690_ORIGINAL_PG_5433=NOT_ACCESSED")
        print("M40690_LOCAL_DB_WRITES=NONE")
        print("M40690_LOCAL_MIGRATIONS=NONE")
        print("M40690_LOCAL_SERVICE_RESTARTS=NONE")
        print("M40690_PIX_REAL=OFF")
        print("M40690_PAGAMENTOS_REAIS=OFF")
        print("M40690_ATIVACAO_REAL=OFF")
        print("M40690_PRODUCTION=BLOCKED")
    print("M40690_STATUS=PASS_ISOLATED_TEST_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
