#!/usr/bin/env python3
"""M40925: synthetic ASGI Ed25519 Master approval -> PG18 one-time SQL fence.

NO production HTTP, no real issuer, no original PG5433, no service reload.
A compromised approval-issuer SQL login + application SQL credentials + valid
Master bearer still bypass client PoP; this is a deliberately demonstrated NO-GO.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import os
import secrets
import sys
from threading import Lock
from uuid import UUID, uuid4

DRAFT_KEYS=frozenset({
    "tier","period","version","price","title","benefit","start","end","reason",
})
TRANS_KEYS=frozenset({
    "campaign_id","expected_revision","action","reason",
})
ISSUER_COLS=(
    "approval_digest,session_digest,actor_id,tenant_id,operation,"
    "campaign_id,expected_revision,body_digest,expires_at"
)

def require_disposable() -> None:
    from m40924_master_one_time_sql_gate_disposable import require_disposable as prior
    prior()
    if os.environ.get("CI_M40925_DISPOSABLE")!="1":
        raise RuntimeError("M40925_GITHUB_PG18_ONLY")

def install_issuer(conn) -> None:
    # No shared app/issuer account. The issuer can mint a capability, but
    # cannot read sessions or execute the promotion writers.
    conn.execute(
        "CREATE ROLE m40925_issuer_role NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    conn.execute(
        "CREATE ROLE m40925_issuer_login LOGIN NOINHERIT NOBYPASSRLS "
        "PASSWORD 'synthetic-m40925-only-issuer-login'"
    )
    conn.execute("GRANT m40925_issuer_role TO m40925_issuer_login")
    conn.execute("GRANT USAGE ON SCHEMA m40924 TO m40925_issuer_role")
    conn.execute(
        "GRANT INSERT ("+ISSUER_COLS+") ON m40924.approvals "
        "TO m40925_issuer_role"
    )
    conn.execute(
        "CREATE POLICY m40925_issuer_insert ON m40924.approvals "
        "FOR INSERT TO m40925_issuer_role WITH CHECK (true)"
    )
    for fn in (
        "m40924.draft_digest(character varying,character varying,uuid,"
        "numeric,text,text,timestamp with time zone,timestamp with time zone,text)",
        "m40924.transition_digest(uuid,integer,text,text)",
    ):
        conn.execute("GRANT EXECUTE ON FUNCTION "+fn+" TO m40925_issuer_role")
    for role in ("m40925_issuer_role","m40925_issuer_login"):
        for priv in ("SELECT","UPDATE","DELETE","TRUNCATE"):
            assert not conn.execute(
                "SELECT has_table_privilege(%s,'m40924.approvals',%s)",
                (role,priv),
            ).fetchone()[0],(role,priv)
        for table in ("m40910.sessions","m40920.audit"):
            for priv in ("SELECT","INSERT","UPDATE","DELETE"):
                assert not conn.execute(
                    "SELECT has_table_privilege(%s,%s,%s)",(role,table,priv),
                ).fetchone()[0],(role,table,priv)
        for function in (
            "m40920.create_draft(text,character varying,character varying,"
            "uuid,numeric,text,text,timestamp with time zone,"
            "timestamp with time zone,text)",
            "m40920.transition(text,uuid,integer,text,text)",
            "m40924.gated_transition(text,text,uuid,integer,text,text)",
        ):
            assert not conn.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE')",
                (role,function),
            ).fetchone()[0],(role,function)
        for parent in (
            "frcaixinha_app_role","m40921_writer_owner",
            "m40924_approval_owner","m40924_gate_owner",
            "m40922_session_owner",
        ):
            assert not conn.execute(
                "SELECT pg_catalog.pg_has_role(%s,%s,'MEMBER')",
                (role,parent),
            ).fetchone()[0],(role,parent)
    assert not conn.execute(
        "SELECT pg_catalog.pg_has_role('frcaixinha_app_role',"
        "'m40925_issuer_role','MEMBER')"
    ).fetchone()[0]
    assert not conn.execute(
        "SELECT has_table_privilege('frcaixinha_app_role',"
        "'m40924.approvals','INSERT')"
    ).fetchone()[0]
    print("M40925_SQL_ISSUER_APP_AND_WRITER_ROLES=DISJOINT")
    print("M40925_SQL_ISSUER_ONLY_INSERTS_APPROVAL_DIGESTS=PASS")

def parse_arguments(action, payload, command):
    """Exact API-side schema prevents unsigned defaults and aliasing."""
    if not isinstance(payload,dict):
        raise ValueError("BAD_BODY")
    if action=="DRAFT":
        if set(payload)!=DRAFT_KEYS:
            raise ValueError("BAD_DRAFT_FIELDS")
        tier,period=payload["tier"],payload["period"]
        if (tier not in ("ESSENCIAL","INTERMEDIARIO")
                or period not in ("MONTHLY","ANNUAL")):
            raise ValueError("BAD_PLAN")
        version=UUID(payload["version"])
        price=Decimal(payload["price"])
        if not price.is_finite():
            raise ValueError("BAD_PRICE")
        start=datetime.fromisoformat(payload["start"])
        end=datetime.fromisoformat(payload["end"])
        if (start.tzinfo is None or end.tzinfo is None):
            raise ValueError("MISSING_TIMEZONE")
        for x in ("title","benefit","reason"):
            if not isinstance(payload[x],str):
                raise ValueError("BAD_TEXT")
        return (
            tier,period,version,price,payload["title"],payload["benefit"],
            start,end,payload["reason"],
        )
    if action in ("PUBLISH","CANCEL"):
        if set(payload)!=TRANS_KEYS:
            raise ValueError("BAD_TRANSITION_FIELDS")
        if (payload["action"]!=action
            or payload["campaign_id"]!=command["campaign_id"]
            or payload["expected_revision"]!=command["expected_revision"]
            or isinstance(payload["expected_revision"],bool)
            or not isinstance(payload["expected_revision"],int)
            or not isinstance(payload["reason"],str)):
            raise ValueError("BAD_TRANSITION_CONTEXT")
        return (
            UUID(payload["campaign_id"]),payload["expected_revision"],
            action,payload["reason"],
        )
    raise ValueError("UNKNOWN_ACTION")

def app_factory(*,issuer_dsn,app_dsn,public_registry):
    import psycopg
    from fastapi import Body, FastAPI, Header
    from fastapi.responses import JSONResponse
    from m40923_offdb_master_action_gate import (
        EphemeralApprovalGate,body_digest,
    )

    api=FastAPI(title="M40925 synthetic Master SQL approval boundary")
    verifier=EphemeralApprovalGate(public_registry)
    nonce_lock=Lock()

    def denied(status=401):
        return JSONResponse(
            {"detail":"Unauthorized" if status==401 else "Unavailable"},
            status_code=status,headers={"Cache-Control":"no-store"},
        )

    def execute(path,data,authorization,signature):
        if (not authorization or not authorization.startswith("Bearer ")
            or not signature or not isinstance(data,dict)
            or set(data)!={"command","payload"}):
            return denied()
        token=authorization[len("Bearer "):]
        if not (32<=len(token)<=256 and token.isascii()):
            return denied()
        command,payload=data["command"],data["payload"]
        if not isinstance(command,dict):
            return denied()
        try:
            from m40923_offdb_master_action_gate import PATHS
            action=command["action"]
            if (action not in PATHS or PATHS[action]!=path
                or command["session_digest"]!=sha256(token.encode("ascii")).hexdigest()
                or command["body_digest"]!=body_digest(payload)):
                return denied()
            params=parse_arguments(action,payload,command)
            with nonce_lock:
                if not verifier.authorize(
                    command,signature,
                    now=int(datetime.now(timezone.utc).timestamp()),
                ):
                    return denied()
            # Deliberately separate database identities:
            # only this ephemeral Python verifier knows the public keys.
            # SQL receives NO Ed25519 signature or public/private key.
            capability=secrets.token_urlsafe(48)
            digest=sha256(capability.encode("ascii")).hexdigest()
            expires=datetime.fromtimestamp(command["expires_at"],timezone.utc)
            with psycopg.connect(issuer_dsn,autocommit=True) as issuer:
                issuer.execute("SET ROLE m40925_issuer_role")
                if action=="DRAFT":
                    fingerprint=issuer.execute(
                        "SELECT m40924.draft_digest(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        params,
                    ).fetchone()[0]
                else:
                    fingerprint=issuer.execute(
                        "SELECT m40924.transition_digest(%s,%s,%s,%s)",
                        params,
                    ).fetchone()[0]
                issuer.execute(
                    "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        digest,command["session_digest"],
                        UUID(command["actor_id"]),UUID(command["tenant_id"]),
                        action,UUID(command["campaign_id"])
                        if command["campaign_id"] else None,
                        command["expected_revision"],fingerprint,expires,
                    ),
                )
            with psycopg.connect(app_dsn,autocommit=True) as app:
                app.execute("SET ROLE frcaixinha_app_role")
                if action=="DRAFT":
                    row=app.execute(
                        "SELECT * FROM m40924.gated_draft("
                        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (capability,token,*params),
                    ).fetchone()
                else:
                    row=app.execute(
                        "SELECT * FROM m40924.gated_transition("
                        "%s,%s,%s,%s,%s,%s)",
                        (capability,token,*params),
                    ).fetchone()
            return JSONResponse(
                {"campaign_id":str(row[0]),"revision":row[1],"state":row[2]},
                status_code=201 if action=="DRAFT" else 200,
                headers={"Cache-Control":"no-store"},
            )
        except (ValueError,TypeError,InvalidOperation,KeyError,OverflowError):
            return denied()
        except psycopg.Error as exc:
            return denied(401 if exc.sqlstate in ("42501","P0001") else 503)

    @api.post("/master/saas-promotions/draft")
    def draft(
        data:dict=Body(...),
        authorization:str|None=Header(default=None),
        x_fr_signature:str|None=Header(default=None),
    ):
        return execute(
            "/master/saas-promotions/draft",data,authorization,x_fr_signature
        )

    @api.post("/master/saas-promotions/transition")
    def transition(
        data:dict=Body(...),
        authorization:str|None=Header(default=None),
        x_fr_signature:str|None=Header(default=None),
    ):
        return execute(
            "/master/saas-promotions/transition",data,authorization,
            x_fr_signature,
        )

    return api

async def proof(conn) -> None:
    import psycopg
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from httpx import ASGITransport,AsyncClient
    from psycopg.conninfo import make_conninfo
    from m40900_sql113_acl_fence_disposable import run as fence
    from m40920_master_token_writes_disposable import install_broker
    from m40921_saas_broker_role_split_disposable import split_broker_roles
    from m40922_saas_session_owner_disposable import separate_session_custody
    from m40924_master_one_time_sql_gate_disposable import install_gate
    from m40923_offdb_master_action_gate import body_digest,sign,PATHS

    fence(conn)
    install_broker(conn)
    split_broker_roles(conn)
    separate_session_custody(conn)
    install_gate(conn)
    install_issuer(conn)

    master=conn.execute(
        "SELECT user_id FROM public.m40560_ci_master_allowlist LIMIT 1"
    ).fetchone()[0]
    tenant=conn.execute(
        "SELECT id FROM public.tenants WHERE admin_user_id=%s LIMIT 1",
        (master,),
    ).fetchone()[0]
    version=conn.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' ORDER BY created_at DESC,id DESC LIMIT 1"
    ).fetchone()[0]
    token=secrets.token_urlsafe(48)
    member=secrets.token_urlsafe(48)
    now=datetime.now(timezone.utc)
    for bearer,role in ((token,"MASTER"),(member,"TENANT_MEMBER")):
        conn.execute(
            "INSERT INTO m40910.sessions("
            "token_digest,user_id,active_role,tenant_id,expires_at,revoked_at)"
            " VALUES (%s,%s,%s,%s,%s,NULL)",
            (sha256(bearer.encode()).hexdigest(),master,role,tenant,
             now+timedelta(minutes=30)),
        )
    issuer_dsn=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],
        user="m40925_issuer_login",
        password="synthetic-m40925-only-issuer-login",
    )
    app_dsn=make_conninfo(
        os.environ["CI_PROMOTIONS_DATABASE_URL"],
        user="m40910_ci_login",
        password="synthetic-m40910-only-no-real-secret",
    )
    key=Ed25519PrivateKey.generate()
    other_key=Ed25519PrivateKey.generate()
    registry={
        (str(master),str(tenant),sha256(token.encode()).hexdigest()):
            key.public_key(),
    }
    api=app_factory(
        issuer_dsn=issuer_dsn,app_dsn=app_dsn,public_registry=registry
    )

    start=(now-timedelta(minutes=1)).isoformat()
    end=(now+timedelta(days=4)).isoformat()
    payload={
        "tier":"ESSENCIAL","period":"MONTHLY","version":str(version),
        "price":"70.25","title":"Campanha de ensaio",
        "benefit":"Beneficio sintetico sem qualquer operacao real",
        "start":start,"end":end,
        "reason":"Autorizacao assinada separada de SQL",
    }
    def envelope(bearer,act,body,*,actor=master,ten=tenant,signer=key,
                 expires=None,nonce=None):
        command={
            "version":1,"method":"POST","path":PATHS[act],
            "actor_id":str(actor),"tenant_id":str(ten),
            "session_digest":sha256(bearer.encode()).hexdigest(),
            "action":act,
            "campaign_id":body.get("campaign_id") if act!="DRAFT" else None,
            "expected_revision":body.get("expected_revision",0)
            if act!="DRAFT" else 0,
            "body_digest":body_digest(body),
            "nonce":str(nonce or uuid4()),
            "expires_at":expires or int(
                datetime.now(timezone.utc).timestamp())+15,
        }
        return ({"command":command,"payload":body},sign(signer,command))

    async with AsyncClient(
        transport=ASGITransport(app=api),base_url="http://fixture-m40925"
    ) as http:
        async def send(data,sig,bearer=token,*,path=None):
            path=path or data["command"]["path"]
            return await http.post(
                path,json=data,
                headers={"Authorization":"Bearer "+bearer,
                         "X-FR-Signature":sig},
            )
        first,sig=envelope(token,"DRAFT",payload)
        no_sig=await http.post(PATHS["DRAFT"],json=first,headers={
            "Authorization":"Bearer "+token,
        })
        assert no_sig.status_code==401
        assert (await send(first,sign(other_key,first["command"]))).status_code==401
        altered={**first,"payload":{**payload,"price":"69.99"}}
        assert (await send(altered,sig)).status_code==401
        changed_tenant={**first,"command":{
            **first["command"],"tenant_id":str(uuid4()),
        }}
        assert (await send(changed_tenant,sig)).status_code==401
        assert (await send(first,sig,member)).status_code==401
        assert (await send(first,sig,path=PATHS["PUBLISH"])).status_code==401
        assert (await send(first,sig)).status_code==201
        assert (await send(first,sig)).status_code==401
        print("M40925_ASGI_ED25519_CONTEXT_TAMPER_REPLAY=DENIED")

        # Fresh valid command succeeds only after external PoP verification
        # and issuer role inserts the SQL one-use approval.
        second,sig2=envelope(token,"DRAFT",payload)
        r=await send(second,sig2)
        assert r.status_code==201,(r.status_code,r.text)
        campaign=r.json()["campaign_id"]
        assert r.json()["revision"]==1 and r.json()["state"]=="DRAFT"
        def transition_body(action,revision):
            return {
                "campaign_id":campaign,"expected_revision":revision,
                "action":action,"reason":
                    "Operacao autorizada apenas em homologacao descartavel",
            }
        pub,s_pub=envelope(token,"PUBLISH",transition_body("PUBLISH",1))
        pub_ok=await send(pub,s_pub)
        assert pub_ok.status_code==200,(pub_ok.status_code,pub_ok.text)
        assert pub_ok.json()["state"]=="PUBLISHED"
        assert (await send(pub,s_pub)).status_code==401
        cancel,s_cancel=envelope(token,"CANCEL",transition_body("CANCEL",2))
        cancel_ok=await send(cancel,s_cancel)
        assert cancel_ok.status_code==200,(cancel_ok.status_code,cancel_ok.text)
        assert cancel_ok.json()["state"]=="CANCELED"
        print("M40925_END_TO_END_DRAFT_PUBLISH_CANCEL=PASS_SYNTHETIC")

        # SQL app login plus raw bearer remains insufficient by itself.
        raw_sql=(
            "SELECT * FROM m40920.create_draft("
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        gated_sql=(
            "SELECT * FROM m40924.gated_draft("
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        params=parse_arguments("DRAFT",payload,second["command"])
        def denied_sql(app,statement,args):
            try:
                with app.transaction():
                    app.execute(statement,args)
            except psycopg.Error as exc:
                assert exc.sqlstate=="42501",exc.sqlstate
            else:
                raise AssertionError("M40925_UNAUTHORIZED_SQL_WRITE")
        with psycopg.connect(app_dsn,autocommit=True) as app:
            app.execute("SET ROLE frcaixinha_app_role")
            app.execute("SELECT set_config('app.current_role','MASTER',false)")
            app.execute(
                "SELECT set_config('app.current_user_id',%s,false)",
                (str(master),),
            )
            denied_sql(app,raw_sql,(token,*params))
            denied_sql(app,gated_sql,("not-an-approval",token,*params))
            denied_sql(app,"SET ROLE m40925_issuer_role",())
        print("M40925_STOLEN_APP_SQL_PLUS_MASTER_NO_APPROVAL=DENIED")

        concurrent,conc_sig=envelope(token,"DRAFT",payload)
        responses=await asyncio.gather(*[
            send(concurrent,conc_sig) for _ in range(6)
        ])
        codes=[r.status_code for r in responses]
        assert codes.count(201)==1,codes
        assert codes.count(401)==5,codes
        print("M40925_ASGI_CONCURRENT_SIGNED_NONCE_ONE_OF_SIX=PASS")

        revoked,rev_sig=envelope(token,"DRAFT",payload)
        conn.execute(
            "UPDATE m40910.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",(sha256(token.encode()).hexdigest(),),
        )
        assert (await send(revoked,rev_sig)).status_code==401
        print("M40925_REVOKED_MASTER_SIGNED_COMMAND=DENIED")

        # Known NO-GO: a compromised issuer SQL login can mint its OWN
        # approval digest, and a separate stolen app SQL login + valid Master
        # token can consume it without any Ed25519 proof. Create a second
        # unrevoked Master token in synthetic PG to demonstrate the attack.
        token2=secrets.token_urlsafe(48)
        conn.execute(
            "INSERT INTO m40910.sessions("
            "token_digest,user_id,active_role,tenant_id,expires_at,revoked_at)"
            " VALUES (%s,%s,'MASTER',%s,%s,NULL)",
            (sha256(token2.encode()).hexdigest(),master,tenant,
             datetime.now(timezone.utc)+timedelta(minutes=30)),
        )
        forged_cap=secrets.token_urlsafe(48)
        with psycopg.connect(issuer_dsn,autocommit=True) as stolen_issuer:
            stolen_issuer.execute("SET ROLE m40925_issuer_role")
            fingerprint=stolen_issuer.execute(
                "SELECT m40924.draft_digest(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                params,
            ).fetchone()[0]
            stolen_issuer.execute(
                "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                "VALUES (%s,%s,%s,%s,'DRAFT',NULL,0,%s,%s)",
                (
                    sha256(forged_cap.encode()).hexdigest(),
                    sha256(token2.encode()).hexdigest(),
                    master,tenant,fingerprint,
                    datetime.now(timezone.utc)+timedelta(seconds=15),
                ),
            )
        with psycopg.connect(app_dsn,autocommit=True) as stolen_app:
            stolen_app.execute("SET ROLE frcaixinha_app_role")
            bypass=stolen_app.execute(
                gated_sql,(forged_cap,token2,*params),
            ).fetchone()
        assert bypass[1:]==(1,"DRAFT")
        print("M40925_STOLEN_ISSUER_PLUS_APP_SQL_PLUS_BEARER=NO_GO_BYPASS")
        print("M40925_APPROVER_SQL_LOGIN_COMPROMISE=NOT_REMEDIATED")
        print("M40925_PUBLIC_KEY_ENROLLMENT_DEVICE_ATTESTATION=NOT_ATTESTED")

    assert conn.execute(
        "SELECT action,revision FROM m40920.audit "
        "WHERE campaign_id=%s ORDER BY revision",
        (UUID(campaign),),
    ).fetchall()==[("DRAFT",1),("PUBLISHED",2),("CANCELED",3)]
    assert conn.execute(
        "SELECT count(*) FROM m40924.approvals WHERE consumed_at IS NOT NULL"
    ).fetchone()[0]>=5
    print("M40925_KEYS_AND_SIGNATURES_NEVER_PASSED_TO_SQL=PASS_SYNTHETIC")
    print("M40925_REAL_FASTAPI_AND_ORIGINAL_PG=NOT_MODIFIED")
    print("M40925_STATUS=PASS_DISPOSABLE_BRIDGE_WITH_NO_GO")

def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            asyncio.run(proof(conn))
    except Exception as exc:
        import traceback
        frame=traceback.extract_tb(exc.__traceback__)[-1]
        print("M40925_FAILURE_SITE="+frame.name+":"+str(frame.lineno))
        if getattr(exc,"sqlstate",None):
            print("M40925_SQLSTATE="+exc.sqlstate)
        print("M40925_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40925_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40925_ORIGINAL_ACL_CHANGES=NONE")
        print("M40925_MIGRATIONS=NONE")
        print("M40925_LOCAL_DB_WRITES=NONE")
        print("M40925_SERVICE_RESTARTS=NONE")
        print("M40925_PIX_REAL=OFF")
        print("M40925_PAGAMENTOS_REAIS=OFF")
        print("M40925_ATIVACAO_REAL=OFF")
        print("M40925_PRODUCTION=BLOCKED")
    return 0

if __name__=="__main__":
    sys.exit(main())
