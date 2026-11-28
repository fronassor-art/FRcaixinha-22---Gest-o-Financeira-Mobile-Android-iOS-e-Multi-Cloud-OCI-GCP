#!/usr/bin/env python3
"""M40720: synthetic Ed25519 client-bound proof, ONLY GitHub disposable PG18.

No real FastAPI route, no production migrations. Client key material never
crosses into SQL; the legacy synthetic HMAC issuer remains an acknowledged
database-owner/logging trust-boundary risk. Production always NO-GO.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlsplit
from uuid import UUID, uuid4
import base64
import os
import re
import secrets

DB = "fr_m40720_disposable_ci"
PORT = 55441
SCOPE = "READ_ENTRIES"
TOKEN_RE = re.compile(r"[A-Za-z0-9_-]{40,128}\Z")
B64_RE = re.compile(r"[A-Za-z0-9_-]{86}\Z")


def gate() -> None:
    for key,value in {
        "GITHUB_ACTIONS": "true",
        "CI_M40720_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }.items():
        if os.environ.get(key) != value:
            raise RuntimeError("M40720_DISPOSABLE_ONLY")
    try:
        u = urlsplit(os.environ.get("CI_M40720_DATABASE_URL", ""))
        if (u.scheme != "postgresql" or u.hostname != "127.0.0.1"
                or u.port != PORT or u.path != "/" + DB
                or u.username != "postgres" or not u.password
                or u.query or u.fragment):
            raise RuntimeError("M40720_WRONG_POSTGRES_IDENTITY")
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("M40720_WRONG_POSTGRES_IDENTITY") from exc


def message(digest: str, tenant: UUID, nonce: UUID, expiry: int) -> bytes:
    path = f"/m40720/tenants/{tenant}/entries"
    return (
        f"FRF-M40720|v1|GET|{path}|{digest}|{tenant}|{nonce}|{expiry}|{SCOPE}"
    ).encode("utf-8")


def encode_signature(private_key, digest, tenant, nonce, expiry):
    return base64.urlsafe_b64encode(
        private_key.sign(message(digest, tenant, nonce, expiry))
    ).decode("ascii").rstrip("=")


def make_app(auth_dsn, financial_dsn, public_keys, hmac_fixture_secret):
    import psycopg
    from cryptography.exceptions import InvalidSignature
    from fastapi import FastAPI, Header
    from fastapi.responses import JSONResponse
    from m40700_request_proof_disposable import sign as sql_sign

    app = FastAPI(title="M40720 entirely independent synthetic PoP gateway")

    @app.get("/m40720/tenants/{tenant_id}/entries")
    def read_entries(
        tenant_id: str,
        authorization: str | None = Header(default=None),
        x_fr_nonce: str | None = Header(default=None),
        x_fr_expires: str | None = Header(default=None),
        x_fr_pop: str | None = Header(default=None),
    ):
        def denied():
            return JSONResponse(
                status_code=401, content={"detail": "Unauthorized"},
                headers={"Cache-Control": "no-store"},
            )

        if not authorization or not authorization.startswith("Bearer "):
            return denied()
        raw = authorization[7:]
        if not TOKEN_RE.fullmatch(raw):
            return denied()
        digest = sha256(raw.encode("ascii")).hexdigest()
        try:
            tenant = UUID(tenant_id)
            if tenant.int == 0 or str(tenant) != tenant_id:
                return denied()
            nonce = UUID(x_fr_nonce or "")
            if nonce.int == 0 or str(nonce) != x_fr_nonce:
                return denied()
            if (not x_fr_expires or not x_fr_expires.isascii()
                    or not x_fr_expires.isdecimal()
                    or len(x_fr_expires) > 11):
                return denied()
            expiry = int(x_fr_expires)
            now = int(datetime.now(timezone.utc).timestamp())
            if expiry <= now or expiry > now + 20:
                return denied()
            if not x_fr_pop or not B64_RE.fullmatch(x_fr_pop):
                return denied()
            signature = base64.urlsafe_b64decode(x_fr_pop + "==")
            if len(signature) != 64 or (
                base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
                != x_fr_pop
            ):
                return denied()
            verifier = public_keys.get((digest, tenant))
            if verifier is None:
                return denied()
            verifier.verify(signature, message(digest, tenant, nonce, expiry))
        except (ValueError, TypeError, InvalidSignature, OverflowError):
            return denied()

        # Ed25519 signature and private key NEVER enter SQL. The trusted
        # synthetic HTTP verifier signs a distinct scoped SQL request, whose
        # HMAC key is unfortunately ALSO present in protected PG18 fixture.
        claim = sql_sign(hmac_fixture_secret, digest, tenant, nonce, expiry)
        try:
            with psycopg.connect(auth_dsn, autocommit=True) as auth:
                auth.execute("SET ROLE m40680_auth")
                ticket = auth.execute(
                    "SELECT m40700.issue_bound(%s,%s,%s,%s,%s,%s)",
                    (digest, tenant, nonce, expiry, SCOPE, claim),
                ).fetchone()[0]
            if not ticket:
                return denied()
            with psycopg.connect(financial_dsn, autocommit=True) as fin:
                fin.execute("SET ROLE m40650_app")
                payload = fin.execute(
                    "SELECT m40650.m40680_consume(%s,%s)",
                    (ticket, tenant),
                ).fetchone()[0]
        except psycopg.Error:
            return JSONResponse(
                status_code=503, content={"detail": "Unavailable"},
                headers={"Cache-Control": "no-store"},
            )
        if not payload.get("authorized"):
            return denied()
        return JSONResponse(
            status_code=200,
            content={"entries": payload["entries"]},
            headers={"Cache-Control": "no-store"},
        )

    return app


async def proof(owner) -> None:
    import asyncio
    import psycopg
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from httpx import ASGITransport, AsyncClient
    from psycopg.conninfo import make_conninfo
    from m40700_request_proof_disposable import bootstrap

    hmac_fixture_secret = secrets.token_bytes(32)
    bootstrap(owner, hmac_fixture_secret)
    ta, tb = uuid4(), uuid4()
    ua, ub = uuid4(), uuid4()
    ea, eb = uuid4(), uuid4()
    for user in (ua, ub):
        owner.execute("INSERT INTO m40650.users VALUES (%s,'ACTIVE',false)", (user,))
        owner.execute(
            "INSERT INTO m40650.memberships VALUES (%s,%s,'TENANT_MEMBER','ATIVA')",
            (user, ta),
        )
    owner.execute("INSERT INTO m40650.entries VALUES (%s,%s,%s,125)", (ea,ta,ua))
    owner.execute("INSERT INTO m40650.entries VALUES (%s,%s,%s,250)", (eb,ta,ub))
    token_a, token_b = secrets.token_urlsafe(40), secrets.token_urlsafe(40)
    digest_a, digest_b = (sha256(t.encode()).hexdigest() for t in (token_a,token_b))
    future = datetime.now(timezone.utc)+timedelta(hours=1)
    for user,digest in ((ua,digest_a),(ub,digest_b)):
        owner.execute(
            "INSERT INTO m40650.sessions VALUES "
            "(%s,%s,'TENANT_MEMBER',%s,%s,NULL)",
            (digest,user,ta,future),
        )

    client_private_a = Ed25519PrivateKey.generate()
    client_private_b = Ed25519PrivateKey.generate()
    public_registry = {
        (digest_a,ta): client_private_a.public_key(),
        (digest_b,ta): client_private_b.public_key(),
    }
    # No SQL statement stores either Ed25519 private or public bytes in the
    # proof fixture: in-memory registration is a synthetic-only shortcut.
    root = os.environ["CI_M40720_DATABASE_URL"]
    auth_dsn = make_conninfo(
        root,user="m40680_auth_login",
        password="m40680-fixture-auth-only-not-real",
    )
    financial_dsn = make_conninfo(
        root,user="m40650_ci_login",
        password="synthetic-only-m40650-ci-not-a-real-credential",
    )
    app=make_app(auth_dsn,financial_dsn,public_registry,hmac_fixture_secret)

    def headers(token,private,tenant=ta,*,nonce=None,expiry=None):
        nonce = nonce or uuid4()
        expiry = expiry if expiry is not None else (
            int(datetime.now(timezone.utc).timestamp())+15
        )
        digest = sha256(token.encode()).hexdigest()
        return {
            "Authorization":"Bearer "+token,
            "X-FR-Nonce":str(nonce),
            "X-FR-Expires":str(expiry),
            "X-FR-Pop":encode_signature(private,digest,tenant,nonce,expiry),
        }

    async with AsyncClient(transport=ASGITransport(app=app),base_url="http://ci") as http:
        async def get(tenant=ta, h=None):
            return await http.get(
                f"/m40720/tenants/{tenant}/entries", headers=h or {},
            )

        valid_a=headers(token_a,client_private_a)
        r=await get(h=valid_a)
        assert r.status_code==200 and r.headers["cache-control"]=="no-store"
        assert {e["id"] for e in r.json()["entries"]}=={str(ea)}
        assert token_a not in r.text
        valid_b=headers(token_b,client_private_b)
        assert {e["id"] for e in (await get(h=valid_b)).json()["entries"]}=={str(eb)}
        print("M40720_VALID_ED25519_CLIENT_BOUND_HTTP_TO_SQL=PASS")

        # Bare bearer/digest alone, forged client signature or swapped
        # request method, destination, nonce, and deadline cannot authorize.
        assert (await get(h={"Authorization":"Bearer "+token_a})).status_code==401
        assert (await get(h=headers(token_a,client_private_b))).status_code==401
        forged=headers(token_a,client_private_a)
        forged["X-FR-Nonce"]=str(uuid4())
        assert (await get(h=forged)).status_code==401
        forged=headers(token_a,client_private_a)
        forged["X-FR-Expires"]=str(int(forged["X-FR-Expires"])+1)
        assert (await get(h=forged)).status_code==401
        forged=headers(token_a,client_private_a)
        forged["X-FR-Pop"]="0"*86
        assert (await get(h=forged)).status_code==401
        assert (await get(tenant=tb,h=headers(token_a,client_private_a))).status_code==401
        assert (await get(h=headers(token_a,client_private_a,expiry=1))).status_code==401
        assert (await get(h=headers(token_a,client_private_a,expiry=(
            int(datetime.now(timezone.utc).timestamp())+120)))).status_code==401
        assert (await http.post(
            f"/m40720/tenants/{ta}/entries",
            headers=headers(token_a,client_private_a),
        )).status_code==405
        assert (await get(h={"Authorization":"Bearer "+token_a,
                             "X-Role":"TENANT_ADMIN",
                             "X-Tenant":str(tb)})).status_code==401
        print("M40720_BEARER_ONLY_TAMPERED_PROOF_AND_CROSS_TENANT_DENIED=PASS")

        # SQL role with a leaked digest still cannot call the legacy or
        # new bound SQL issuer without a separate trusted signer signature.
        with psycopg.connect(auth_dsn,autocommit=True) as auth:
            auth.execute("SET ROLE m40680_auth")
            assert not auth.execute(
                "SELECT pg_catalog.has_function_privilege("
                "'m40680_auth','m40650.m40680_issue(text,uuid)','EXECUTE')"
            ).fetchone()[0]
            assert auth.execute(
                "SELECT m40700.issue_bound(%s,%s,%s,%s,%s,%s)",
                (digest_a,ta,uuid4(),
                 int(datetime.now(timezone.utc).timestamp())+15,SCOPE,"0"*64),
            ).fetchone()[0] is None
        print("M40720_SQL_AUTH_ROLE_WITHOUT_SIGNER_CANNOT_MINT=PASS")

        # HTTP signed proof is a transferable credential before first use
        # if attacker captures both Bearer and valid signature headers.
        intercepted=headers(token_a,client_private_a)
        attacker=await get(h=intercepted)
        assert attacker.status_code==200
        legitimate=await get(h=intercepted)
        assert legitimate.status_code==401
        print("M40720_STOLEN_BEARER_PLUS_PREUSE_POP_PROOF=CONFIRMED_NO_GO")

        # Distinct nonces: a flood of identical signed requests gets exactly
        # one authorized response. Not an authenticated client connection.
        race_headers=headers(token_a,client_private_a)
        responses=await asyncio.gather(*[get(h=race_headers) for _ in range(6)])
        assert sum(x.status_code==200 for x in responses)==1
        assert sum(x.status_code==401 for x in responses)==5
        print("M40720_CONCURRENT_SIGNED_REQUEST_ONE_TIME=PASS")

        revoked=headers(token_b,client_private_b)
        owner.execute(
            "UPDATE m40650.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",(digest_b,),
        )
        assert (await get(h=revoked)).status_code==401
        assert (await get(h=headers(token_b,client_private_b))).status_code==401
        print("M40720_REVOKED_SESSION_WITH_VALID_POP_DENIED=PASS")

    # HMAC key remains accessible to privileged PG owner in this fixture,
    # while the Ed25519 client private key is not a DB parameter/record.
    extracted=owner.execute(
        "SELECT key FROM m40700.verifier_secret WHERE singleton=true"
    ).fetchone()[0]
    assert bytes(extracted)==hmac_fixture_secret
    print("M40720_ED25519_PRIVATE_KEY_SENT_TO_SQL=NONE")
    print("M40720_SQL_HMAC_KEY_EXTRACTABLE_BY_DB_OWNER=CONFIRMED_NO_GO")
    print("M40720_IN_MEMORY_PUBLIC_KEY_REGISTRY=NOT_PRODUCTION")
    print("M40720_REQUEST_CAPTURE_REPLAY_BEFORE_USE=NOT_REMEDIATED")
    print("M40720_REAL_FASTAPI_AND_PROD_ROUTES=NOT_MODIFIED")
    print("M40720_EXISTING_GUC_SPOOF=NOT_REMEDIATED")


def main():
    print("=== FR FINANCE M40720 — CLIENT ED25519 PROOF (SYNTHETIC) ===")
    try:
        gate()
        import asyncio
        import psycopg
        with psycopg.connect(
            os.environ["CI_M40720_DATABASE_URL"],autocommit=True,
        ) as owner:
            asyncio.run(proof(owner))
    except Exception as exc:
        import traceback
        frames=traceback.extract_tb(exc.__traceback__)
        if frames:
            last=frames[-1]
            print("M40720_FAILURE_SITE="+last.name+":"+str(last.lineno))
        if getattr(exc,"sqlstate",None):
            print("M40720_SQLSTATE="+exc.sqlstate)
        print("M40720_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40720_ORIGINAL_PG_5433=NOT_ACCESSED")
        print("M40720_LOCAL_DB_WRITES=NONE")
        print("M40720_MIGRATIONS=NONE")
        print("M40720_SERVICE_RESTARTS=NONE")
        print("M40720_PIX_REAL=OFF")
        print("M40720_PAGAMENTOS_REAIS=OFF")
        print("M40720_ATIVACAO_REAL=OFF")
        print("M40720_PRODUCTION=BLOCKED")
    print("M40720_STATUS=PASS_SYNTHETIC_ONLY_NO_GO_PRODUCTION")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
