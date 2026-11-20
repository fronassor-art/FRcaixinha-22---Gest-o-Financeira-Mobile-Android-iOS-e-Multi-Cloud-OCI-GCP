#!/usr/bin/env python3
"""M40926: guardian approval seal required in addition to issuer SQL token.

PG18 in GitHub CI only. Demonstrates *conditional* resistance to a stolen
issuer+app+Master credential set when the guardian SQL credential stays safe.
An adversary holding all three SQL credentials can STILL bypass Ed25519.
No production service, bank, migration, role grant or Android integration.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import secrets
import sys
from threading import Lock
from uuid import UUID, uuid4

GUARD_COLUMNS=(
    "approval_digest,session_digest,actor_id,tenant_id,operation,"
    "campaign_id,expected_revision,body_digest,expires_at"
)

def require_disposable() -> None:
    from m40925_signed_master_sql_bridge_disposable import require_disposable as prior
    prior()
    if os.environ.get("CI_M40926_DISPOSABLE")!="1":
        raise RuntimeError("M40926_GITHUB_PG18_DISPOSABLE_ONLY")

def install_guardian(conn) -> None:
    """One independent, insert-only guardian; trigger checks and consumes seal."""
    conn.execute(
        "CREATE ROLE m40926_seal_owner NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    conn.execute(
        "CREATE ROLE m40926_seal_checker NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    conn.execute(
        "CREATE ROLE m40926_guardian_writer NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    conn.execute(
        "CREATE ROLE m40926_guardian_login LOGIN NOINHERIT NOBYPASSRLS "
        "PASSWORD 'm40926-only-disposable-guardian'"
    )
    conn.execute("GRANT m40926_guardian_writer TO m40926_guardian_login")
    conn.execute("CREATE SCHEMA m40926 AUTHORIZATION m40926_seal_owner")
    conn.execute("REVOKE ALL ON SCHEMA m40926 FROM PUBLIC")
    conn.execute(
        "GRANT USAGE ON SCHEMA m40926 "
        "TO m40926_guardian_writer,m40926_seal_checker"
    )
    conn.execute("""
        CREATE TABLE m40926.seals(
            approval_digest text PRIMARY KEY CHECK (
                approval_digest ~ '^[0-9a-f]{64}$'),
            session_digest text NOT NULL CHECK (
                session_digest ~ '^[0-9a-f]{64}$'),
            actor_id uuid NOT NULL,
            tenant_id uuid NOT NULL,
            operation text NOT NULL CHECK (
                operation IN ('DRAFT','PUBLISH','CANCEL')),
            campaign_id uuid,
            expected_revision integer NOT NULL CHECK (
                expected_revision>=0),
            body_digest text NOT NULL CHECK (
                body_digest ~ '^[0-9a-f]{64}$'),
            expires_at timestamptz NOT NULL,
            consumed_at timestamptz
        )
    """)
    conn.execute("ALTER TABLE m40926.seals OWNER TO m40926_seal_owner")
    conn.execute(
        "REVOKE ALL ON m40926.seals FROM PUBLIC,frcaixinha_app_role,"
        "m40925_issuer_role,m40924_gate_owner,m40921_writer_owner"
    )
    conn.execute("ALTER TABLE m40926.seals ENABLE ROW LEVEL SECURITY")
    conn.execute("ALTER TABLE m40926.seals FORCE ROW LEVEL SECURITY")
    conn.execute(
        "GRANT INSERT ("+GUARD_COLUMNS+") ON m40926.seals "
        "TO m40926_guardian_writer"
    )
    conn.execute(
        "GRANT SELECT,UPDATE(consumed_at) ON m40926.seals "
        "TO m40926_seal_checker"
    )
    conn.execute(
        "CREATE POLICY m40926_seal_issue ON m40926.seals FOR INSERT "
        "TO m40926_guardian_writer WITH CHECK (true)"
    )
    conn.execute(
        "CREATE POLICY m40926_seal_read ON m40926.seals FOR SELECT "
        "TO m40926_seal_checker USING (true)"
    )
    conn.execute(
        "CREATE POLICY m40926_seal_consume ON m40926.seals FOR UPDATE "
        "TO m40926_seal_checker USING (true) WITH CHECK (true)"
    )
    conn.execute("""
        CREATE FUNCTION m40926.require_guardian_seal()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        BEGIN
          IF OLD.consumed_at IS NOT NULL OR NEW.consumed_at IS NULL THEN
            RAISE EXCEPTION 'M40926_INVALID_CONSUMPTION'
              USING ERRCODE='42501';
          END IF;
          UPDATE m40926.seals AS s
          SET consumed_at=pg_catalog.clock_timestamp()
          WHERE s.approval_digest=NEW.approval_digest
            AND s.session_digest=NEW.session_digest
            AND s.actor_id=NEW.actor_id
            AND s.tenant_id=NEW.tenant_id
            AND s.operation=NEW.operation
            AND s.campaign_id IS NOT DISTINCT FROM NEW.campaign_id
            AND s.expected_revision=NEW.expected_revision
            AND s.body_digest=NEW.body_digest
            AND s.expires_at>=NEW.expires_at
            AND s.expires_at>pg_catalog.clock_timestamp()
            AND s.consumed_at IS NULL;
          IF NOT FOUND THEN
            RAISE EXCEPTION 'M40926_GUARDIAN_REQUIRED'
              USING ERRCODE='42501';
          END IF;
          RETURN NEW;
        END
        $body$
    """)
    conn.execute(
        "ALTER FUNCTION m40926.require_guardian_seal() "
        "OWNER TO m40926_seal_checker"
    )
    conn.execute(
        "REVOKE ALL ON FUNCTION m40926.require_guardian_seal() FROM PUBLIC"
    )
    conn.execute("""
        CREATE TRIGGER m40926_guardian_fence
        BEFORE UPDATE OF consumed_at ON m40924.approvals
        FOR EACH ROW EXECUTE FUNCTION m40926.require_guardian_seal()
    """)
    record=conn.execute(
        "SELECT t.tgenabled,t.tgisinternal,"
        "pg_catalog.pg_get_userbyid(c.relowner) "
        "FROM pg_catalog.pg_trigger AS t "
        "JOIN pg_catalog.pg_class AS c ON c.oid=t.tgrelid "
        "WHERE t.tgname='m40926_guardian_fence' "
        "AND t.tgrelid='m40924.approvals'::pg_catalog.regclass"
    ).fetchone()
    assert record==("O",False,"m40924_approval_owner"),record
    for role in ("m40925_issuer_role","frcaixinha_app_role",
                 "m40924_gate_owner","m40921_writer_owner"):
        for verb in ("SELECT","INSERT","UPDATE","DELETE","TRUNCATE","TRIGGER"):
            assert not conn.execute(
                "SELECT has_table_privilege(%s,'m40926.seals',%s)",
                (role,verb),
            ).fetchone()[0],(role,verb)
        assert not conn.execute(
            "SELECT pg_catalog.pg_has_role(%s,'m40926_guardian_writer','MEMBER')",
            (role,),
        ).fetchone()[0],role
    for role in ("m40926_guardian_writer","m40926_guardian_login"):
        for p in ("SELECT","UPDATE","DELETE","TRUNCATE","TRIGGER"):
            assert not conn.execute(
                "SELECT has_table_privilege(%s,'m40926.seals',%s)",
                (role,p),
            ).fetchone()[0],(role,p)
        for tbl in ("m40924.approvals","m40910.sessions","m40920.audit"):
            assert not conn.execute(
                "SELECT has_table_privilege(%s,%s,'INSERT')",
                (role,tbl),
            ).fetchone()[0],(role,tbl)
        for privileged in (
            "frcaixinha_app_role","m40925_issuer_role",
            "m40924_gate_owner","m40926_seal_checker","m40926_seal_owner",
        ):
            assert not conn.execute(
                "SELECT pg_catalog.pg_has_role(%s,%s,'MEMBER')",
                (role,privileged),
            ).fetchone()[0],(role,privileged)
    print("M40926_GUARDIAN_TABLE_FORCED_RLS=PASS")
    print("M40926_GUARDIAN_FENCE_TRIGGER=ENABLED")
    print("M40926_GUARDIAN_ROLE_INDEPENDENT=PASS")

def app_factory(*,issuer_dsn,app_dsn,guardian_dsn,public_registry):
    """Synthetic HTTP bridge: both SQL approvals follow the Ed25519 check."""
    import psycopg
    from fastapi import FastAPI, Body, Header
    from fastapi.responses import JSONResponse
    from m40923_offdb_master_action_gate import (
        EphemeralApprovalGate,PATHS,body_digest,
    )
    from m40925_signed_master_sql_bridge_disposable import (
        parse_arguments,ISSUER_COLS,
    )
    api=FastAPI(title="M40926 synthetic dual-custody Master ASGI")
    verifier=EphemeralApprovalGate(public_registry)
    lock=Lock()

    def response(code,description):
        return JSONResponse(
            {"detail":description},status_code=code,
            headers={"Cache-Control":"no-store"},
        )

    def handle(path,data,authorization,signature):
        if (not authorization or not authorization.startswith("Bearer ")
            or not signature or not isinstance(data,dict)
            or set(data)!={"command","payload"}):
            return response(401,"Unauthorized")
        token=authorization[len("Bearer "):]
        if not (32<=len(token)<=256 and token.isascii()):
            return response(401,"Unauthorized")
        command,payload=data["command"],data["payload"]
        if not isinstance(command,dict):
            return response(401,"Unauthorized")
        try:
            action=command["action"]
            if (action not in PATHS or PATHS[action]!=path
                or command["session_digest"]!=sha256(
                    token.encode("ascii")).hexdigest()
                or command["body_digest"]!=body_digest(payload)):
                return response(401,"Unauthorized")
            params=parse_arguments(action,payload,command)
            with lock:
                if not verifier.authorize(
                    command,signature,
                    now=int(datetime.now(timezone.utc).timestamp())
                ):
                    return response(401,"Unauthorized")
            approval=secrets.token_urlsafe(48)
            approval_digest=sha256(approval.encode("ascii")).hexdigest()
            expires=datetime.fromtimestamp(
                command["expires_at"],timezone.utc
            )
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
                values=(
                    approval_digest,command["session_digest"],
                    UUID(command["actor_id"]),UUID(command["tenant_id"]),
                    action,UUID(command["campaign_id"])
                    if command["campaign_id"] else None,
                    command["expected_revision"],fingerprint,expires,
                )
                issuer.execute(
                    "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",values,
                )
            with psycopg.connect(guardian_dsn,autocommit=True) as guardian:
                guardian.execute("SET ROLE m40926_guardian_writer")
                guardian.execute(
                    "INSERT INTO m40926.seals ("+GUARD_COLUMNS+") "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",values,
                )
            with psycopg.connect(app_dsn,autocommit=True) as app:
                app.execute("SET ROLE frcaixinha_app_role")
                if action=="DRAFT":
                    result=app.execute(
                        "SELECT * FROM m40924.gated_draft("
                        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (approval,token,*params),
                    ).fetchone()
                else:
                    result=app.execute(
                        "SELECT * FROM m40924.gated_transition("
                        "%s,%s,%s,%s,%s,%s)",
                        (approval,token,*params),
                    ).fetchone()
            return JSONResponse(
                {"campaign_id":str(result[0]),"revision":result[1],
                 "state":result[2]},
                status_code=201 if action=="DRAFT" else 200,
                headers={"Cache-Control":"no-store"},
            )
        except (ValueError,TypeError,KeyError,OverflowError):
            return response(401,"Unauthorized")
        except psycopg.Error as exc:
            return response(401 if exc.sqlstate in ("42501","P0001")
                            else 503,"Unauthorized" if exc.sqlstate in
                            ("42501","P0001") else "Unavailable")

    @api.post("/master/saas-promotions/draft")
    def draft(
        data:dict=Body(...),
        authorization:str|None=Header(default=None),
        x_fr_signature:str|None=Header(default=None),
    ):
        return handle(
            "/master/saas-promotions/draft",data,authorization,x_fr_signature
        )

    @api.post("/master/saas-promotions/transition")
    def transition(
        data:dict=Body(...),
        authorization:str|None=Header(default=None),
        x_fr_signature:str|None=Header(default=None),
    ):
        return handle(
            "/master/saas-promotions/transition",data,authorization,
            x_fr_signature,
        )

    return api

async def proof(conn) -> None:
    import psycopg
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from httpx import ASGITransport,AsyncClient
    from psycopg.conninfo import make_conninfo
    from m40900_sql113_acl_fence_disposable import run as fence
    from m40920_master_token_writes_disposable import install_broker
    from m40921_saas_broker_role_split_disposable import split_broker_roles
    from m40922_saas_session_owner_disposable import separate_session_custody
    from m40924_master_one_time_sql_gate_disposable import install_gate
    from m40925_signed_master_sql_bridge_disposable import (
        install_issuer,parse_arguments,ISSUER_COLS,
    )
    from m40923_offdb_master_action_gate import (
        PATHS,body_digest,sign,
    )

    fence(conn)
    install_broker(conn)
    split_broker_roles(conn)
    separate_session_custody(conn)
    install_gate(conn)
    install_issuer(conn)
    install_guardian(conn)

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
    now=datetime.now(timezone.utc)
    token=secrets.token_urlsafe(48)
    member=secrets.token_urlsafe(48)
    for bearer,active in ((token,"MASTER"),(member,"TENANT_MEMBER")):
        conn.execute(
            "INSERT INTO m40910.sessions("
            "token_digest,user_id,active_role,tenant_id,expires_at,revoked_at)"
            " VALUES (%s,%s,%s,%s,%s,NULL)",
            (sha256(bearer.encode()).hexdigest(),master,active,tenant,
             now+timedelta(minutes=30)),
        )

    root=os.environ["CI_PROMOTIONS_DATABASE_URL"]
    issuer_dsn=make_conninfo(root,user="m40925_issuer_login",
                              password="synthetic-m40925-only-issuer-login")
    guardian_dsn=make_conninfo(root,user="m40926_guardian_login",
                                password="m40926-only-disposable-guardian")
    app_dsn=make_conninfo(root,user="m40910_ci_login",
                           password="synthetic-m40910-only-no-real-secret")
    master_key=Ed25519PrivateKey.generate()
    member_key=Ed25519PrivateKey.generate()
    registry={
        (str(master),str(tenant),
         sha256(token.encode()).hexdigest()):master_key.public_key(),
        (str(master),str(tenant),
         sha256(member.encode()).hexdigest()):member_key.public_key(),
    }
    api=app_factory(
        issuer_dsn=issuer_dsn,app_dsn=app_dsn,
        guardian_dsn=guardian_dsn,public_registry=registry,
    )
    payload={
        "tier":"ESSENCIAL","period":"MONTHLY",
        "version":str(version),"price":"74.95",
        "title":"Oferta dupla custodia",
        "benefit":"Beneficio sem cobranca em ambiente sintetico",
        "start":(now-timedelta(minutes=1)).isoformat(),
        "end":(now+timedelta(days=5)).isoformat(),
        "reason":"Aprovacao externa e duas custodias independentes",
    }
    params=parse_arguments("DRAFT",payload,{"action":"DRAFT"})
    def envelope(bearer,action,body,*,signer=master_key,alter=None):
        command={
            "version":1,"method":"POST","path":PATHS[action],
            "actor_id":str(master),"tenant_id":str(tenant),
            "session_digest":sha256(bearer.encode()).hexdigest(),
            "action":action,
            "campaign_id":body.get("campaign_id") if action!="DRAFT" else None,
            "expected_revision":body.get("expected_revision",0)
                if action!="DRAFT" else 0,
            "body_digest":body_digest(body),
            "nonce":str(uuid4()),
            "expires_at":int(datetime.now(timezone.utc).timestamp())+15,
        }
        if alter:
            command.update(alter)
        return ({"command":command,"payload":body},sign(signer,command))

    async with AsyncClient(
        transport=ASGITransport(app=api),
        base_url="http://m40926-disposable",
    ) as http:
        async def send(data,sig,bearer=token):
            return await http.post(
                data["command"]["path"],json=data,headers={
                    "Authorization":"Bearer "+bearer,
                    "X-FR-Signature":sig,
                },
            )
        sample,sample_sig=envelope(token,"DRAFT",payload)
        assert (await send(sample,"invalid-signature")).status_code==401
        bad={**sample,"payload":{**payload,"price":"74.96"}}
        assert (await send(bad,sample_sig)).status_code==401
        wrong_tenant={**sample,"command":{
            **sample["command"],"tenant_id":str(uuid4()),
        }}
        assert (await send(wrong_tenant,sample_sig)).status_code==401
        other,other_sig=envelope(
            member,"DRAFT",payload,signer=member_key
        )
        assert (await send(other,other_sig,bearer=member)).status_code==401
        good=await send(sample,sample_sig)
        assert good.status_code==201,(good.status_code,good.text)
        assert (await send(sample,sample_sig)).status_code==401
        campaign=good.json()["campaign_id"]
        print("M40926_ED25519_GUARDIAN_ASGI_DRAFT=PASS")

        def transition_body(action,revision):
            return {
                "campaign_id":campaign,"expected_revision":revision,
                "action":action,
                "reason":"Dupla custodia somente no ambiente descartavel",
            }
        pub,pub_sig=envelope(
            token,"PUBLISH",transition_body("PUBLISH",1)
        )
        pub_resp=await send(pub,pub_sig)
        assert pub_resp.status_code==200,(pub_resp.status_code,pub_resp.text)
        assert pub_resp.json()["state"]=="PUBLISHED"
        cancel,cancel_sig=envelope(
            token,"CANCEL",transition_body("CANCEL",2)
        )
        can_resp=await send(cancel,cancel_sig)
        assert can_resp.status_code==200,(can_resp.status_code,can_resp.text)
        assert can_resp.json()["state"]=="CANCELED"
        print("M40926_DRAFT_PUBLISH_CANCEL_WITH_TWO_SEALS=PASS")

        # Adversary: stolen issuer SQL + app SQL + Master bearer without
        # independent guardian credential cannot consume SQL approval.
        def deny_sql(connection,query,args,marker):
            try:
                with connection.transaction():
                    connection.execute(query,args)
            except psycopg.Error as e:
                assert e.sqlstate=="42501",(marker,e.sqlstate)
            else:
                raise AssertionError("M40926_UNAUTHORIZED_"+marker)

        issued_cap=secrets.token_urlsafe(48)
        fingerprint=conn.execute(
            "SELECT m40924.draft_digest(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            params,
        ).fetchone()[0]
        expiry=datetime.now(timezone.utc)+timedelta(seconds=15)
        values=(
            sha256(issued_cap.encode()).hexdigest(),
            sha256(token.encode()).hexdigest(),master,tenant,"DRAFT",
            None,0,fingerprint,expiry,
        )
        with psycopg.connect(issuer_dsn,autocommit=True) as issuer:
            issuer.execute("SET ROLE m40925_issuer_role")
            issuer.execute(
                "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                values,
            )
            deny_sql(
                issuer,
                "INSERT INTO m40926.seals ("+GUARD_COLUMNS+") "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                values,"ISSUER_FORGED_SEAL",
            )
            deny_sql(
                issuer,"SET ROLE m40926_guardian_writer",(),
                "ISSUER_ESCALATION",
            )
        sql=(
            "SELECT * FROM m40924.gated_draft("
            "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        )
        with psycopg.connect(app_dsn,autocommit=True) as app:
            app.execute("SET ROLE frcaixinha_app_role")
            app.execute("SELECT set_config('app.current_role','MASTER',false)")
            app.execute("SELECT set_config('app.current_user_id',%s,false)",
                        (str(master),))
            deny_sql(app,sql,(issued_cap,token,*params),
                     "ISSUER_PLUS_APP_PLUS_TOKEN_NO_SEAL")
            deny_sql(app,"ALTER TABLE m40924.approvals "
                     "DISABLE TRIGGER m40926_guardian_fence",(),
                     "APP_DISABLE_TRIGGER")
        assert conn.execute(
            "SELECT consumed_at FROM m40924.approvals "
            "WHERE approval_digest=%s",
            (values[0],),
        ).fetchone()==(None,)
        print("M40926_STOLEN_ISSUER_APP_BEARER_WITHOUT_GUARDIAN=DENIED")

        # A guardian credential without the issuer also cannot create a
        # consumable approval row. Its insert-only seal is not sufficient.
        with psycopg.connect(guardian_dsn,autocommit=True) as guardian:
            guardian.execute("SET ROLE m40926_guardian_writer")
            deny_sql(
                guardian,
                "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                values,"GUARDIAN_FORGED_ISSUER",
            )
        print("M40926_STOLEN_GUARDIAN_APP_BEARER_NO_ISSUER=DENIED")

        # Audit error MUST undo both approval and seal consumption.
        audit_data,audit_sig=envelope(token,"DRAFT",payload)
        conn.execute(
            "ALTER TABLE m40920.audit ADD CONSTRAINT m40926_ci_fail_audit "
            "CHECK (false) NOT VALID"
        )
        err=await send(audit_data,audit_sig)
        assert err.status_code==503,(err.status_code,err.text)
        conn.execute(
            "ALTER TABLE m40920.audit DROP CONSTRAINT m40926_ci_fail_audit"
        )
        assert (await send(audit_data,audit_sig)).status_code==401
        both=conn.execute(
            "SELECT a.consumed_at,s.consumed_at FROM m40924.approvals AS a "
            "JOIN m40926.seals AS s USING(approval_digest) "
            "WHERE a.operation='DRAFT' AND a.consumed_at IS NULL "
            "AND s.consumed_at IS NULL "
            "ORDER BY a.expires_at DESC LIMIT 1"
        ).fetchone()
        assert both==(None,None)
        print("M40926_AUDIT_FAILURE_ROLLS_BACK_BOTH_CONSUMPTIONS=PASS")

        # Six identical signed HTTP commands: only one Ed25519 nonce and
        # one issuer/guardian pair can reach the SQL writer.
        concurrent,conc_sig=envelope(token,"DRAFT",payload)
        replies=await asyncio.gather(*[
            send(concurrent,conc_sig) for _ in range(6)
        ])
        codes=[x.status_code for x in replies]
        assert codes.count(201)==1,codes
        assert codes.count(401)==5,codes
        print("M40926_CONCURRENT_DUAL_APPROVAL_ONE_OF_SIX=PASS")

        # Revoking Master prevents a valid Ed25519 request even if both
        # SQL approvals were inserted by the gateway.
        revoked,rev_sig=envelope(token,"DRAFT",payload)
        conn.execute(
            "UPDATE m40910.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",(sha256(token.encode()).hexdigest(),),
        )
        assert (await send(revoked,rev_sig)).status_code==401
        print("M40926_REVOKED_MASTER_DUAL_APPROVAL=DENIED")

        # Deliberate NO-GO: the three leaked SQL logins + a valid Master
        # bearer can insert BOTH approvals without any Ed25519 signature.
        second=secrets.token_urlsafe(48)
        conn.execute(
            "INSERT INTO m40910.sessions("
            "token_digest,user_id,active_role,tenant_id,expires_at,revoked_at)"
            " VALUES (%s,%s,'MASTER',%s,%s,NULL)",
            (sha256(second.encode()).hexdigest(),master,tenant,
             datetime.now(timezone.utc)+timedelta(minutes=30)),
        )
        forged=secrets.token_urlsafe(48)
        forged_values=(
            sha256(forged.encode()).hexdigest(),
            sha256(second.encode()).hexdigest(),
            master,tenant,"DRAFT",None,0,fingerprint,
            datetime.now(timezone.utc)+timedelta(seconds=15),
        )
        with psycopg.connect(issuer_dsn,autocommit=True) as issuer:
            issuer.execute("SET ROLE m40925_issuer_role")
            issuer.execute(
                "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",forged_values,
            )
        with psycopg.connect(guardian_dsn,autocommit=True) as guardian:
            guardian.execute("SET ROLE m40926_guardian_writer")
            guardian.execute(
                "INSERT INTO m40926.seals ("+GUARD_COLUMNS+") "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",forged_values,
            )
        with psycopg.connect(app_dsn,autocommit=True) as app:
            app.execute("SET ROLE frcaixinha_app_role")
            bypass=app.execute(
                sql,(forged,second,*params),
            ).fetchone()
            assert bypass[1:]==(1,"DRAFT")
        print("M40926_ALL_SQL_CREDENTIALS_AND_BEARER=NO_GO_BYPASS")

    assert conn.execute(
        "SELECT action,revision FROM m40920.audit "
        "WHERE campaign_id=%s ORDER BY revision",
        (UUID(campaign),),
    ).fetchall()==[("DRAFT",1),("PUBLISHED",2),("CANCELED",3)]
    print("M40926_PRIVATE_KEYS_AND_SIGNATURES_NOT_SENT_TO_SQL=PASS")
    print("M40926_CUSTODY_BOTH_SQL_LOGINS_IN_ONE_PROCESS=NOT_REMEDIATED")
    print("M40926_REAL_FASTAPI_VAULT_HSM_DEVICE_ENROLLMENT=NOT_ATTESTED")
    print("M40926_ORIGINAL_GUC_SPOOF=NOT_REMEDIATED")

def main() -> int:
    try:
        require_disposable()
        from m39067_postgres18_disposable_runtime import restricted_connection
        with restricted_connection() as conn:
            asyncio.run(proof(conn))
    except Exception as exc:
        import traceback
        frames=traceback.extract_tb(exc.__traceback__)
        last=frames[-1] if frames else None
        print("M40926_FAILURE_SITE="+
              (last.name+":"+str(last.lineno) if last else "unknown"))
        if getattr(exc,"sqlstate",None):
            print("M40926_SQLSTATE="+str(exc.sqlstate))
        print("M40926_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40926_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40926_ORIGINAL_ACL_CHANGES=NONE")
        print("M40926_MIGRATIONS=NONE")
        print("M40926_LOCAL_DB_WRITES=NONE")
        print("M40926_SERVICE_RESTARTS=NONE")
        print("M40926_PIX_REAL=OFF")
        print("M40926_PAGAMENTOS_REAIS=OFF")
        print("M40926_ATIVACAO_REAL=OFF")
        print("M40926_PRODUCTION=BLOCKED")
    print("M40926_STATUS=PASS_SYNTHETIC_WITH_EXPLICIT_NO_GO")
    return 0

if __name__=="__main__":
    sys.exit(main())
