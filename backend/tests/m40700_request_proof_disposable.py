#!/usr/bin/env python3
"""M40700: synthetic request-bound HMAC claim before SQL ticket issuance.

CI PostgreSQL 18 disposable only. Proves a leaked bearer digest by itself
cannot invoke the restricted issuer. NOT production authentication, NOT
migration, NOT an integration into existing FastAPI/RLS routes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import os
import secrets
from urllib.parse import urlsplit
from uuid import UUID, uuid4

DB = "fr_m40700_disposable_ci"
PORT = 55439
SCOPE = "READ_ENTRIES"


def require_disposable_ci() -> None:
    expected = {
        "GITHUB_ACTIONS": "true",
        "CI_M40700_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("M40700_DISPOSABLE_ONLY")
    try:
        u = urlsplit(os.environ.get("CI_M40700_DATABASE_URL", ""))
        if (u.scheme != "postgresql" or u.hostname != "127.0.0.1"
                or u.port != PORT or u.path != "/" + DB
                or u.username != "postgres" or not u.password
                or u.query or u.fragment):
            raise RuntimeError("M40700_WRONG_POSTGRES_IDENTITY")
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("M40700_WRONG_POSTGRES_IDENTITY") from exc


def message(digest: str, tenant: UUID, nonce: UUID, expiry: int,
            scope: str = SCOPE) -> bytes:
    return (f"FRF-M40700|v1|{digest}|{tenant}|{nonce}|{expiry}|{scope}").encode("utf-8")


def sign(secret: bytes, digest: str, tenant: UUID, nonce: UUID, expiry: int,
         scope: str = SCOPE) -> str:
    return hmac.new(secret, message(digest, tenant, nonce, expiry, scope),
                    sha256).hexdigest()


def bootstrap(owner, verifier_secret: bytes) -> None:
    # All referenced schemas, roles and records are synthetic and disposable.
    from m40680_digest_one_time_gateway_disposable import bootstrap as old
    old(owner)
    owner.execute("REVOKE EXECUTE ON FUNCTION m40650.m40680_issue(text,uuid) "
                  "FROM m40680_auth")
    owner.execute("CREATE SCHEMA m40700 AUTHORIZATION m40650_owner")
    owner.execute("REVOKE ALL ON SCHEMA m40700 FROM PUBLIC")
    owner.execute("GRANT USAGE ON SCHEMA m40700 TO m40680_auth")
    owner.execute("CREATE EXTENSION pgcrypto WITH SCHEMA m40700")
    owner.execute("""
        CREATE TABLE m40700.verifier_secret(
          singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
          key bytea NOT NULL
        )
    """)
    owner.execute("ALTER TABLE m40700.verifier_secret OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON m40700.verifier_secret FROM PUBLIC, m40680_auth, m40650_app")
    owner.execute("INSERT INTO m40700.verifier_secret(singleton,key) VALUES(true,%s)",
                  (verifier_secret,))
    owner.execute("""
        CREATE TABLE m40700.used_nonces (
          nonce uuid PRIMARY KEY,
          session_digest text NOT NULL,
          tenant_id uuid NOT NULL,
          accepted_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
        )
    """)
    owner.execute("ALTER TABLE m40700.used_nonces OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON m40700.used_nonces FROM PUBLIC, m40680_auth, m40650_app")
    owner.execute("""
        CREATE FUNCTION m40700.issue_bound(
            p_digest text, p_tenant uuid, p_nonce uuid,
            p_expiry bigint, p_scope text, p_proof text
        )
        RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE
          v_secret bytea;
          v_payload text;
          v_expected text;
          v_nonce uuid;
          v_ticket text;
        BEGIN
          IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
             OR p_tenant IS NULL OR p_nonce IS NULL
             OR p_expiry IS NULL OR p_scope IS DISTINCT FROM 'READ_ENTRIES'
             OR p_proof IS NULL OR p_proof !~ '^[0-9a-f]{64}$'
             OR p_expiry<=pg_catalog.floor(
                    pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint
             OR p_expiry>pg_catalog.floor(
                    pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint+30
          THEN RETURN NULL; END IF;

          SELECT k.key INTO v_secret FROM m40700.verifier_secret AS k
          WHERE k.singleton=true;
          IF NOT FOUND THEN RETURN NULL; END IF;

          v_payload='FRF-M40700|v1|'||p_digest||'|'||p_tenant::text||'|'||
                    p_nonce::text||'|'||p_expiry::text||'|'||p_scope;
          v_expected=pg_catalog.encode(
              m40700.hmac(pg_catalog.convert_to(v_payload,'UTF8'),v_secret,'sha256'),
              'hex');
          -- Educational equality only, not certified constant-time comparison.
          IF p_proof<>v_expected THEN RETURN NULL; END IF;

          PERFORM 1 FROM m40650.sessions AS s
            JOIN m40650.users AS u ON u.id=s.user_id AND u.status='ACTIVE'
            JOIN m40650.memberships AS m
              ON m.user_id=s.user_id AND m.tenant_id=s.active_tenant_id
             AND m.role=s.active_role AND m.status='ATIVA'
          WHERE s.token_digest=p_digest
            AND s.revoked_at IS NULL
            AND s.expires_at>pg_catalog.clock_timestamp()
            AND s.active_role IN ('TENANT_MEMBER','TENANT_ADMIN')
            AND s.active_tenant_id=p_tenant;
          IF NOT FOUND THEN RETURN NULL; END IF;

          INSERT INTO m40700.used_nonces(nonce,session_digest,tenant_id)
          VALUES(p_nonce,p_digest,p_tenant)
          ON CONFLICT(nonce) DO NOTHING RETURNING nonce INTO v_nonce;
          IF NOT FOUND THEN RETURN NULL; END IF;

          v_ticket=pg_catalog.replace(pg_catalog.gen_random_uuid()::text,'-','')
                   ||pg_catalog.replace(pg_catalog.gen_random_uuid()::text,'-','');
          INSERT INTO m40650.m40680_tickets(
            digest,session_digest,tenant_id,expires_at
          ) VALUES (
            pg_catalog.encode(
              pg_catalog.sha256(pg_catalog.convert_to(v_ticket,'UTF8')),'hex'),
            p_digest,p_tenant,
            pg_catalog.clock_timestamp()+interval '20 seconds'
          );
          RETURN v_ticket;
        END
        $body$
    """)
    owner.execute("ALTER FUNCTION m40700.issue_bound(text,uuid,uuid,bigint,text,text) "
                  "OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON FUNCTION "
                  "m40700.issue_bound(text,uuid,uuid,bigint,text,text) "
                  "FROM PUBLIC,m40650_app")
    owner.execute("GRANT EXECUTE ON FUNCTION "
                  "m40700.issue_bound(text,uuid,uuid,bigint,text,text) "
                  "TO m40680_auth")


def proof(owner) -> None:
    import psycopg
    from psycopg.conninfo import make_conninfo
    verifier_secret = secrets.token_bytes(32)
    bootstrap(owner, verifier_secret)
    print("M40700_PHASE=BOOTSTRAP_COMPLETED")
    ta, tb = uuid4(), uuid4()
    member, other, admin = uuid4(), uuid4(), uuid4()
    e1, e2 = uuid4(), uuid4()
    for user in (member, other, admin):
        owner.execute("INSERT INTO m40650.users VALUES (%s,'ACTIVE',false)", (user,))
    for user, tenant, role in (
        (member, ta, "TENANT_MEMBER"), (member, tb, "TENANT_MEMBER"),
        (other, ta, "TENANT_MEMBER"), (admin, ta, "TENANT_ADMIN"),
    ):
        owner.execute(
            "INSERT INTO m40650.memberships VALUES (%s,%s,%s,'ATIVA')",
            (user, tenant, role),
        )
    for entry, user, amount in ((e1, member, 120), (e2, other, 240)):
        owner.execute("INSERT INTO m40650.entries VALUES (%s,%s,%s,%s)",
                      (entry, ta, user, amount))
    raw_member = secrets.token_urlsafe(40)
    digest_member = sha256(raw_member.encode()).hexdigest()
    digest_other = sha256(secrets.token_urlsafe(40).encode()).hexdigest()
    expires_at = datetime.now(timezone.utc)+timedelta(hours=1)
    for digest,user,role in (
        (digest_member,member,"TENANT_MEMBER"),
        (digest_other,other,"TENANT_MEMBER"),
    ):
        owner.execute("INSERT INTO m40650.sessions VALUES (%s,%s,%s,%s,%s,NULL)",
                      (digest,user,role,ta,expires_at))
    root_dsn = os.environ["CI_M40700_DATABASE_URL"]
    auth_dsn = make_conninfo(root_dsn,user="m40680_auth_login",
                             password="m40680-fixture-auth-only-not-real")
    app_dsn = make_conninfo(root_dsn,user="m40650_ci_login",
                            password="synthetic-only-m40650-ci-not-a-real-credential")

    def issue(digest, tenant, nonce, expiry, scope, proof_value):
        with psycopg.connect(auth_dsn,autocommit=True) as auth:
            auth.execute("SET ROLE m40680_auth")
            return auth.execute(
                "SELECT m40700.issue_bound(%s,%s,%s,%s,%s,%s)",
                (digest,tenant,nonce,expiry,scope,proof_value),
            ).fetchone()[0]

    def consume(ticket, tenant):
        with psycopg.connect(app_dsn,autocommit=True) as financial:
            financial.execute("SET ROLE m40650_app")
            return financial.execute(
                "SELECT m40650.m40680_consume(%s,%s)",(ticket,tenant)
            ).fetchone()[0]

    def approved(digest, tenant=ta, *, nonce=None, expiry=None, scope=SCOPE):
        nonce = nonce or uuid4()
        expiry = expiry if expiry is not None else int(
            datetime.now(timezone.utc).timestamp())+15
        proof_value = sign(verifier_secret,digest,tenant,nonce,expiry,scope)
        return issue(digest,tenant,nonce,expiry,scope,proof_value)

    # Real low-privilege SQL logins, not SET ROLE from the postgres superuser.
    with psycopg.connect(auth_dsn,autocommit=True) as a:
        a.execute("SET ROLE m40680_auth")
        assert a.execute("SELECT session_user").fetchone()[0]=="m40680_auth_login"
        for table in ("m40700.verifier_secret","m40700.used_nonces",
                      "m40650.sessions","m40650.m40680_tickets"):
            assert not a.execute(
                "SELECT pg_catalog.has_table_privilege('m40680_auth',%s,'SELECT')",
                (table,),
            ).fetchone()[0]
        assert not a.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40680_auth','m40650.m40680_issue(text,uuid)','EXECUTE')"
        ).fetchone()[0]
    print("M40700_PHASE=AUTH_ROLE_PRIVILEGES_COMPLETED")
    with psycopg.connect(app_dsn,autocommit=True) as a:
        a.execute("SET ROLE m40650_app")
        assert not a.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40650_app','m40700.issue_bound(text,uuid,uuid,bigint,text,text)','EXECUTE')"
        ).fetchone()[0]
        assert not a.execute(
            "SELECT pg_catalog.has_table_privilege("
            "'m40650_app','m40700.verifier_secret','SELECT')"
        ).fetchone()[0]
    print("M40700_PHASE=FINANCIAL_ROLE_PRIVILEGES_COMPLETED")
    print("M40700_SIGNING_SECRET_AND_ROLE_ACL_DENIED=PASS")

    # An attacker with only the bearer digest and the auth SQL role
    # CANNOT issue: the unrelated verifier secret remains inaccessible.
    nonce=uuid4()
    expiry=int(datetime.now(timezone.utc).timestamp())+15
    assert issue(digest_member,ta,nonce,expiry,SCOPE,"0"*64) is None
    assert issue(digest_member,ta,nonce,expiry,SCOPE,
                 sign(secrets.token_bytes(32),digest_member,ta,nonce,expiry)) is None
    assert issue(digest_member,ta,nonce,expiry,SCOPE,
                 sign(verifier_secret,digest_member,tb,nonce,expiry)) is None
    assert issue(digest_member,ta,nonce,expiry,SCOPE,
                 sign(verifier_secret,digest_member,ta,uuid4(),expiry)) is None
    assert issue(digest_member,ta,nonce,expiry,SCOPE,
                 sign(verifier_secret,digest_member,ta,nonce,expiry+1)) is None
    assert issue(digest_member,ta,nonce,expiry,"WRITE_ENTRIES",
                 sign(verifier_secret,digest_member,ta,nonce,expiry,"WRITE_ENTRIES")) is None
    assert approved(digest_member,ta,expiry=expiry-100) is None
    assert approved(digest_member,ta,expiry=expiry+300) is None
    assert approved(digest_member,tb) is None
    print("M40700_DIGEST_ALONE_AND_TAMPERED_ATTESTATION_DENIED=PASS")

    same_nonce=uuid4()
    signed=sign(verifier_secret,digest_member,ta,same_nonce,expiry)
    first=issue(digest_member,ta,same_nonce,expiry,SCOPE,signed)
    assert first and len(first)==64
    assert issue(digest_member,ta,same_nonce,expiry,SCOPE,signed) is None
    assert consume(first,ta)["authorized"] is True
    assert consume(first,ta)["authorized"] is False
    assert consume(first,tb)["authorized"] is False
    print("M40700_NONCE_REPLAY_AND_TICKET_REPLAY_DENIED=PASS")

    ticket=approved(digest_member)
    assert ticket
    owner.execute("UPDATE m40650.sessions SET revoked_at=pg_catalog.clock_timestamp() "
                  "WHERE token_digest=%s",(digest_member,))
    assert consume(ticket,ta)["authorized"] is False
    assert approved(digest_member) is None
    print("M40700_SESSION_REVOCATION_AFTER_SIGNING_DENIED=PASS")

    # A signer or the shared verifier key is still a powerful trust anchor:
    # this proof does NOT claim to eliminate credential equivalents in SQL.
    assert approved(digest_other)
    print("M40700_SIGNER_KEY_COMPROMISE=NO_GO")
    print("M40700_SIGNATURE_DB_PARAMETER_LOGGING=NOT_REMEDIATED")
    print("M40700_HMAC_VERIFY_TIMING=NOT_ATTESTED")
    print("M40700_EXISTING_GUC_SPOOF=NOT_REMEDIATED")
    print("M40700_PRODUCTION_INTEGRATION=NOT_ACTIVATED")


def main() -> int:
    print("=== FR FINANCE M40700 — HMAC REQUEST BINDING DISPOSABLE ===")
    try:
        require_disposable_ci()
        import psycopg
        with psycopg.connect(os.environ["CI_M40700_DATABASE_URL"],
                             autocommit=True) as owner:
            proof(owner)
    except Exception as exc:
        import traceback
        frames = traceback.extract_tb(exc.__traceback__)
        if frames:
            last = frames[-1]
            print("M40700_FAILURE_SITE=" + last.name + ":" + str(last.lineno))
        if getattr(exc, "sqlstate", None):
            print("M40700_SQLSTATE=" + exc.sqlstate)
        print("M40700_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40700_ORIGINAL_PG_5433=NOT_ACCESSED")
        print("M40700_LOCAL_DB_WRITES=NONE")
        print("M40700_LOCAL_MIGRATIONS=NONE")
        print("M40700_SERVICE_RESTARTS=NONE")
        print("M40700_PIX_REAL=OFF")
        print("M40700_PAGAMENTOS_REAIS=OFF")
        print("M40700_ATIVACAO_REAL=OFF")
        print("M40700_PRODUCTION=BLOCKED")
    print("M40700_STATUS=PASS_SYNTHETIC_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
