#!/usr/bin/env python3
"""M37462: token -> real PostgreSQL sessions.id in disposable GitHub CI.

True token-hash lookup/refresh and revocation within a *synthetic CI DB*;
not a real person's credential, legal consent, OCI deployment or a license.
No production payments/activation. All fixture tokens are public test text.
"""
from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID
import os

from fastapi import HTTPException
from starlette.requests import Request
from app.dependencies import get_current_session
from app.routers.saas_authenticated_contract_ci import check_server_identity_binding
from app.saas_server_context_readback_ci import READBACK_SQL,build_ci_trusted_context


CI_ENV={
    "GITHUB_ACTIONS":"true","FRCAIXINHA_CI_ISOLATED":"1",
    "PGHOST":"127.0.0.1","PGPORT":"5432",
    "PGDATABASE":"frcaixinha_staging","PGUSER":"postgres",
    "PGPASSWORD":"ci-test-only",
    "PGOPTIONS":"-c frcaixinha.saas_token_ci=1",
}
TOKEN1="m37462-ci-only-first-bearer-NEVER-REAL-01"
TOKEN2="m37462-ci-only-rotated-bearer-NEVER-REAL-02"
TOKEN3="m37462-ci-only-foreign-bearer-NEVER-REAL-03"
TOKEN4="m37462-ci-only-expired-bearer-NEVER-REAL-04"
S1=UUID("daba0000-0000-4000-8000-000000000581")
S2=UUID("daba0000-0000-4000-8000-000000000588")
S3=UUID("daba0000-0000-4000-8000-000000000589")
T=UUID("daba0000-0000-4000-8000-000000000010")
A=UUID("daba0000-0000-4000-8000-000000000001")
OTHER_T=UUID("daba0000-0000-4000-8000-000000000020")
OTHER_A=UUID("daba0000-0000-4000-8000-000000000002")
REQUEST=UUID("daba0000-0000-4000-8000-000000000594")
CI_DSN=(
    "postgresql://frcaixinha_auth_token_ci:ci-test-only"
    "@127.0.0.1:5432/frcaixinha_staging"
)


def environment_allowed(env:dict[str,str])->bool:
    return all(env.get(k)==v for k,v in CI_ENV.items())


def request_from_bearer(raw: str,*,forge_role: str|None=None)->Request:
    headers=[(b"authorization",("Bearer "+raw).encode("ascii"))]
    if forge_role:
        headers.append((b"x-fr-finance-role",forge_role.encode("ascii")))
    return Request({
        "type":"http","method":"POST",
        "path":"/api/v1/saas/ci-contract/transition",
        "headers":headers,"query_string":b"",
    })


def expect(result,want,label):
    if result!=want:
        raise AssertionError(f"M37462_{label}: unexpected result")


async def auth(raw:str,*,forge_role:str|None=None):
    return await get_current_session(request_from_bearer(raw,forge_role=forge_role))


async def denied_401(raw:str)->None:
    try:
        await auth(raw)
    except HTTPException as exc:
        expect(exc.status_code,401,"AUTH_MUST_DENY")
    else:
        raise AssertionError("M37462_UNAUTHENTICATED_BEARER_ACCEPTED")


async def check_real_token_lookup(*,context):
    s=await auth(TOKEN1,forge_role="MASTER")
    expect(s.user_id,str(A),"USER")
    expect(s.tenant_id,str(T),"TENANT")
    expect(s.role,"TENANT_ADMIN","DB_ROLE_NOT_HEADER")
    expect(s.verified_session_id,str(S1),"SESSION_ID_FROM_TOKEN_HASH_DB")
    expect(s.verification_source,"POSTGRES_TOKEN_HASH_REFRESH","REFRESH_SOURCE")
    if (s.verified_session_at is None
        or s.verified_session_expires_at is None
        or s.verified_session_expires_at<=s.verified_session_at
        or s.verified_session_expires_at<=datetime.now(timezone.utc)):
        raise AssertionError("M37462_SESSION_NOT_VERIFIED_OR_RENEWED")
    for value in (TOKEN1,TOKEN2,TOKEN3,TOKEN4):
        if value in repr(s.__dict__):
            raise AssertionError("M37462_RAW_BEARER_LEAKED_FROM_PRINCIPAL")
    # Limit synthetic context expiry to actual refreshed bearer expiry.
    # This is a CI-only comparison; the M37458 fixture itself was created
    # without binding to an operational user login.
    bounded=replace(
        context,session_expires_at=min(
            context.session_expires_at,s.verified_session_expires_at),
    )
    principal=check_server_identity_binding(
        s,bounded,now=datetime.now(timezone.utc))
    if principal is None or principal.session_id!=S1:
        raise AssertionError("M37462_VALID_TOKEN_SESSION_CONTEXT_NOT_BOUND")

    foreign=await auth(TOKEN3)
    expect(foreign.verified_session_id,str(S3),"FOREIGN_SESSION_ID")
    expect(foreign.tenant_id,str(OTHER_T),"FOREIGN_TENANT")
    expect(foreign.user_id,str(OTHER_A),"FOREIGN_ADMIN")
    if check_server_identity_binding(foreign,bounded,now=datetime.now(timezone.utc)):
        raise AssertionError("M37462_FOREIGN_ADMIN_CONTEXT_ACCEPTED")

    rotated=await auth(TOKEN2)
    expect(rotated.verified_session_id,str(S2),"ROTATED_ID")
    if check_server_identity_binding(rotated,bounded,now=datetime.now(timezone.utc)):
        raise AssertionError("M37462_DIFFERENT_TOKEN_SAME_ADMIN_CONTEXT_ACCEPTED")

    await denied_401(TOKEN4)  # expired in PostgreSQL
    await denied_401("ci-not-a-token-or-session")
    await denied_401("m37462-ci-only-unknown-token-NEVER-REAL-09")

    # Revoke TOKEN1 through the token-verified SECURITY DEFINER function.
    # Auth role has NO direct SQL UPDATE permission to public.sessions.
    import asyncpg
    conn=await asyncpg.connect(CI_DSN,timeout=5)
    try:
        revoked=await conn.fetchval(
            "SELECT public.auth_revoke_session($1::text)",TOKEN1)
        expect(revoked,True,"TOKEN_BOUND_REVOCATION")
    finally:
        await conn.close()
    await denied_401(TOKEN1)
    s2=await auth(TOKEN2)
    expect(s2.verified_session_id,str(S2),"NEW_TOKEN_UNREVOKED")
    print("M37462_DISPOSABLE_TOKEN_HASH_TO_SESSION_ID=PASS")
    print("M37462_ROTATED_AND_CROSS_TENANT_BEARERS=DENIED_FOR_OLD_CONTEXT")
    print("M37462_EXPIRED_AND_REVOKED_TOKEN=401")


async def async_main()->int:
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user="postgres",password="ci-test-only",connect_timeout=5,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_database() AS db,session_user AS actor,"
                "current_setting('transaction_read_only') AS ro,"
                "current_setting('is_superuser') AS root,inet_server_port() AS port"
            )
            identity=cur.fetchone()
            if (identity is None or identity["db"]!="frcaixinha_staging"
                or identity["actor"]!="postgres" or identity["ro"]!="on"
                or identity["root"]!="on" or identity["port"]!=5432):
                print("M37462_BLOCKED=DATABASE_IDENTITY_OR_NOT_READ_ONLY")
                return 1
            cur.execute(READBACK_SQL,(S1,T,A,REQUEST))
            rows=cur.fetchall()
            if len(rows)!=1:
                print("M37462_BLOCKED=SYNTHETIC_CONTEXT_ABSENT")
                return 1
            state,context=build_ci_trusted_context(
                dict(rows[0]),session_id=S1,tenant_id=T,
                admin_id=A,request_id=REQUEST,
                checked_at=datetime.now(timezone.utc),
            )
            if state!="CI_DISPOSABLE_SERVER_CONTEXT_READBACK_ONLY" or context is None:
                print("M37462_BLOCKED=SYNTHETIC_CONTEXT_INVALID")
                return 1
            cur.execute(
                "SELECT has_table_privilege('frcaixinha_app_role',"
                "'public.sessions','SELECT') AS app_session_read,"
                "has_column_privilege('frcaixinha_auth_token_ci',"
                "'public.sessions','token_hash','UPDATE') AS auth_hash_write"
            )
            access=cur.fetchone()
            if access["app_session_read"] or access["auth_hash_write"]:
                print("M37462_BLOCKED=EXCESSIVE_SESSION_PRIVILEGES")
                return 1
    # auth_database_url checks technical role; no original DB and no
    # production environment. Never print bearer or connection string.
    os.environ["FRCAIXINHA_TEST_AUTH"]="1"
    os.environ["ENVIRONMENT"]="ci"
    os.environ["AUTH_DATABASE_URL"]=CI_DSN
    await check_real_token_lookup(context=context)

    with psycopg.connect(
        host="127.0.0.1",port=5432,dbname="frcaixinha_staging",
        user="postgres",password="ci-test-only",connect_timeout=5,
        options="-c default_transaction_read_only=on",
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT revoked_at IS NOT NULL FROM public.sessions WHERE id=%s",(S1,)
            )
            expect(cur.fetchone()[0],True,"REVOKED_PERSISTED")
            for table in ("saas_payment_intents","saas_license_entitlements"):
                cur.execute(
                    "SELECT count(*) FROM public."+table+" WHERE tenant_id=%s",(T,)
                )
                expect(cur.fetchone()[0],0,"ZERO_FINANCIAL_ACTIVITY")
            cur.execute("SELECT count(*) FROM public.ledger_entries WHERE tenant_id=%s",(T,))
            expect(cur.fetchone()[0],0,"ZERO_TENANT_LEDGER")
    print("M37462_REAL_SAAS_CONSENT=NOT_ATTESTED")
    print("M37462_PAYMENT_PIX_LICENSE_ACTIVATION=OFF")
    print("M37462_TERМUX_LOCAL_DB=UNTOUCHED")
    return 0


def main()->int:
    if not environment_allowed(dict(os.environ)):
        print("M37462_BLOCKED=NON_DISPOSABLE_GITHUB_CI")
        return 1
    return asyncio.run(async_main())


if __name__=="__main__":
    raise SystemExit(main())
