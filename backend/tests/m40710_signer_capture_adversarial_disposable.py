#!/usr/bin/env python3
"""M40710: SQL signing-key exposure / first-use stolen claim adversarial proof.

Entirely synthetic, only PostgreSQL 18 disposable CI on 127.0.0.1:55440.
IMPORTANT: expected outputs expose risk, not remediation or production readiness.
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

DB = "fr_m40710_disposable_ci"
PORT = 55440
GATE_ENV = {
    "GITHUB_ACTIONS": "true",
    "CI_M40710_DISPOSABLE": "1",
    "FRCAIXINHA_CI_ISOLATED": "1",
    "PIX_REAL": "OFF",
    "PAGAMENTOS_REAIS": "OFF",
    "ATIVACAO_REAL": "OFF",
}


def require_disposable() -> None:
    if any(os.environ.get(k) != v for k, v in GATE_ENV.items()):
        raise RuntimeError("M40710_DISPOSABLE_ONLY")
    try:
        u = urlsplit(os.environ.get("CI_M40710_DATABASE_URL", ""))
        if (u.scheme != "postgresql" or u.hostname != "127.0.0.1"
                or u.port != PORT or u.path != "/" + DB
                or u.username != "postgres" or not u.password
                or u.query or u.fragment):
            raise RuntimeError("M40710_WRONG_DATABASE_IDENTITY")
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("M40710_WRONG_DATABASE_IDENTITY") from exc


def proof(owner) -> None:
    import psycopg
    from psycopg.conninfo import make_conninfo
    from m40700_request_proof_disposable import (
        SCOPE, bootstrap, sign,
    )

    # Synthetic users/sessions and transient key on disposable PG18 only.
    trusted_key = secrets.token_bytes(32)
    bootstrap(owner, trusted_key)
    tenant_a, tenant_b = uuid4(), uuid4()
    user_a, user_b = uuid4(), uuid4()
    entry_a, entry_b = uuid4(), uuid4()
    for user in (user_a, user_b):
        owner.execute(
            "INSERT INTO m40650.users VALUES (%s,'ACTIVE',false)",
            (user,),
        )
        owner.execute(
            "INSERT INTO m40650.memberships "
            "VALUES (%s,%s,'TENANT_MEMBER','ATIVA')",
            (user, tenant_a),
        )
    for eid, user, value in (
        (entry_a, user_a, 125),
        (entry_b, user_b, 375),
    ):
        owner.execute(
            "INSERT INTO m40650.entries VALUES (%s,%s,%s,%s)",
            (eid, tenant_a, user, value),
        )
    digest_a = sha256(secrets.token_urlsafe(40).encode()).hexdigest()
    digest_b = sha256(secrets.token_urlsafe(40).encode()).hexdigest()
    future = datetime.now(timezone.utc)+timedelta(hours=1)
    for digest, user in ((digest_a, user_a), (digest_b, user_b)):
        owner.execute(
            "INSERT INTO m40650.sessions VALUES "
            "(%s,%s,'TENANT_MEMBER',%s,%s,NULL)",
            (digest, user, tenant_a, future),
        )

    root = os.environ["CI_M40710_DATABASE_URL"]
    auth_dsn = make_conninfo(
        root, user="m40680_auth_login",
        password="m40680-fixture-auth-only-not-real",
    )
    financial_dsn = make_conninfo(
        root, user="m40650_ci_login",
        password="synthetic-only-m40650-ci-not-a-real-credential",
    )

    def new_claim(digest, tenant=tenant_a, *, key=trusted_key, nonce=None):
        nonce = nonce if nonce is not None else uuid4()
        expiry = int(datetime.now(timezone.utc).timestamp()) + 15
        return (digest, tenant, nonce, expiry, SCOPE,
                sign(key, digest, tenant, nonce, expiry, SCOPE))

    def issue(claim, *, user_settable_guc=False):
        with psycopg.connect(auth_dsn, autocommit=True) as auth:
            auth.execute("SET ROLE m40680_auth")
            if user_settable_guc:
                auth.execute(
                    "SELECT pg_catalog.set_config('app.current_role','MASTER',false)"
                )
                auth.execute(
                    "SELECT pg_catalog.set_config('app.current_tenant_id',%s,false)",
                    (str(tenant_b),),
                )
            return auth.execute(
                "SELECT m40700.issue_bound(%s,%s,%s,%s,%s,%s)",
                claim,
            ).fetchone()[0]

    def consume(ticket, tenant=tenant_a):
        with psycopg.connect(financial_dsn, autocommit=True) as fin:
            fin.execute("SET ROLE m40650_app")
            return fin.execute(
                "SELECT m40650.m40680_consume(%s,%s)",
                (ticket, tenant),
            ).fetchone()[0]

    # SQL auth role must not extract HMAC key, access nonce table, or use
    # legacy digest-only issuer; SQL financial role cannot access signer.
    with psycopg.connect(auth_dsn, autocommit=True) as auth:
        auth.execute("SET ROLE m40680_auth")
        assert auth.execute("SELECT session_user").fetchone()[0] == "m40680_auth_login"
        for name in ("verifier_secret", "used_nonces"):
            assert not auth.execute(
                "SELECT pg_catalog.has_table_privilege('m40680_auth',%s,'SELECT')",
                ("m40700."+name,),
            ).fetchone()[0]
        assert not auth.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40680_auth','m40650.m40680_issue(text,uuid)','EXECUTE')"
        ).fetchone()[0]
    with psycopg.connect(financial_dsn, autocommit=True) as fin:
        fin.execute("SET ROLE m40650_app")
        assert fin.execute("SELECT session_user").fetchone()[0] == "m40650_ci_login"
        assert not fin.execute(
            "SELECT pg_catalog.has_schema_privilege("
            "'m40650_app','m40700','USAGE')"
        ).fetchone()[0]
        # The function OID can be checked without granting schema USAGE.
        assert not fin.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40650_app',p.oid,'EXECUTE') "
            "FROM pg_catalog.pg_proc AS p "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid=p.pronamespace "
            "WHERE n.nspname='m40700' AND p.proname='issue_bound'"
        ).fetchone()[0]
    print("M40710_LOW_PRIVILEGE_SIGNING_SECRET_AND_ISSUER_ACL=PASS")

    # A stolen digest + SQL auth privilege without the signing key is rejected
    # despite spoofed SQL GUC; this is a narrow protection, not PoP.
    wrong = new_claim(digest_a, key=secrets.token_bytes(32))
    assert issue(wrong, user_settable_guc=True) is None
    print("M40710_DIGEST_PLUS_AUTH_ROLE_WITHOUT_SIGNER_KEY=DENIED")

    # Attacker with auth SQL access plus a VALID pre-use captured claim wins:
    # the legitimate signer gets no second ticket. No HTTP identity/channel
    # proof is bound to the claim, even with nonce and short expiry.
    stolen = new_claim(digest_a)
    attacker_ticket = issue(stolen, user_settable_guc=True)
    assert attacker_ticket and len(attacker_ticket) == 64
    assert issue(stolen) is None
    first = consume(attacker_ticket)
    assert first["authorized"] is True
    assert {x["id"] for x in first["entries"]} == {str(entry_a)}
    assert consume(attacker_ticket)["authorized"] is False
    print("M40710_PREUSE_CAPTURED_SIGNED_CLAIM_ACCEPTED=CONFIRMED_NO_GO")

    # Parallel interception of ONE valid signed claim: one wins; not
    # necessarily the genuine holder. The nonce limits duplication but
    # does not establish possession of the original Bearer or device key.
    workers = 6
    for _ in range(2):
        race_claim = new_claim(digest_a)
        barrier = Barrier(workers, timeout=20)

        def race(_index):
            with psycopg.connect(auth_dsn, autocommit=True) as auth:
                auth.execute("SET ROLE m40680_auth")
                barrier.wait(timeout=20)
                return auth.execute(
                    "SELECT m40700.issue_bound(%s,%s,%s,%s,%s,%s)",
                    race_claim,
                ).fetchone()[0]

        with ThreadPoolExecutor(max_workers=workers) as pool:
            issued = list(pool.map(race, range(workers)))
        tickets = [value for value in issued if value is not None]
        assert len(tickets) == 1
        assert len(issued) - len(tickets) == workers - 1
        assert consume(tickets[0])["authorized"] is True
    print("M40710_CONCURRENT_SIGNED_CLAIM_SINGLE_REDEEM=PASS")
    print("M40710_PREUSE_INTERCEPTION_RISK=NOT_REMEDIATED")

    # Privileged fixture database owner can extract the symmetric HMAC
    # signing key. A stolen key can forge a new claim for ANY active
    # digest and allowed tenant. No actual secret is emitted to logs.
    extracted = owner.execute(
        "SELECT key FROM m40700.verifier_secret WHERE singleton=true"
    ).fetchone()[0]
    assert bytes(extracted) == trusted_key
    forged = new_claim(digest_b, key=bytes(extracted))
    forged_ticket = issue(forged)
    assert forged_ticket
    leaked = consume(forged_ticket)
    assert leaked["authorized"] is True
    assert {x["id"] for x in leaked["entries"]} == {str(entry_b)}
    print("M40710_DATABASE_OWNER_HMAC_KEY_EXTRACTION=CONFIRMED_NO_GO")
    print("M40710_EXTRACTED_HMAC_KEY_CAN_FORGE_SESSION_CLAIM=CONFIRMED_NO_GO")

    # HMAC proof and ticket remain SQL parameters: SQL/logging exposure is a
    # threat, not resolved by parameterization or avoiding raw Bearer text.
    assert forged[-1] and len(forged[-1]) == 64
    assert len(forged_ticket) == 64
    print("M40710_SIGNED_CLAIM_SQL_PARAMETER_EXPOSURE=NOT_REMEDIATED")
    print("M40710_NO_REAL_SIGNER_OR_FASTAPI_INTEGRATION=PASS")
    print("M40710_ORIGINAL_GUC_SPOOF=NOT_REMEDIATED")


def main() -> int:
    print("=== FR FINANCE M40710 — SIGNING KEY / FIRST USE INTERCEPTION ===")
    try:
        require_disposable()
        # No driver import or connection occurs before exact CI gate.
        import psycopg
        with psycopg.connect(os.environ["CI_M40710_DATABASE_URL"],
                             autocommit=True) as owner:
            proof(owner)
    except Exception as exc:
        import traceback
        frames = traceback.extract_tb(exc.__traceback__)
        if frames:
            last = frames[-1]
            print("M40710_FAILURE_SITE=" + last.name + ":" + str(last.lineno))
        if getattr(exc, "sqlstate", None):
            print("M40710_SQLSTATE=" + exc.sqlstate)
        print("M40710_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40710_ORIGINAL_PG_5433=NOT_ACCESSED")
        print("M40710_LOCAL_DB_WRITES=NONE")
        print("M40710_MIGRATIONS=NONE")
        print("M40710_SERVICE_RESTARTS=NONE")
        print("M40710_PIX_REAL=OFF")
        print("M40710_PAGAMENTOS_REAIS=OFF")
        print("M40710_ATIVACAO_REAL=OFF")
        print("M40710_PRODUCTION=BLOCKED")
    print("M40710_STATUS=PASS_ADVERSARIAL_PROOF_NO_GO_PRODUCTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
