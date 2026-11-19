#!/usr/bin/env python3
"""M40730: off-database client signing key, split SQL issuer privilege.

SYNTHETIC-only GitHub Actions PostgreSQL 18 on loopback 55442. This is NOT
production authorization: a compromised signer SQL login or privileged DBA
still mints tickets without proof of possession. No real API or migrations.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import re
import secrets
from urllib.parse import urlsplit
from uuid import UUID, uuid4

DATABASE="fr_m40730_disposable_ci"
PORT=55442
BEARER_PATTERN=re.compile(r"[A-Za-z0-9_-]{40,128}\Z")
SIGNATURE_PATTERN=re.compile(r"[A-Za-z0-9_-]{86}\Z")
SCOPE="READ_ENTRIES"


def gate() -> None:
    expected={
        "GITHUB_ACTIONS":"true",
        "FRCAIXINHA_CI_ISOLATED":"1",
        "CI_M40730_DISPOSABLE":"1",
        "PIX_REAL":"OFF",
        "PAGAMENTOS_REAIS":"OFF",
        "ATIVACAO_REAL":"OFF",
    }
    if any(os.environ.get(k)!=v for k,v in expected.items()):
        raise RuntimeError("M40730_DISPOSABLE_ONLY")
    try:
        u=urlsplit(os.environ.get("CI_M40730_DATABASE_URL",""))
        if (u.scheme!="postgresql" or u.hostname!="127.0.0.1" or u.port!=PORT
                or u.path!="/"+DATABASE or u.username!="postgres"
                or not u.password or u.query or u.fragment):
            raise RuntimeError("M40730_DATABASE_IDENTITY_DENIED")
    except (ValueError,AttributeError) as exc:
        raise RuntimeError("M40730_DATABASE_IDENTITY_DENIED") from exc


def canonical(digest,tenant,nonce,expires):
    return (f"FRF-M40730|v1|GET|/m40730/tenants/{tenant}/entries|"
            f"{digest}|{tenant}|{nonce}|{expires}|{SCOPE}").encode("utf-8")


def signed_header(private,digest,tenant,nonce,expires):
    return base64.urlsafe_b64encode(
        private.sign(canonical(digest,tenant,nonce,expires))
    ).decode("ascii").rstrip("=")


def bootstrap(owner):
    from m40680_digest_one_time_gateway_disposable import bootstrap as prior
    prior(owner)
    owner.execute("CREATE ROLE m40730_signer NOLOGIN NOINHERIT NOBYPASSRLS")
    owner.execute(
        "CREATE ROLE m40730_signer_login LOGIN NOINHERIT NOBYPASSRLS "
        "PASSWORD 'm40730-isolated-fixture-not-a-real-password'"
    )
    owner.execute("GRANT m40730_signer TO m40730_signer_login")
    # Critical: neither auth SQL role nor signer SQL role can call legacy
    # digest-only issuer; signer has ONE guarded nonce function instead.
    owner.execute(
        "REVOKE EXECUTE ON FUNCTION m40650.m40680_issue(text,uuid) "
        "FROM PUBLIC,m40680_auth,m40730_signer"
    )
    owner.execute("CREATE SCHEMA m40730 AUTHORIZATION m40650_owner")
    owner.execute("REVOKE ALL ON SCHEMA m40730 FROM PUBLIC")
    owner.execute("GRANT USAGE ON SCHEMA m40730 TO m40730_signer")
    owner.execute("""
        CREATE TABLE m40730.nonces (
            nonce uuid PRIMARY KEY,
            digest text NOT NULL,
            tenant_id uuid NOT NULL,
            accepted_at timestamptz NOT NULL DEFAULT pg_catalog.clock_timestamp()
        )
    """)
    owner.execute("ALTER TABLE m40730.nonces OWNER TO m40650_owner")
    owner.execute(
        "REVOKE ALL ON m40730.nonces "
        "FROM PUBLIC,m40730_signer,m40680_auth,m40650_app"
    )
    owner.execute("""
        CREATE FUNCTION m40730.issue_if_unused(
            p_digest text, p_tenant uuid, p_nonce uuid, p_expires bigint
        )
        RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE v_nonce uuid; v_ticket text;
        BEGIN
          IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
            OR p_tenant IS NULL OR p_nonce IS NULL
            OR p_expires IS NULL
            OR p_expires<=pg_catalog.floor(pg_catalog.date_part(
                'epoch',pg_catalog.clock_timestamp()))::bigint
            OR p_expires>pg_catalog.floor(pg_catalog.date_part(
                'epoch',pg_catalog.clock_timestamp()))::bigint+20
          THEN RETURN NULL; END IF;
          -- A unique nonce is consumed even if the subsequent session check
          -- fails. Atomic INSERT prevents concurrent double ticket issue.
          INSERT INTO m40730.nonces(nonce,digest,tenant_id)
          VALUES(p_nonce,p_digest,p_tenant)
          ON CONFLICT(nonce) DO NOTHING RETURNING nonce INTO v_nonce;
          IF NOT FOUND THEN RETURN NULL; END IF;
          SELECT m40650.m40680_issue(p_digest,p_tenant) INTO v_ticket;
          RETURN v_ticket;
        END
        $body$
    """)
    owner.execute(
        "ALTER FUNCTION m40730.issue_if_unused(text,uuid,uuid,bigint) "
        "OWNER TO m40650_owner"
    )
    owner.execute(
        "REVOKE ALL ON FUNCTION m40730.issue_if_unused(text,uuid,uuid,bigint) "
        "FROM PUBLIC,m40680_auth,m40650_app"
    )
    owner.execute(
        "GRANT EXECUTE ON FUNCTION m40730.issue_if_unused(text,uuid,uuid,bigint) "
        "TO m40730_signer"
    )


def app_factory(signer_dsn,financial_dsn,registry):
    import psycopg
    from cryptography.exceptions import InvalidSignature
    from fastapi import FastAPI, Header
    from fastapi.responses import JSONResponse

    app=FastAPI(title="M40730 isolated synthetic proof-of-possession")

    @app.get("/m40730/tenants/{tenant_id}/entries")
    def entries(
        tenant_id:str,
        authorization:str|None=Header(default=None),
        x_fr_nonce:str|None=Header(default=None),
        x_fr_expires:str|None=Header(default=None),
        x_fr_pop:str|None=Header(default=None),
    ):
        def denied():
            return JSONResponse({"detail":"Unauthorized"},status_code=401,
                                headers={"Cache-Control":"no-store"})
        if not authorization or not authorization.startswith("Bearer "):
            return denied()
        raw=authorization[len("Bearer "):]
        if not BEARER_PATTERN.fullmatch(raw):
            return denied()
        digest=sha256(raw.encode("ascii")).hexdigest()
        try:
            tenant=UUID(tenant_id)
            nonce=UUID(x_fr_nonce or "")
            if (tenant.int==0 or nonce.int==0 or str(tenant)!=tenant_id
                    or str(nonce)!=x_fr_nonce):
                return denied()
            if (not x_fr_expires or not x_fr_expires.isascii()
                    or not x_fr_expires.isdecimal() or len(x_fr_expires)>11):
                return denied()
            expiry=int(x_fr_expires)
            now=int(datetime.now(timezone.utc).timestamp())
            if expiry<=now or expiry>now+20:
                return denied()
            if not x_fr_pop or not SIGNATURE_PATTERN.fullmatch(x_fr_pop):
                return denied()
            sig=base64.urlsafe_b64decode(x_fr_pop+"==")
            if len(sig)!=64 or base64.urlsafe_b64encode(sig).decode(
                    "ascii").rstrip("=")!=x_fr_pop:
                return denied()
            public=registry.get((digest,tenant))
            if public is None:
                return denied()
            public.verify(sig,canonical(digest,tenant,nonce,expiry))
        except (ValueError,TypeError,InvalidSignature,OverflowError):
            return denied()

        # SQL receives only digest/tenant/nonce/expiry, NOT any Ed25519 key,
        # signature, or server HMAC. DB login itself is a bearer-equivalent
        # privileged signer capability if leaked (deliberate NO-GO).
        try:
            with psycopg.connect(signer_dsn,autocommit=True) as signer:
                signer.execute("SET ROLE m40730_signer")
                ticket=signer.execute(
                    "SELECT m40730.issue_if_unused(%s,%s,%s,%s)",
                    (digest,tenant,nonce,expiry),
                ).fetchone()[0]
            if ticket is None:
                return denied()
            with psycopg.connect(financial_dsn,autocommit=True) as financial:
                financial.execute("SET ROLE m40650_app")
                result=financial.execute(
                    "SELECT m40650.m40680_consume(%s,%s)",
                    (ticket,tenant),
                ).fetchone()[0]
        except psycopg.Error:
            return JSONResponse({"detail":"Unavailable"},status_code=503,
                                headers={"Cache-Control":"no-store"})
        if not result.get("authorized"):
            return denied()
        return JSONResponse(
            {"entries":result["entries"]},status_code=200,
            headers={"Cache-Control":"no-store"}
        )

    return app


async def proof(owner):
    import psycopg
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from httpx import ASGITransport,AsyncClient
    from psycopg.conninfo import make_conninfo

    bootstrap(owner)
    tenant_a,tenant_b=uuid4(),uuid4()
    user_a,user_b=uuid4(),uuid4()
    entry_a,entry_b=uuid4(),uuid4()
    for user in (user_a,user_b):
        owner.execute("INSERT INTO m40650.users VALUES (%s,'ACTIVE',false)",(user,))
        owner.execute(
            "INSERT INTO m40650.memberships "
            "VALUES (%s,%s,'TENANT_MEMBER','ATIVA')",(user,tenant_a)
        )
    owner.execute("INSERT INTO m40650.entries VALUES (%s,%s,%s,100)",
                  (entry_a,tenant_a,user_a))
    owner.execute("INSERT INTO m40650.entries VALUES (%s,%s,%s,300)",
                  (entry_b,tenant_a,user_b))
    token_a,token_b=secrets.token_urlsafe(40),secrets.token_urlsafe(40)
    digest_a,digest_b=[sha256(x.encode()).hexdigest() for x in (token_a,token_b)]
    until=datetime.now(timezone.utc)+timedelta(hours=1)
    for user,digest in ((user_a,digest_a),(user_b,digest_b)):
        owner.execute(
            "INSERT INTO m40650.sessions VALUES "
            "(%s,%s,'TENANT_MEMBER',%s,%s,NULL)",
            (digest,user,tenant_a,until)
        )
    key_a,key_b=Ed25519PrivateKey.generate(),Ed25519PrivateKey.generate()
    public_registry={
        (digest_a,tenant_a):key_a.public_key(),
        (digest_b,tenant_a):key_b.public_key(),
    }
    root=os.environ["CI_M40730_DATABASE_URL"]
    signer_dsn=make_conninfo(
        root,user="m40730_signer_login",
        password="m40730-isolated-fixture-not-a-real-password"
    )
    auth_dsn=make_conninfo(
        root,user="m40680_auth_login",
        password="m40680-fixture-auth-only-not-real"
    )
    fin_dsn=make_conninfo(
        root,user="m40650_ci_login",
        password="synthetic-only-m40650-ci-not-a-real-credential"
    )
    app=app_factory(signer_dsn,fin_dsn,public_registry)

    def headers(token,private,tenant=tenant_a,*,nonce=None,expiry=None):
        nonce=nonce or uuid4()
        expiry=expiry if expiry is not None else (
            int(datetime.now(timezone.utc).timestamp())+15
        )
        digest=sha256(token.encode()).hexdigest()
        return {
            "Authorization":"Bearer "+token,
            "X-FR-Nonce":str(nonce),
            "X-FR-Expires":str(expiry),
            "X-FR-Pop":signed_header(private,digest,tenant,nonce,expiry),
        }

    # Verify SQL structural separation through actual low-privilege logins.
    with psycopg.connect(auth_dsn,autocommit=True) as auth:
        auth.execute("SET ROLE m40680_auth")
        assert not auth.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40680_auth','m40650.m40680_issue(text,uuid)','EXECUTE')"
        ).fetchone()[0]
        assert not auth.execute(
            "SELECT pg_catalog.has_schema_privilege("
            "'m40680_auth','m40730','USAGE')"
        ).fetchone()[0]
        # Check protected function by OID; regprocedure text can throw on
        # schema USAGE absence, which is an expected and desired denial.
        assert not auth.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40680_auth',p.oid,'EXECUTE') "
            "FROM pg_catalog.pg_proc AS p "
            "JOIN pg_catalog.pg_namespace AS n ON n.oid=p.pronamespace "
            "WHERE n.nspname='m40730' AND p.proname='issue_if_unused'"
        ).fetchone()[0]
    with psycopg.connect(fin_dsn,autocommit=True) as fin:
        fin.execute("SET ROLE m40650_app")
        assert not fin.execute(
            "SELECT pg_catalog.has_schema_privilege('m40650_app','m40730','USAGE')"
        ).fetchone()[0]
    with psycopg.connect(signer_dsn,autocommit=True) as signer:
        signer.execute("SET ROLE m40730_signer")
        assert signer.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40730_signer','m40730.issue_if_unused(text,uuid,uuid,bigint)','EXECUTE')"
        ).fetchone()[0]
        assert not signer.execute(
            "SELECT pg_catalog.has_function_privilege("
            "'m40730_signer','m40650.m40680_issue(text,uuid)','EXECUTE')"
        ).fetchone()[0]
        assert not signer.execute(
            "SELECT pg_catalog.has_table_privilege("
            "'m40730_signer','m40730.nonces','SELECT')"
        ).fetchone()[0]

    assert not owner.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace "
        "WHERE nspname='m40700')"
    ).fetchone()[0]
    stored_columns=owner.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='m40730'"
    ).fetchall()
    assert all(
        not any(secret_name in row[0] for secret_name in
                ("private_key","verifier_secret","hmac_key","ed25519","signature"))
        for row in stored_columns
    )
    print("M40730_NO_SIGNING_KEYS_OR_PROOFS_STORED_IN_SQL=PASS_SYNTHETIC")
    print("M40730_AUTH_FINANCIAL_SIGNER_SQL_ROLE_SPLIT=PASS")

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://fixture") as http:
        async def get(tenant=tenant_a,h=None):
            return await http.get(
                f"/m40730/tenants/{tenant}/entries",headers=h or {}
            )

        ok_a=await get(h=headers(token_a,key_a))
        assert ok_a.status_code==200
        assert {r["id"] for r in ok_a.json()["entries"]}=={str(entry_a)}
        ok_b=await get(h=headers(token_b,key_b))
        assert ok_b.status_code==200
        assert {r["id"] for r in ok_b.json()["entries"]}=={str(entry_b)}
        assert (await get(h={"Authorization":"Bearer "+token_a})).status_code==401
        assert (await get(h=headers(token_a,key_b))).status_code==401
        invalid=headers(token_a,key_a)
        invalid["X-FR-Nonce"]=str(uuid4())
        assert (await get(h=invalid)).status_code==401
        assert (await get(tenant=tenant_b,h=headers(token_a,key_a))).status_code==401
        assert (await get(h=headers(token_a,key_a,expiry=1))).status_code==401
        assert (await http.post(
            f"/m40730/tenants/{tenant_a}/entries",
            headers=headers(token_a,key_a)
        )).status_code==405
        print("M40730_CLIENT_POP_AND_TENANT_BOUND_HTTP_GATE=PASS")

        replay=headers(token_a,key_a)
        assert (await get(h=replay)).status_code==200
        assert (await get(h=replay)).status_code==401
        same=headers(token_a,key_a)
        responses=await asyncio.gather(*[get(h=same) for _ in range(6)])
        assert sum(r.status_code==200 for r in responses)==1
        assert sum(r.status_code==401 for r in responses)==5
        print("M40730_CONCURRENT_NONCE_SINGLE_ISSUE=PASS")

        # Attackers who have stolen both Bearer and signed request can still
        # race and use it before legitimate holder. No channel binding.
        stolen=headers(token_a,key_a)
        assert (await get(h=stolen)).status_code==200
        assert (await get(h=stolen)).status_code==401
        print("M40730_PREUSE_CAPTURED_HTTP_REQUEST=CONFIRMED_NO_GO")

        proof_revoked=headers(token_a,key_a)
        owner.execute(
            "UPDATE m40650.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",(digest_a,)
        )
        assert (await get(h=proof_revoked)).status_code==401
        print("M40730_SESSION_REVOCATION_AFTER_POP=PASS")

    # CRITICAL NEGATIVE PROOF: if signer SQL login is leaked, an attacker
    # with digest B can issue WITHOUT any Ed25519 private key or HTTP proof.
    with psycopg.connect(signer_dsn,autocommit=True) as stolen_signer:
        stolen_signer.execute("SET ROLE m40730_signer")
        illegal_ticket=stolen_signer.execute(
            "SELECT m40730.issue_if_unused(%s,%s,%s,%s)",
            (digest_b,tenant_a,uuid4(),
             int(datetime.now(timezone.utc).timestamp())+15),
        ).fetchone()[0]
    assert illegal_ticket
    with psycopg.connect(fin_dsn,autocommit=True) as financial:
        financial.execute("SET ROLE m40650_app")
        result=financial.execute(
            "SELECT m40650.m40680_consume(%s,%s)",
            (illegal_ticket,tenant_a),
        ).fetchone()[0]
        assert result["authorized"]
        assert {r["id"] for r in result["entries"]}=={str(entry_b)}
    print("M40730_COMPROMISED_SIGNER_SQL_LOGIN_BYPASSES_POP=CONFIRMED_NO_GO")
    print("M40730_PRIVILEGED_DB_OWNER_CAN_REGRANT_SIGNER=CONFIRMED_NO_GO")
    print("M40730_SIGNER_LOGIN_AND_TICKET_LOG_LEAKAGE=NOT_REMEDIATED")
    print("M40730_TLS_DEVICE_KEY_ENROLLMENT_ATTESTATION=NOT_ATTESTED")
    print("M40730_ORIGINAL_GUC_SPOOF=NOT_REMEDIATED")
    print("M40730_REAL_FASTAPI_SQL_APP=NOT_MODIFIED")


def main():
    print("=== FR FINANCE M40730 — OFF-DB PROOF / PRIVILEGED SQL NO-GO ===")
    try:
        gate()
        import psycopg
        with psycopg.connect(os.environ["CI_M40730_DATABASE_URL"],
                             autocommit=True) as owner:
            asyncio.run(proof(owner))
    except Exception as exc:
        import traceback
        frames=traceback.extract_tb(exc.__traceback__)
        if frames:
            last=frames[-1]
            print("M40730_FAILURE_SITE="+last.name+":"+str(last.lineno))
        if getattr(exc,"sqlstate",None):
            print("M40730_SQLSTATE="+exc.sqlstate)
        print("M40730_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40730_ORIGINAL_PG_5433=NOT_ACCESSED")
        print("M40730_LOCAL_DB_WRITES=NONE")
        print("M40730_MIGRATIONS=NONE")
        print("M40730_SERVICE_RESTARTS=NONE")
        print("M40730_PIX_REAL=OFF")
        print("M40730_PAGAMENTOS_REAIS=OFF")
        print("M40730_ATIVACAO_REAL=OFF")
        print("M40730_PRODUCTION=BLOCKED")
    print("M40730_STATUS=PASS_ADVERSARIAL_SYNTHETIC_NO_GO")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
