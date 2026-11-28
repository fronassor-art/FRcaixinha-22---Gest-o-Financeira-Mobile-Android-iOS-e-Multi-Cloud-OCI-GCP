#!/usr/bin/env python3
"""M40923: PG18 disposable compromised SQL issuer versus off-DB action proof.

Explicitly demonstrates remaining NO-GO: app SQL login plus a stolen valid
Master bearer may still invoke the disconnected M40920 writer without PoP.
NOT a migration, no real HTTP endpoint, no durable approval registry.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import os
import secrets
import sys
from uuid import uuid4

def require_disposable() -> None:
    from m40922_saas_session_owner_disposable import require_disposable as prior
    prior()
    if os.environ.get("CI_M40923_DISPOSABLE")!="1":
        raise RuntimeError("M40923_CI_DISPOSABLE_ONLY")

def proof(conn) -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    import psycopg
    from psycopg.conninfo import make_conninfo
    from m40900_sql113_acl_fence_disposable import run as fence
    from m40920_master_token_writes_disposable import install_broker
    from m40921_saas_broker_role_split_disposable import split_broker_roles
    from m40922_saas_session_owner_disposable import separate_session_custody
    from m40923_offdb_master_action_gate import (
        EphemeralApprovalGate,body_digest,sign,
    )

    fence(conn)
    install_broker(conn)
    split_broker_roles(conn)
    separate_session_custody(conn)

    # This synthetic, untrusted SQL login simulates compromise of the
    # M40730 issuer boundary, but is granted NO Master/SaaS capabilities.
    conn.execute(
        "CREATE ROLE m40923_issuer_login LOGIN NOINHERIT NOBYPASSRLS "
        "PASSWORD 'synthetic-m40923-issuer-only-ci'"
    )
    for schema in ("m40910","m40920"):
        assert not conn.execute(
            "SELECT has_schema_privilege('m40923_issuer_login',%s,'USAGE')",
            (schema,),
        ).fetchone()[0]
    for role in ("frcaixinha_app_role","m40910_broker_owner",
                 "m40921_writer_owner","m40922_session_owner"):
        assert not conn.execute(
            "SELECT pg_catalog.pg_has_role('m40923_issuer_login',%s,'MEMBER')",
            (role,),
        ).fetchone()[0]
    for table in ("m40910.sessions","m40920.audit",
                  "public.platform_saas_promotion_revisions"):
        for privilege in ("SELECT","INSERT","UPDATE","DELETE"):
            assert not conn.execute(
                "SELECT has_table_privilege('m40923_issuer_login',%s,%s)",
                (table,privilege),
            ).fetchone()[0]
    print("M40923_COMPROMISED_ISSUER_SQL_GRANTS=ZERO")

    master=conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist"
    ).fetchone()[0]
    tenant=conn.execute(
        "SELECT id FROM public.tenants WHERE admin_user_id=%s LIMIT 1",
        (master,),
    ).fetchone()[0]
    version=conn.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' ORDER BY created_at DESC,id DESC LIMIT 1"
    ).fetchone()[0]
    token=secrets.token_urlsafe(40)
    digest=sha256(token.encode("ascii")).hexdigest()
    now=datetime.now(timezone.utc)
    conn.execute(
        "INSERT INTO m40910.sessions "
        "(token_digest,user_id,active_role,tenant_id,expires_at,revoked_at)"
        " VALUES (%s,%s,'MASTER',%s,%s,NULL)",
        (digest,master,tenant,now+timedelta(minutes=30)),
    )

    sql="SELECT * FROM m40920.create_draft(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
    payload={
        "tier":"ESSENCIAL","period":"MONTHLY",
        "version":str(version),"price":"61.23",
        "title":"Oferta sintetica",
        "benefit":"Beneficio restrito a ambiente descartavel",
        "start":(now-timedelta(hours=1)).isoformat(),
        "end":(now+timedelta(days=5)).isoformat(),
        "reason":"Aprovacao experimental externa ao SQL",
    }
    args=(
        token,payload["tier"],payload["period"],version,Decimal(payload["price"]),
        payload["title"],payload["benefit"],
        now-timedelta(hours=1),now+timedelta(days=5),payload["reason"],
    )
    def deny(c, statement, params, label):
        try:
            with c.transaction():
                c.execute(statement,params)
        except psycopg.Error as exc:
            assert exc.sqlstate=="42501",(label,exc.sqlstate)
        else:
            raise AssertionError("M40923_SQL_ISSUER_ESCAPED_"+label)

    issuer_url=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],
        user="m40923_issuer_login",
        password="synthetic-m40923-issuer-only-ci",
    )
    with psycopg.connect(issuer_url,autocommit=True) as issuer:
        # Even with a stolen valid bearer and forged GUC, issuer SQL cannot
        # call writer, read session digests or impersonate application roles.
        issuer.execute("SELECT set_config('app.current_role','MASTER',false)")
        issuer.execute(
            "SELECT set_config('app.current_user_id',%s,false)",(str(master),)
        )
        deny(issuer,"SELECT * FROM m40910.sessions",(),"SESSION_READ")
        deny(issuer,"INSERT INTO m40910.sessions DEFAULT VALUES",(),"TOKEN_MINT")
        deny(issuer,"SELECT * FROM m40920.audit",(),"AUDIT_READ")
        deny(issuer,sql,args,"MASTER_DRAFT_EVEN_WITH_VALID_BEARER")
        deny(issuer,"SET ROLE frcaixinha_app_role",(),"ROLE_ESCALATION")
    print("M40923_STOLEN_SIGNER_SQL_LOGIN_NO_MASTER_WRITE=PASS")

    # All public keys and approval nonces below live in Python memory ONLY.
    private=Ed25519PrivateKey.generate()
    actor=str(master)
    scope=(actor,str(tenant),digest)
    gate=EphemeralApprovalGate({scope:private.public_key()})
    expires=int(datetime.now(timezone.utc).timestamp())+15
    command={
        "version":1,
        "method":"POST",
        "path":"/master/saas-promotions/draft",
        "actor_id":actor,
        "tenant_id":str(tenant),
        "session_digest":digest,
        "action":"DRAFT",
        "campaign_id":None,
        "expected_revision":0,
        "body_digest":body_digest(payload),
        "nonce":str(uuid4()),
        "expires_at":expires,
    }
    signature=sign(private,command)
    assert not gate.authorize({**command,"body_digest":"0"*64},
                              signature,now=expires-15)
    assert not gate.authorize({**command,"action":"CANCEL"},
                              signature,now=expires-15)
    assert not gate.authorize({**command,"tenant_id":str(uuid4())},
                              signature,now=expires-15)
    other_private=Ed25519PrivateKey.generate()
    assert not gate.authorize(command,sign(other_private,command),
                              now=expires-15)
    assert gate.authorize(command,signature,now=expires-15)
    assert not gate.authorize(command,signature,now=expires-15)
    assert not gate.authorize({**command,"nonce":str(uuid4()),
        "expires_at":expires-16},sign(private,{**command,"nonce":str(uuid4()),
        "expires_at":expires-16}),now=expires-15)
    print("M40923_OFFDB_ED25519_COMMAND_CONTEXT=PASS")
    print("M40923_OFFDB_NONCE_SINGLE_USE=PASS_MEMORY_ONLY")

    app_url=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],
        user="m40910_ci_login",
        password="synthetic-m40910-only-no-real-secret",
    )
    with psycopg.connect(app_url,autocommit=True) as app:
        app.execute("SET ROLE frcaixinha_app_role")
        approved=app.execute(sql,args).fetchone()
        assert approved[1:]==(1,"DRAFT")
        assert conn.execute(
            "SELECT count(*) FROM m40920.audit WHERE campaign_id=%s",
            (approved[0],),
        ).fetchone()[0]==1
        print("M40923_APPROVED_MASTER_DRAFT=PASS_DISCONNECTED_PROOF")

        # Deliberate adverse test: proof not enforced by SQL broker itself.
        # A leaked app SQL login AND valid bearer can bypass Python verifier.
        unapproved=app.execute(sql,args).fetchone()
        assert unapproved[0]!=approved[0]
        print("M40923_STOLEN_APP_SQL_PLUS_MASTER_BEARER=NO_GO_BYPASS_CONFIRMED")

        conn.execute(
            "UPDATE m40910.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",(digest,),
        )
        try:
            with app.transaction():
                app.execute(sql,args)
        except psycopg.Error as exc:
            assert exc.sqlstate=="42501",exc.sqlstate
        else:
            raise AssertionError("M40923_REVOKED_MASTER_SESSION_REUSED")
        print("M40923_MASTER_REVOCATION=ENFORCED")

    print("M40923_OFFDB_SIGNATURE_NOT_STORED_IN_SQL=PASS_SYNTHETIC")
    print("M40923_REAL_FASTAPI_AND_ORIGINAL_ACL=NOT_MODIFIED")
    print("M40923_DB_OWNER_OR_APP_SQL_COMPROMISE=NOT_REMEDIATED_NO_GO")

def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            proof(conn)
    except Exception as exc:
        import traceback
        frame=traceback.extract_tb(exc.__traceback__)[-1]
        print("M40923_FAILURE_SITE="+frame.name+":"+str(frame.lineno))
        print("M40923_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40923_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40923_ORIGINAL_ACL_CHANGES=NONE")
        print("M40923_MIGRATIONS=NONE")
        print("M40923_LOCAL_DB_WRITES=NONE")
        print("M40923_SERVICE_RESTARTS=NONE")
        print("M40923_PIX_REAL=OFF")
        print("M40923_PAGAMENTOS_REAIS=OFF")
        print("M40923_ATIVACAO_REAL=OFF")
        print("M40923_PRODUCTION=BLOCKED")
    print("M40923_STATUS=PASS_SYNTHETIC_WITH_NO_GO_LIMITS")
    return 0

if __name__=="__main__":
    sys.exit(main())
