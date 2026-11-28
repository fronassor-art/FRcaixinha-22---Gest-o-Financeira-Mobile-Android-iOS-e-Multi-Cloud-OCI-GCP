"""M41610 dual identity proof: existing disposable PG18 fixture only."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import os
import secrets
from uuid import uuid4, UUID

V2="m40700.issue_bound_v2(text,uuid,uuid,bigint,text,uuid,text,bigint,text)"
V3="m40700.issue_bound_v3(text,uuid,uuid,bigint,text,uuid,text,bigint,text,uuid,text)"


def install_gate(owner, identity_key):
    if (os.environ.get("GITHUB_ACTIONS")!="true"
            or os.environ.get("FRCAIXINHA_CI_ISOLATED")!="1"
            or os.environ.get("CI_M41150_DISPOSABLE")!="1"
            or any(os.environ.get(k)!="OFF" for k in ("PIX_REAL","PAGAMENTOS_REAIS","ATIVACAO_REAL"))):
        raise RuntimeError("M41610_DISPOSABLE_ONLY")
    if owner.info.dbname!="fr_m40700_disposable_ci" or owner.info.port!=55439 or owner.info.host!="127.0.0.1":
        raise RuntimeError("M41610_WRONG_DATABASE")
    if type(identity_key) is not bytes or len(identity_key)!=32:
        raise ValueError("M41610_INVALID_KEY")
    owner.execute("""
        CREATE TABLE m40700.identity_authorization_secret(
          singleton boolean PRIMARY KEY CHECK(singleton),
          key bytea NOT NULL CHECK(octet_length(key)=32)
        )
    """)
    owner.execute("ALTER TABLE m40700.identity_authorization_secret OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON m40700.identity_authorization_secret FROM PUBLIC,m40680_auth,m40650_app")
    owner.execute("INSERT INTO m40700.identity_authorization_secret VALUES(true,%s)",(identity_key,))
    owner.execute("""
        CREATE FUNCTION m40700.issue_bound_v3(
          p_digest text,p_tenant uuid,p_nonce uuid,p_expiry bigint,p_scope text,
          p_user uuid,p_role text,p_generation bigint,p_proof text,
          p_session uuid,p_identity_proof text
        ) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $body$
        DECLARE
          v_key bytea;
          v_expected text;
          v_payload text;
        BEGIN
          IF session_user<>'m40680_auth_login'
             OR p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
             OR p_tenant IS NULL OR p_nonce IS NULL OR p_session IS NULL
             OR p_user IS NULL OR p_generation IS NULL OR p_generation<0
             OR p_role IS DISTINCT FROM 'TENANT_ADMIN'
             OR p_scope IS DISTINCT FROM 'READ_ENTRIES'
             OR p_expiry IS NULL
             OR p_expiry<=pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint
             OR p_expiry>pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint+30
             OR p_identity_proof IS NULL OR p_identity_proof !~ '^[0-9a-f]{64}$'
          THEN RETURN NULL; END IF;
          SELECT key INTO v_key FROM m40700.identity_authorization_secret WHERE singleton=true;
          IF NOT FOUND THEN RETURN NULL; END IF;
          v_payload:='FRF-M41610|v1|'||p_digest||'|'||p_session::text||'|'||
                     p_tenant::text||'|'||p_nonce::text||'|'||p_expiry::text||'|'||
                     p_scope||'|'||p_user::text||'|'||p_role||'|'||p_generation::text;
          v_expected:=pg_catalog.encode(
             m40700.hmac(pg_catalog.convert_to(v_payload,'UTF8'),v_key,'sha256'),'hex');
          IF p_identity_proof<>v_expected THEN RETURN NULL; END IF;
          PERFORM 1 FROM m40650.sessions AS s
            WHERE s.id=p_session AND s.token_digest=p_digest AND s.user_id=p_user
              AND s.active_role=p_role AND s.active_tenant_id=p_tenant
              AND s.context_generation=p_generation AND s.revoked_at IS NULL
              AND s.expires_at>pg_catalog.clock_timestamp()
            FOR SHARE OF s;
          IF NOT FOUND THEN RETURN NULL; END IF;
          RETURN m40700.issue_bound_v2(p_digest,p_tenant,p_nonce,p_expiry,p_scope,
                                     p_user,p_role,p_generation,p_proof);
        END
        $body$
    """)
    owner.execute("ALTER FUNCTION "+V3+" OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON FUNCTION "+V3+" FROM PUBLIC,m40650_app")
    owner.execute("GRANT EXECUTE ON FUNCTION "+V3+" TO m40680_auth")
    owner.execute("REVOKE EXECUTE ON FUNCTION "+V2+" FROM m40680_auth")


def identity_proof(key, digest, session_id, tenant, nonce, expiry, scope, context):
    user,role,generation=context
    message=(f"FRF-M41610|v1|{digest}|{session_id}|{tenant}|{nonce}|{expiry}|"
             f"{scope}|{user}|{role}|{generation}").encode("ascii")
    return hmac.new(key,message,sha256).hexdigest()


async def exercise_dual_identity(*, owner, auth_dsn, app_dsn, key, fixture,
                                 provider, client, read_paths, path_a, admin_headers,
                                 second_headers, admin_id, admin_digest, admin_session_id,
                                 second_digest, second_session_id, tenant_a, tenant_b):
    import psycopg
    identity_key=secrets.token_bytes(32)
    assert identity_key!=bytes(key)
    install_gate(owner,identity_key)
    ctx=fixture.fixture_context(owner,second_digest)
    assert ctx[0]==admin_id and ctx[1]=="TENANT_ADMIN"
    frozen=(second_digest,second_session_id,tenant_a,ctx)
    with psycopg.connect(auth_dsn,autocommit=True) as auth:
        auth.execute("SET ROLE m40680_auth")
        assert not auth.execute("SELECT has_function_privilege(current_user,%s,'EXECUTE')",(V2,)).fetchone()[0]
        assert auth.execute("SELECT has_function_privilege(current_user,%s,'EXECUTE')",(V3,)).fetchone()[0]
        for sql in ("SELECT key FROM m40700.identity_authorization_secret",
                    "UPDATE m40700.identity_authorization_secret SET key=key",
                    "DELETE FROM m40700.identity_authorization_secret"):
            try:
                auth.execute(sql)
            except psycopg.errors.InsufficientPrivilege:
                pass
            else:
                raise AssertionError("M41610_IDENTITY_KEY_EXPOSED")
    with psycopg.connect(app_dsn,autocommit=True) as low:
        low.execute("SET ROLE m40650_app")
        assert not low.execute(
            "SELECT has_function_privilege(current_user,p.oid,'EXECUTE') FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='m40700' AND p.proname='issue_bound_v3'"
        ).fetchone()[0]
        try:
            low.execute("SELECT key FROM m40700.identity_authorization_secret")
        except psycopg.errors.InsufficientPrivilege:
            pass
        else:
            raise AssertionError("M41610_APP_IDENTITY_KEY_EXPOSED")
    try:
        fixture.issue_ticket(owner,auth_dsn,key,second_digest,tenant_a)
    except psycopg.errors.InsufficientPrivilege:
        pass
    else:
        raise AssertionError("M41610_LEGACY_ISSUER_STILL_CALLABLE")
    print("M41610_DUAL_KEY_ACL_LEGACY_ISSUER_DENIED=PASS")

    def submit(args, proof, second):
        digest,session_id,tenant,nonce,expiry,scope,context=args
        user,role,generation=context
        with psycopg.connect(auth_dsn,autocommit=True) as auth:
            auth.execute("SET ROLE m40680_auth")
            return auth.execute(
                "SELECT m40700.issue_bound_v3(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (digest,tenant,nonce,expiry,scope,user,role,generation,proof,session_id,second)
            ).fetchone()[0]

    def first(args):
        digest,_,tenant,nonce,expiry,scope,context=args
        return fixture.sign_context(key,digest,tenant,nonce,expiry,scope,context)

    def second(args):
        return identity_proof(identity_key,*args)

    def fresh_args():
        digest,session_id,tenant,context=frozen
        return (digest,session_id,tenant,uuid4(),
                int(datetime.now(timezone.utc).timestamp())+20,"READ_ENTRIES",context)

    args=fresh_args()
    proof,approval=first(args),second(args)
    assert submit(args,proof,None) is None
    assert submit(args,proof,"0"*64) is None
    assert submit(args,proof,proof) is None
    assert submit(args,"0"*64,approval) is None
    for index,value in ((0,admin_digest),(1,admin_session_id),(2,tenant_b),
                        (3,uuid4()),(4,args[4]+1),(5,"WRITE_TEST_ENTRY"),
                        (6,(admin_id,"TENANT_MEMBER",ctx[2])),(6,(admin_id,"TENANT_ADMIN",ctx[2]+1))):
        mutated=list(args)
        mutated[index]=value
        assert submit(tuple(mutated),first(tuple(mutated)),approval) is None
    wrong=list(args)
    wrong[1]=admin_session_id
    assert submit(tuple(wrong),first(tuple(wrong)),second(tuple(wrong))) is None
    expired=list(args)
    expired[4]=int(datetime.now(timezone.utc).timestamp())-1
    assert submit(tuple(expired),first(tuple(expired)),second(tuple(expired))) is None
    revoked=(admin_digest,admin_session_id,tenant_a,uuid4(),args[4],"READ_ENTRIES",
             fixture.fixture_context(owner,admin_digest))
    assert submit(revoked,first(revoked),second(revoked)) is None
    issued=await asyncio.gather(*(asyncio.to_thread(submit,args,proof,approval) for _ in range(2)))
    assert sum(ticket is not None for ticket in issued)==1
    assert submit(args,proof,approval) is None
    print("M41610_DUAL_PROOF_SCOPE_EXPIRY_REVOCATION_REPLAY=PASS")

    def issue_authorized(digest,tenant,nonce,scope):
        allowed_digest,session_id,allowed_tenant,context=frozen
        if (digest,tenant,scope)!=(allowed_digest,allowed_tenant,"READ_ENTRIES"):
            return None
        args=(digest,session_id,tenant,nonce,
              int(datetime.now(timezone.utc).timestamp())+20,scope,context)
        return submit(args,first(args),second(args))

    async def issue_ticket(session, *, scope, request_nonce):
        provider.issue_calls+=1
        digest=provider.session_digests.get(
            (session.verified_session_id,session.user_id,session.role,session.tenant_id))
        ticket=issue_authorized(digest,UUID(session.tenant_id),request_nonce,scope)
        if ticket:
            provider.last_ticket=ticket
        return ticket

    provider.issue_ticket=issue_ticket
    responses=await asyncio.gather(*(client.get(p,headers=second_headers) for p in read_paths))
    assert all(response.status_code==200 for response in responses)
    assert (await client.get(path_a,headers=admin_headers)).status_code==401
    assert (await client.get(path_a.replace(str(tenant_a),str(tenant_b),1),
                             headers=second_headers)).status_code==403
    owner.execute("DELETE FROM m40700.identity_authorization_secret")
    assert (await client.get(path_a,headers=second_headers)).status_code==401
    owner.execute("INSERT INTO m40700.identity_authorization_secret VALUES(true,%s)",(identity_key,))
    assert (await client.get(path_a,headers=second_headers)).status_code==200
    print("M41610_DUAL_PROOF_FASTAPI_SIX_READS_AND_KEY_LOSS=PASS")
    return issue_authorized
