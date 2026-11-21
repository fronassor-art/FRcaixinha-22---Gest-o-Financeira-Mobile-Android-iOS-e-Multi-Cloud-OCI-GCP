#!/usr/bin/env python3
"""M37463: CI disposable token-bound SaaS contract readback BEFORE/AFTER revoke.

Uses real (test-only) get_current_session and a read-only SELECT join. The
offer, challenge and identity records are synthetic. No legal consent,
payment, license, production authentication, or local DB access.
"""
from __future__ import annotations

import asyncio
from datetime import datetime,timezone
import os
import sys
from uuid import UUID

from fastapi import HTTPException
from starlette.requests import Request

from app.dependencies import get_current_session
from app.security import hash_token
from app.saas_token_scoped_offer_readback_ci import (
    TOKEN_SCOPE_SQL,token_scope_params,build_token_scoped_ci_context,
)

EXPECTED_ENV={
    "GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1","PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging","PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_token_ci=1",
}
CI_AUTH_DSN=(
    "postgresql://frcaixinha_auth_token_ci:ci-test-only"
    "@127.0.0.1:5432/frcaixinha_staging"
)
S1=UUID("daba0000-0000-4000-8000-000000000581")
S2=UUID("daba0000-0000-4000-8000-000000000588")
A=UUID("daba0000-0000-4000-8000-000000000001")
T=UUID("daba0000-0000-4000-8000-000000000010")
REQUEST=UUID("daba0000-0000-4000-8000-000000000594")
TOKEN1="m37462-ci-only-first-bearer-NEVER-REAL-01"
TOKEN2="m37462-ci-only-rotated-bearer-NEVER-REAL-02"


def environment_allowed(environ:dict[str,str],mode:str)->bool:
    return (mode in ("before-revoke","after-revoke")
        and all(environ.get(k)==v for k,v in EXPECTED_ENV.items())
        and environ.get("FR_FINANCE_SAAS_REAL","OFF")=="OFF"
        and environ.get("FR_FINANCE_PIX_REAL","OFF")=="OFF")


def bearer_request(token:str)->Request:
    return Request({
        "type":"http","method":"POST","path":"/ci/m37463/scope",
        "headers":[(b"authorization",("Bearer "+token).encode("ascii"))],
        "query_string":b"",
    })


async def authenticated(token:str):
    return await get_current_session(bearer_request(token))


def make_connection():
    import psycopg
    from psycopg.rows import dict_row
    return psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user="postgres",password="ci-test-only",connect_timeout=5,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    )


def read_scope(cur,params)->list[dict]:
    cur.execute(TOKEN_SCOPE_SQL,params)
    return [dict(x) for x in cur.fetchall()]


def check_connection(cur)->None:
    cur.execute(
        "SELECT current_database() AS db,session_user AS actor,"
        "current_setting('transaction_read_only') AS ro,"
        "current_setting('is_superuser') AS root,inet_server_port() AS port")
    identity=cur.fetchone()
    if (identity is None or identity["db"]!="frcaixinha_staging"
        or identity["actor"]!="postgres" or identity["ro"]!="on"
        or identity["root"]!="on" or identity["port"]!=5432):
        raise AssertionError("M37463_WRONG_DATABASE_OR_READONLY_POLICY")


async def run_before()->int:
    # This is the genuine backend dependency with a synthetic bearer token
    # whose SHA-256 is persisted in the isolated public.sessions fixture.
    session=await authenticated(TOKEN1)
    now=datetime.now(timezone.utc)
    params=token_scope_params(session,REQUEST,hash_token(TOKEN1),now=now)
    if params is None or params[:4]!=(S1,A,T,REQUEST):
        raise AssertionError("M37463_VERIFIED_SESSION_PARAMS_INVALID")
    # DB readback MUST occur after the token verification and against
    # canonical public.sessions inside the SELECT, not f.session_active alone.
    with make_connection() as conn:
        with conn.cursor() as cur:
            check_connection(cur)
            rows=read_scope(cur,params)
            if len(rows)!=1:
                raise AssertionError("M37463_TOKEN_SCOPED_CONTRACT_NOT_UNIQUE")
            state,ctx=build_token_scoped_ci_context(
                rows[0],session,REQUEST,hash_token(TOKEN1),
                now=datetime.now(timezone.utc),
            )
            if state!="CI_TOKEN_HASH_SESSION_CONTRACT_READBACK_ONLY" or ctx is None:
                raise AssertionError("M37463_TOKEN_SCOPED_CONTEXT_DENIED_"+state)
            if (ctx.offer.price_cents<=0 or ctx.offer.document_sha256==""
                or ctx.session_id!=S1 or ctx.administrator_id!=A
                or ctx.tenant_id!=T):
                raise AssertionError("M37463_OFFER_CONTRACT_SCOPE_INVALID")
            # The wrong token digest is denied even with correct IDs.
            bad_cases=[
                (S1,A,T,REQUEST,hash_token(TOKEN2)),
                (S2,A,T,REQUEST,hash_token(TOKEN2)),
                (S1,A,T,REQUEST,"0"*64),
                (S1,A,T,UUID("daba0000-0000-4000-8000-000000000050"),hash_token(TOKEN1)),
                (S1,UUID("daba0000-0000-4000-8000-000000000002"),T,REQUEST,hash_token(TOKEN1)),
                (S1,A,UUID("daba0000-0000-4000-8000-000000000020"),REQUEST,hash_token(TOKEN1)),
            ]
            for params_bad in bad_cases:
                if read_scope(cur,params_bad):
                    raise AssertionError("M37463_FOREIGN_TOKEN_OR_TENANT_SCOPED_READ_LEAK")
    print("M37463_TOKEN_SESSION_TENANT_OFFER_SINGLE_READBACK=PASS")
    print("M37463_FOREIGN_TOKEN_REQUEST_AND_TENANT=DENIED")
    print("M37463_DOCUMENT_VERSION_AND_PRICE=CI_DATABASE_READBACK")
    print("M37463_POSTGRESQL_SCOPE_TRANSACTION=READ_ONLY")
    return 0


async def run_after()->int:
    # M37462 must have revoked S1 using the token-bound SQL function.
    # A stale Python principal would no longer be sufficient: the live
    # SELECT joins public.sessions and detects s.revoked_at IS NULL.
    try:
        await authenticated(TOKEN1)
    except HTTPException as exc:
        if exc.status_code!=401:
            raise AssertionError("M37463_REVOKED_BEARER_WRONG_STATUS")
    else:
        raise AssertionError("M37463_REVOKED_BEARER_AUTHENTICATED")
    with make_connection() as conn:
        with conn.cursor() as cur:
            check_connection(cur)
            if read_scope(cur,(S1,A,T,REQUEST,hash_token(TOKEN1))):
                raise AssertionError("M37463_REVOKED_SESSION_READBACK_ALLOWED")
            # A different still-active session of the same administrator
            # cannot adopt the old session's challenge/request.
            second=await authenticated(TOKEN2)
            params=token_scope_params(
                second,REQUEST,hash_token(TOKEN2),
                now=datetime.now(timezone.utc),
            )
            if params is None or params[0]!=S2 or read_scope(cur,params):
                raise AssertionError("M37463_ROTATED_TOKEN_REUSED_OLD_CHALLENGE")
    print("M37463_REVOKED_BEARER_CANNOT_READ_CONTRACT=PASS")
    print("M37463_OTHER_ACTIVE_SESSION_CANNOT_ADOPT_CHALLENGE=PASS")
    print("M37463_REAL_USER_AUTH_OR_LEGAL_CONSENT=NOT_ATTESTED")
    print("M37463_REAL_SAAS_PAYMENT_LICENSE_PIX_ACTIVATION=OFF")
    print("M37463_ORIGINAL_TERMUX_DATABASE=UNTOUCHED")
    return 0


def main()->int:
    mode=sys.argv[1] if len(sys.argv)==2 else ""
    if not environment_allowed(dict(os.environ),mode):
        print("M37463_BLOCKED=DISPOSABLE_GITHUB_CI_ONLY")
        return 1
    os.environ["FRCAIXINHA_TEST_AUTH"]="1"
    os.environ["ENVIRONMENT"]="ci"
    os.environ["AUTH_DATABASE_URL"]=CI_AUTH_DSN
    if mode=="before-revoke":
        return asyncio.run(run_before())
    return asyncio.run(run_after())


if __name__=="__main__":
    raise SystemExit(main())
