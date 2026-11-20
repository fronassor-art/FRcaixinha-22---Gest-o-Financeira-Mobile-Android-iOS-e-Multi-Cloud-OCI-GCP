#!/usr/bin/env python3
"""M40927: synthetic gateway uses a separate guardian UNIX-socket process.

The FastAPI fixture holds ONLY issuer/app DSNs + socket locator. Guardian
child holds ONLY guardian DSN + public Ed25519 keys. The CI harness can
bootstrap all three roles and remains privileged; NOT production isolation.
"""
from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from uuid import UUID,uuid4

ROOT=Path(__file__).resolve().parents[2]
WORKER=ROOT/"backend/tests/m40927_guardian_worker_disposable.py"
ISSUER_COLS=(
    "approval_digest,session_digest,actor_id,tenant_id,operation,"
    "campaign_id,expected_revision,body_digest,expires_at"
)

def require_disposable() -> None:
    from m40926_dual_custody_master_disposable import require_disposable as prior
    prior()
    if os.environ.get("CI_M40927_DISPOSABLE")!="1":
        raise RuntimeError("M40927_CI_DISPOSABLE_ONLY")

def guardian_call(socket_path,command,payload,signature):
    request=json.dumps(
        {"command":command,"payload":payload,"signature":signature},
        sort_keys=True,separators=(",",":"),allow_nan=False
    ).encode("utf-8")
    if len(request)>12000:
        raise ValueError("M40927_LARGE_COMMAND")
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
        client.settimeout(3)
        client.connect(socket_path)
        client.sendall(request)
        client.shutdown(socket.SHUT_WR)
        reply=bytearray()
        while len(reply)<2048:
            part=client.recv(2048)
            if not part:
                break
            reply.extend(part)
        if len(reply)>=2048:
            raise ValueError("M40927_GUARDIAN_OVERSIZED_RESPONSE")
    answer=json.loads(reply.decode("utf-8"))
    if not isinstance(answer,dict) or not answer.get("ok"):
        return None
    cap=answer.get("capability")
    if not isinstance(cap,str) or not 32<=len(cap)<=256:
        raise ValueError("M40927_INVALID_CAPABILITY")
    return cap

def app_factory(*,issuer_dsn,app_dsn,guardian_socket_path):
    """No guardian DSN or public-key registry is accepted by this gateway."""
    import psycopg
    from fastapi import Body,FastAPI,Header
    from fastapi.responses import JSONResponse
    from m40923_offdb_master_action_gate import (
        PATHS,body_digest,
    )
    from m40925_signed_master_sql_bridge_disposable import parse_arguments

    api=FastAPI(title="M40927 isolated guardian worker laboratory")

    def respond(status):
        return JSONResponse(
            {"detail":"Unauthorized" if status==401 else "Unavailable"},
            status_code=status,headers={"Cache-Control":"no-store"},
        )

    def execute(path,data,authorization,signature):
        if (not authorization or not authorization.startswith("Bearer ")
            or not signature or not isinstance(data,dict)
            or set(data)!={"command","payload"}):
            return respond(401)
        token=authorization[len("Bearer "):]
        if not (32<=len(token)<=256 and token.isascii()):
            return respond(401)
        command,payload=data["command"],data["payload"]
        if not isinstance(command,dict) or not isinstance(payload,dict):
            return respond(401)
        try:
            action=command["action"]
            if (action not in PATHS or PATHS[action]!=path
                or command["session_digest"]!=sha256(
                    token.encode("ascii")).hexdigest()
                or command["body_digest"]!=body_digest(payload)):
                return respond(401)
            params=parse_arguments(action,payload,command)
            # Guardian independently verifies Ed25519 and derives the SQL
            # canonical fingerprint. No fallback to direct app/issuer SQL.
            capability=guardian_call(
                guardian_socket_path,command,payload,signature,
            )
            if not capability:
                return respond(401)
            digest=sha256(capability.encode("ascii")).hexdigest()
            with psycopg.connect(issuer_dsn,autocommit=True) as issuer:
                issuer.execute("SET ROLE m40925_issuer_role")
                if action=="DRAFT":
                    fingerprint=issuer.execute(
                        "SELECT m40924.draft_digest("
                        "%s,%s,%s,%s,%s,%s,%s,%s,%s)",params,
                    ).fetchone()[0]
                else:
                    fingerprint=issuer.execute(
                        "SELECT m40924.transition_digest("
                        "%s,%s,%s,%s)",params,
                    ).fetchone()[0]
                issuer.execute(
                    "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        digest,command["session_digest"],
                        UUID(command["actor_id"]),
                        UUID(command["tenant_id"]),action,
                        UUID(command["campaign_id"])
                        if command["campaign_id"] else None,
                        command["expected_revision"],fingerprint,
                        datetime.fromtimestamp(
                            command["expires_at"],timezone.utc
                        ),
                    ),
                )
            with psycopg.connect(app_dsn,autocommit=True) as app:
                app.execute("SET ROLE frcaixinha_app_role")
                if action=="DRAFT":
                    result=app.execute(
                        "SELECT * FROM m40924.gated_draft("
                        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (capability,token,*params),
                    ).fetchone()
                else:
                    result=app.execute(
                        "SELECT * FROM m40924.gated_transition("
                        "%s,%s,%s,%s,%s,%s)",
                        (capability,token,*params),
                    ).fetchone()
            return JSONResponse(
                {"campaign_id":str(result[0]),"revision":result[1],
                 "state":result[2]},
                status_code=201 if action=="DRAFT" else 200,
                headers={"Cache-Control":"no-store"},
            )
        except (KeyError,ValueError,TypeError,OverflowError):
            return respond(401)
        except (OSError,TimeoutError,ConnectionError):
            return respond(503)
        except psycopg.Error as exc:
            return respond(401 if exc.sqlstate in ("42501","P0001") else 503)

    @api.post("/master/saas-promotions/draft")
    def draft(
        data:dict=Body(...),
        authorization:str|None=Header(default=None),
        x_fr_signature:str|None=Header(default=None),
    ):
        return execute(
            "/master/saas-promotions/draft",data,authorization,x_fr_signature,
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
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,PublicFormat,
    )
    from httpx import ASGITransport,AsyncClient
    from psycopg.conninfo import make_conninfo
    from m40900_sql113_acl_fence_disposable import run as fence
    from m40920_master_token_writes_disposable import install_broker
    from m40921_saas_broker_role_split_disposable import split_broker_roles
    from m40922_saas_session_owner_disposable import separate_session_custody
    from m40924_master_one_time_sql_gate_disposable import install_gate
    from m40925_signed_master_sql_bridge_disposable import (
        install_issuer,parse_arguments,
    )
    from m40926_dual_custody_master_disposable import install_guardian
    from m40923_offdb_master_action_gate import PATHS,body_digest,sign

    fence(conn)
    install_broker(conn)
    split_broker_roles(conn)
    separate_session_custody(conn)
    install_gate(conn)
    install_issuer(conn)
    install_guardian(conn)
    # Function EXECUTE is not enough without USAGE on its containing schema.
    # This isolated role still cannot read approvals or execute Master writes.
    conn.execute(
        "GRANT USAGE ON SCHEMA m40924 TO m40926_guardian_writer"
    )
    conn.execute(
        "GRANT EXECUTE ON FUNCTION "
        "m40924.draft_digest(character varying,character varying,uuid,"
        "numeric,text,text,timestamp with time zone,timestamp with time zone,text)"
        " TO m40926_guardian_writer"
    )
    conn.execute(
        "GRANT EXECUTE ON FUNCTION "
        "m40924.transition_digest(uuid,integer,text,text) "
        "TO m40926_guardian_writer"
    )

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
    for t,role in ((token,"MASTER"),(member,"TENANT_MEMBER")):
        conn.execute(
            "INSERT INTO m40910.sessions("
            "token_digest,user_id,active_role,tenant_id,expires_at,revoked_at)"
            " VALUES (%s,%s,%s,%s,%s,NULL)",
            (sha256(t.encode()).hexdigest(),master,role,tenant,
             now+timedelta(minutes=30)),
        )
    root=os.environ["CI_PROMOTIONS_DATABASE_URL"]
    issuer_dsn=make_conninfo(
        root,user="m40925_issuer_login",
        password="synthetic-m40925-only-issuer-login",
    )
    app_dsn=make_conninfo(
        root,user="m40910_ci_login",
        password="synthetic-m40910-only-no-real-secret",
    )
    guardian_dsn=make_conninfo(
        root,user="m40926_guardian_login",
        password="m40926-only-disposable-guardian",
    )
    key=Ed25519PrivateKey.generate()
    member_key=Ed25519PrivateKey.generate()
    public={
        (str(master),str(tenant),sha256(token.encode()).hexdigest()):
            key.public_key(),
        (str(master),str(tenant),sha256(member.encode()).hexdigest()):
            member_key.public_key(),
    }
    registry={}
    for scope,pub in public.items():
        encoded=pub.public_bytes(Encoding.Raw,PublicFormat.Raw)
        registry["|".join(scope)]=base64.urlsafe_b64encode(
            encoded
        ).decode("ascii").rstrip("=")

    payload={
        "tier":"ESSENCIAL","period":"MONTHLY",
        "version":str(version),"price":"76.42",
        "title":"Custodia por processo separado",
        "benefit":"Campanha ficticia sem dinheiro ou cliente real",
        "start":(now-timedelta(minutes=1)).isoformat(),
        "end":(now+timedelta(days=5)).isoformat(),
        "reason":"Assinatura de dispositivo exigida no processo guardiao",
    }
    args=parse_arguments("DRAFT",payload,{"action":"DRAFT"})
    def envelope(bearer,action,body,*,signer=key):
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
        return ({"command":command,"payload":body},sign(signer,command))

    with tempfile.TemporaryDirectory(prefix="m40927_",dir="/tmp") as tmp:
        sock_path=str(Path(tmp)/"guardian.sock")
        child_env={
            "PATH":os.environ.get("PATH",""),
            "PYTHONDONTWRITEBYTECODE":"1",
            "GITHUB_ACTIONS":"true",
            "FRCAIXINHA_CI_ISOLATED":"1",
            "CI_M40927_GUARDIAN_ONLY":"1",
            "CI_M40927_GUARDIAN_DSN":guardian_dsn,
            "CI_M40927_PUBLIC_REGISTRY":json.dumps(
                registry,separators=(",",":"),
            ),
            "PIX_REAL":"OFF",
            "PAGAMENTOS_REAIS":"OFF",
            "ATIVACAO_REAL":"OFF",
        }
        assert all(secret not in child_env for secret in (
            "CI_PROMOTIONS_DATABASE_URL","CI_M40927_APP_DSN",
            "CI_M40927_ISSUER_DSN","CI_M40927_PRIVATE_KEY",
        ))
        proc=subprocess.Popen(
            [sys.executable,"-B",str(WORKER),sock_path],
            env=child_env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            text=True,
        )
        try:
            for _ in range(120):
                if os.path.exists(sock_path):
                    break
                if proc.poll() is not None:
                    raise RuntimeError(
                        "M40927_GUARDIAN_EXITED_BEFORE_SOCKET"
                    )
                time.sleep(0.05)
            else:
                raise RuntimeError("M40927_GUARDIAN_NOT_READY")
            api=app_factory(
                issuer_dsn=issuer_dsn,
                app_dsn=app_dsn,
                guardian_socket_path=sock_path,
            )
            print("M40927_GUARDIAN_SEPARATE_OS_PROCESS=PASS")
            print("M40927_GATEWAY_NO_GUARDIAN_DSN=PASS_FIXTURE")
            print("M40927_GUARDIAN_NO_APP_ISSUER_ROOT_DSN=PASS_FIXTURE")
            async with AsyncClient(
                transport=ASGITransport(app=api),
                base_url="http://fixture-m40927",
            ) as http:
                async def send(data,sig,bearer=token):
                    return await http.post(
                        data["command"]["path"],json=data,headers={
                            "Authorization":"Bearer "+bearer,
                            "X-FR-Signature":sig,
                        },
                    )
                first,sig=envelope(token,"DRAFT",payload)
                assert (await send(first,"bad-signature")).status_code==401
                assert (await send(first,sign(
                    member_key,first["command"],
                ))).status_code==401
                assert (await send({
                    **first,"payload":{**payload,"price":"999.01"},
                },sig)).status_code==401
                assert (await send({
                    **first,"command":{
                        **first["command"],"tenant_id":str(uuid4()),
                    },
                },sig)).status_code==401
                member_req,msig=envelope(
                    member,"DRAFT",payload,signer=member_key,
                )
                assert (await send(member_req,msig,member)).status_code==401
                draft=await send(first,sig)
                assert draft.status_code==201,(draft.status_code,draft.text)
                assert (await send(first,sig)).status_code==401
                campaign=draft.json()["campaign_id"]

                def transition_body(action,revision):
                    return {
                        "campaign_id":campaign,"expected_revision":revision,
                        "action":action,"reason":
                            "Assinatura e processo guardiao isolado em CI",
                    }
                pub,pub_sig=envelope(
                    token,"PUBLISH",transition_body("PUBLISH",1),
                )
                published=await send(pub,pub_sig)
                assert published.status_code==200,(published.status_code,
                                                  published.text)
                assert published.json()["state"]=="PUBLISHED"
                cancel,cancel_sig=envelope(
                    token,"CANCEL",transition_body("CANCEL",2),
                )
                canceled=await send(cancel,cancel_sig)
                assert canceled.status_code==200,(canceled.status_code,
                                                 canceled.text)
                assert canceled.json()["state"]=="CANCELED"
                print("M40927_ASGI_SIGNED_DRAFT_PUBLISH_CANCEL=PASS")
                print("M40927_INVALID_SIGNATURE_SCOPE_REPLAY_MEMBER=DENIED")

                # Attacker has issuer login + app login + valid Master bearer.
                # Guardian socket refuses unsigned forged seal requests.
                forged=secrets.token_urlsafe(48)
                fingerprint=conn.execute(
                    "SELECT m40924.draft_digest(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    args,
                ).fetchone()[0]
                values=(
                    sha256(forged.encode()).hexdigest(),
                    sha256(token.encode()).hexdigest(),
                    master,tenant,"DRAFT",None,0,fingerprint,
                    datetime.now(timezone.utc)+timedelta(seconds=15),
                )
                with psycopg.connect(issuer_dsn,autocommit=True) as issuer:
                    issuer.execute("SET ROLE m40925_issuer_role")
                    issuer.execute(
                        "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",values,
                    )
                with psycopg.connect(app_dsn,autocommit=True) as app:
                    app.execute("SET ROLE frcaixinha_app_role")
                    try:
                        with app.transaction():
                            app.execute(
                                "SELECT * FROM m40924.gated_draft("
                                "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                                (forged,token,*args),
                            )
                    except psycopg.Error as exc:
                        assert exc.sqlstate=="42501",exc.sqlstate
                    else:
                        raise AssertionError("M40927_ISSUER_APP_BEARER_BYPASS")
                unsigned,envelope_sig=envelope(token,"DRAFT",payload)
                assert guardian_call(
                    sock_path,unsigned["command"],payload,
                    "not-a-real-signature",
                ) is None
                print("M40927_STOLEN_APP_ISSUER_MASTER_WITHOUT_SIGNED_SEAL=DENIED")

                concurrent,conc_sig=envelope(token,"DRAFT",payload)
                codes=[res.status_code for res in await asyncio.gather(*[
                    send(concurrent,conc_sig) for _ in range(6)
                ])]
                assert codes.count(201)==1,codes
                assert codes.count(401)==5,codes
                print("M40927_GUARDIAN_PROCESS_NONCE_ONE_OF_SIX=PASS")

                revoked,rev_sig=envelope(token,"DRAFT",payload)
                conn.execute(
                    "UPDATE m40910.sessions SET revoked_at="
                    "pg_catalog.clock_timestamp() WHERE token_digest=%s",
                    (sha256(token.encode()).hexdigest(),),
                )
                assert (await send(revoked,rev_sig)).status_code==401
                print("M40927_REVOKED_MASTER=DENIED")

                # Deliberate NO-GO with ALL THREE compromised SQL identities:
                # direct owner-like access to guardian login bypasses ASGI.
                second=secrets.token_urlsafe(48)
                conn.execute(
                    "INSERT INTO m40910.sessions("
                    "token_digest,user_id,active_role,tenant_id,"
                    "expires_at,revoked_at) VALUES "
                    "(%s,%s,'MASTER',%s,%s,NULL)",
                    (
                        sha256(second.encode()).hexdigest(),master,tenant,
                        datetime.now(timezone.utc)+timedelta(minutes=30),
                    ),
                )
                malicious=secrets.token_urlsafe(48)
                evil=(
                    sha256(malicious.encode()).hexdigest(),
                    sha256(second.encode()).hexdigest(),
                    master,tenant,"DRAFT",None,0,fingerprint,
                    datetime.now(timezone.utc)+timedelta(seconds=15),
                )
                with psycopg.connect(issuer_dsn,autocommit=True) as issuer:
                    issuer.execute("SET ROLE m40925_issuer_role")
                    issuer.execute(
                        "INSERT INTO m40924.approvals ("+ISSUER_COLS+") "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",evil,
                    )
                with psycopg.connect(guardian_dsn,autocommit=True) as stolen:
                    stolen.execute("SET ROLE m40926_guardian_writer")
                    stolen.execute(
                        "INSERT INTO m40926.seals ("+ISSUER_COLS+") "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",evil,
                    )
                with psycopg.connect(app_dsn,autocommit=True) as stolen:
                    stolen.execute("SET ROLE frcaixinha_app_role")
                    result=stolen.execute(
                        "SELECT * FROM m40924.gated_draft("
                        "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (malicious,second,*args),
                    ).fetchone()
                assert result[1:]==(1,"DRAFT")
                print("M40927_STOLEN_ALL_THREE_SQL_LOGINS=NO_GO_BYPASS")

                # A gateway with no guardian cannot silently write directly.
                dead_request,dead_sig=envelope(
                    second,"DRAFT",payload,signer=key,
                )
                # Stop worker without altering a real service.
                proc.terminate()
                proc.wait(timeout=5)
                unavailable=await send(dead_request,dead_sig,second)
                assert unavailable.status_code==503,(
                    unavailable.status_code,unavailable.text,
                )
                print("M40927_GUARDIAN_UNAVAILABLE=FAIL_CLOSED_503")

            assert conn.execute(
                "SELECT action,revision FROM m40920.audit "
                "WHERE campaign_id=%s ORDER BY revision",
                (UUID(campaign),),
            ).fetchall()==[("DRAFT",1),("PUBLISHED",2),("CANCELED",3)]
            print("M40927_PUBLIC_KEYS_ONLY_GUARDIAN_SQL=PASS")
            print("M40927_SAME_OS_UID_SOCKET_HIJACK=NOT_REMEDIATED_NO_GO")
            print("M40927_ORCHESTRATOR_ROOT_FIXTURE=NOT_PRODUCTION_ISOLATION")
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                out,err=proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out,err=proc.communicate(timeout=5)
            if "M40927_GUARDIAN_HAS_NO_ROOT_ISSUER_APP_DSN=PASS" not in out:
                raise AssertionError("M40927_WORKER_ENV_ISOLATION_NOT_PROVED")
            if "M40927_GUARDIAN_PUBLIC_KEYS_ONLY=PASS" not in out:
                raise AssertionError("M40927_WORKER_KEY_BOUNDARY_NOT_PROVED")
            if proc.returncode not in (-15,-9):
                raise AssertionError(
                    "M40927_WORKER_EXIT_"+str(proc.returncode)+":"+err[-200:]
                )

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
        print(
            "M40927_FAILURE_SITE="+
            (last.name+":"+str(last.lineno) if last else "unknown")
        )
        if getattr(exc,"sqlstate",None):
            print("M40927_SQLSTATE="+str(exc.sqlstate))
        print("M40927_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M40927_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED")
        print("M40927_ORIGINAL_ACL_CHANGES=NONE")
        print("M40927_MIGRATIONS=NONE")
        print("M40927_LOCAL_DB_WRITES=NONE")
        print("M40927_SERVICE_RESTARTS=NONE")
        print("M40927_RUNTIME_RELOAD=NONE")
        print("M40927_PIX_REAL=OFF")
        print("M40927_PAGAMENTOS_REAIS=OFF")
        print("M40927_ATIVACAO_REAL=OFF")
        print("M40927_PRODUCTION=BLOCKED")
    print("M40927_STATUS=PASS_SYNTHETIC_GUARDIAN_WITH_NO_GO")
    return 0

if __name__=="__main__":
    sys.exit(main())
