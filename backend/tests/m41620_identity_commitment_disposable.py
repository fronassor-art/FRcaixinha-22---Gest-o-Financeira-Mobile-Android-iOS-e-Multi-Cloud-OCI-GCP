"""M41620: ephemeral commitment authority, existing disposable CI only."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import secrets
import socket
import subprocess
import sys
from threading import Lock
from time import time
from uuid import UUID, uuid4

from m41240_target_signer_disposable import (
    GATE, HEX, MAX_FRAME, TIMEOUT, allowed, process_credentials, receive_frame,
)
from m41610_identity_authorization_disposable import V2, V3

V4="m40700.issue_bound_v4(text,uuid,uuid,bigint,text,uuid,text,bigint,text,uuid,text)"
LIMIT=128
FIELDS=("digest","session","tenant","nonce","expiry","scope","user","role","generation")


def message(p):
    if type(p) is not dict or set(p)!=set(FIELDS):
        raise ValueError("M41620_FIELDS")
    for name in ("session","tenant","nonce","user"):
        if type(p[name]) is not str or str(UUID(p[name]))!=p[name] or UUID(p[name]).int==0:
            raise ValueError("M41620_UUID")
    if (type(p["digest"]) is not str or not HEX.fullmatch(p["digest"])
            or p["scope"]!="READ_ENTRIES" or p["role"]!="TENANT_ADMIN"
            or type(p["generation"]) is not int or not 0<=p["generation"]<2**63
            or type(p["expiry"]) is not int or not int(time())<p["expiry"]<=int(time())+30):
        raise ValueError("M41620_SCOPE")
    return ("FRF-M41620|v1|"+"|".join(str(p[k]) for k in FIELDS)).encode("ascii")


def commitment(p,token):
    if type(token) is not str or not HEX.fullmatch(token):
        raise ValueError("M41620_TOKEN")
    return sha256(message(p)+b"|"+token.encode("ascii")).hexdigest()


def worker(parent_pid,fd):
    if (not allowed() or os.getppid()!=parent_pid or parent_pid<=1
            or set(os.environ)-(set(GATE)|{"PYTHONDONTWRITEBYTECODE","LC_CTYPE"})):
        return 2
    expected=process_credentials(parent_pid)
    with socket.socket(fileno=fd) as ch:
        if ch.family!=socket.AF_UNIX or ch.getsockopt(socket.SOL_SOCKET,socket.SO_TYPE)!=socket.SOCK_SEQPACKET:
            return 2
        ch.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
        raw,cred=receive_frame(ch,MAX_FRAME)
        if cred!=expected:
            return 2
        frozen=json.loads(raw)
        if type(frozen) is not dict or set(frozen)!=(set(FIELDS)-{"nonce","expiry"}):
            return 2
        pending={}
        seen=set()
        ch.sendall(b"READY")
        while os.getppid()==parent_pid:
            raw,cred=receive_frame(ch,MAX_FRAME)
            if not raw:
                return 0
            response=b"DENIED"
            if cred==expected and os.getppid()==parent_pid:
                try:
                    request=json.loads(raw)
                    if type(request) is not dict or set(request)!={"op","request"}:
                        raise ValueError("M41620_PACKET")
                    p=request["request"]
                    canonical=message(p)
                    if any(p[k]!=v for k,v in frozen.items()):
                        raise ValueError("M41620_IDENTITY")
                    nonce=p["nonce"]
                    if request["op"]=="prepare" and nonce not in seen and len(seen)<LIMIT:
                        token=secrets.token_hex(32)
                        pending[nonce]=(canonical,token)
                        seen.add(nonce)
                        response=commitment(p,token).encode("ascii")
                    elif request["op"]=="release" and nonce in pending and pending[nonce][0]==canonical:
                        _,token=pending.pop(nonce)
                        response=token.encode("ascii")
                except (ValueError,TypeError,KeyError,OverflowError):
                    pass
            ch.sendall(response)
    return 2


class Authority:
    def __init__(self,frozen):
        if not allowed():
            raise RuntimeError("M41620_CI_ONLY")
        self.lock=Lock()
        self.channel,child=socket.socketpair(socket.AF_UNIX,socket.SOCK_SEQPACKET)
        self.proc=None
        try:
            for ch in (self.channel,child):
                ch.setsockopt(socket.SOL_SOCKET,socket.SO_PASSCRED,1)
            self.channel.settimeout(TIMEOUT)
            self.proc=subprocess.Popen(
                [sys.executable,"-B",__file__,"--worker",str(os.getpid()),str(child.fileno())],
                env={**GATE,"PYTHONDONTWRITEBYTECODE":"1"},
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                pass_fds=(child.fileno(),),close_fds=True,
            )
            child.close()
            if self.exchange(frozen)!=b"READY":
                raise RuntimeError("M41620_BOOTSTRAP_DENIED")
        except BaseException:
            self.close()
            raise
        finally:
            child.close()

    def exchange(self,packet):
        with self.lock:
            try:
                if self.proc is None or self.proc.poll() is not None:
                    raise RuntimeError("M41620_UNAVAILABLE")
                data=json.dumps(packet,separators=(",",":")).encode("ascii")
                if len(data)>MAX_FRAME or self.channel.send(data)!=len(data):
                    raise RuntimeError("M41620_UNAVAILABLE")
                reply,cred=receive_frame(self.channel,64)
                if cred!=process_credentials(self.proc.pid):
                    raise RuntimeError("M41620_UNAVAILABLE")
                return reply
            except (OSError,ValueError,RuntimeError):
                raise RuntimeError("M41620_UNAVAILABLE") from None

    def request(self,op,p):
        result=self.exchange({"op":op,"request":p}).decode("ascii")
        if result=="DENIED":
            return None
        if not HEX.fullmatch(result):
            raise RuntimeError("M41620_BAD_RESPONSE")
        return result

    def close(self):
        with self.lock:
            self.channel.close()
            if self.proc is not None:
                try:
                    self.proc.wait(timeout=TIMEOUT)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait(timeout=TIMEOUT)


def install(owner):
    if (not allowed() or owner.info.dbname!="fr_m40700_disposable_ci"
            or owner.info.port!=55439 or owner.info.host!="127.0.0.1"):
        raise RuntimeError("M41620_DISPOSABLE_ONLY")
    # Old proofs cannot be used via the issuer in this additional phase.
    owner.execute("REVOKE EXECUTE ON FUNCTION "+V3+" FROM m40680_auth")
    owner.execute("DELETE FROM m40700.identity_authorization_secret")
    owner.execute("""
        CREATE TABLE m40700.identity_commitments(
          nonce uuid PRIMARY KEY,
          commitment text UNIQUE NOT NULL CHECK(commitment ~ '^[0-9a-f]{64}$'),
          expiry bigint NOT NULL,
          consumed_at timestamptz
        )
    """)
    owner.execute("ALTER TABLE m40700.identity_commitments OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON m40700.identity_commitments FROM PUBLIC,m40680_auth,m40650_app")
    owner.execute("""
        CREATE FUNCTION m40700.issue_bound_v4(
          p_digest text,p_tenant uuid,p_nonce uuid,p_expiry bigint,p_scope text,
          p_user uuid,p_role text,p_generation bigint,p_proof text,
          p_session uuid,p_token text
        ) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $body$
        DECLARE v_hash text; v_ticket text;
        BEGIN
          IF session_user<>'m40680_auth_login'
             OR p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
             OR p_tenant IS NULL OR p_nonce IS NULL OR p_session IS NULL
             OR p_user IS NULL OR p_generation IS NULL OR p_generation<0
             OR p_role IS DISTINCT FROM 'TENANT_ADMIN'
             OR p_scope IS DISTINCT FROM 'READ_ENTRIES'
             OR p_token IS NULL OR p_token !~ '^[0-9a-f]{64}$'
             OR p_expiry IS NULL
             OR p_expiry<=pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint
             OR p_expiry>pg_catalog.floor(pg_catalog.date_part('epoch',pg_catalog.clock_timestamp()))::bigint+30
          THEN RETURN NULL; END IF;
          v_hash:=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(
             'FRF-M41620|v1|'||p_digest||'|'||p_session::text||'|'||p_tenant::text||'|'||
             p_nonce::text||'|'||p_expiry::text||'|'||p_scope||'|'||p_user::text||'|'||
             p_role||'|'||p_generation::text||'|'||p_token,'UTF8')),'hex');
          PERFORM 1 FROM m40700.identity_commitments
            WHERE nonce=p_nonce AND commitment=v_hash AND expiry=p_expiry
              AND consumed_at IS NULL FOR UPDATE;
          IF NOT FOUND THEN RETURN NULL; END IF;
          PERFORM 1 FROM m40650.sessions AS s
            WHERE s.id=p_session AND s.token_digest=p_digest AND s.user_id=p_user
              AND s.active_role=p_role AND s.active_tenant_id=p_tenant
              AND s.context_generation=p_generation AND s.revoked_at IS NULL
              AND s.expires_at>pg_catalog.clock_timestamp() FOR SHARE OF s;
          IF NOT FOUND THEN RETURN NULL; END IF;
          v_ticket:=m40700.issue_bound_v2(p_digest,p_tenant,p_nonce,p_expiry,p_scope,
                                         p_user,p_role,p_generation,p_proof);
          IF v_ticket IS NULL THEN RETURN NULL; END IF;
          UPDATE m40700.identity_commitments SET consumed_at=pg_catalog.clock_timestamp()
            WHERE nonce=p_nonce;
          RETURN v_ticket;
        END
        $body$
    """)
    owner.execute("ALTER FUNCTION "+V4+" OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON FUNCTION "+V4+" FROM PUBLIC,m40650_app")
    owner.execute("GRANT EXECUTE ON FUNCTION "+V4+" TO m40680_auth")


async def exercise_commitment(*,owner,auth_dsn,app_dsn,key,fixture,provider,client,
                              read_paths,path_a,admin_headers,second_headers,admin_id,
                              second_digest,second_session_id,tenant_a,tenant_b):
    import psycopg
    ctx=fixture.fixture_context(owner,second_digest)
    assert ctx[:2]==(admin_id,"TENANT_ADMIN")
    frozen=dict(digest=second_digest,session=str(second_session_id),tenant=str(tenant_a),
                scope="READ_ENTRIES",user=str(admin_id),role="TENANT_ADMIN",generation=ctx[2])
    install(owner)
    authority=Authority(frozen)
    try:
        for dsn,role in ((auth_dsn,"m40680_auth"),(app_dsn,"m40650_app")):
            with psycopg.connect(dsn,autocommit=True) as c:
                c.execute("SET ROLE "+role)
                for signature in (V2,V3,V4):
                    actual=c.execute(
                        "SELECT has_function_privilege(current_user,p.oid,'EXECUTE') "
                        "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname='m40700' AND p.proname=%s",
                        (signature.split(".")[1].split("(")[0],)
                    ).fetchone()[0]
                    assert actual==(role=="m40680_auth" and signature==V4)
                for sql in ("SELECT * FROM m40700.identity_commitments",
                            "INSERT INTO m40700.identity_commitments VALUES(gen_random_uuid(),'0',1,NULL)",
                            "UPDATE m40700.identity_commitments SET expiry=0",
                            "DELETE FROM m40700.identity_commitments"):
                    try:
                        c.execute(sql)
                    except psycopg.errors.InsufficientPrivilege:
                        pass
                    else:
                        raise AssertionError("M41620_COMMITMENT_ACL")
        assert owner.execute("SELECT count(*) FROM m40700.identity_authorization_secret").fetchone()[0]==0
        print("M41620_NO_SHARED_SECOND_KEY_LEGACY_AND_ACL=PASS")

        def packet(nonce=None):
            return {**frozen,"nonce":str(nonce or uuid4()),"expiry":int(time())+20}

        def first(p):
            return fixture.sign_context(key,p["digest"],UUID(p["tenant"]),UUID(p["nonce"]),
                       p["expiry"],p["scope"],(UUID(p["user"]),p["role"],p["generation"]))

        def submit(p,token,proof=None):
            with psycopg.connect(auth_dsn,autocommit=True) as c:
                c.execute("SET ROLE m40680_auth")
                return c.execute("SELECT m40700.issue_bound_v4(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (p["digest"],UUID(p["tenant"]),UUID(p["nonce"]),p["expiry"],p["scope"],
                     UUID(p["user"]),p["role"],p["generation"],first(p) if proof is None else proof,
                     UUID(p["session"]),token)).fetchone()[0]

        def register(p):
            digest=authority.request("prepare",p)
            assert digest
            owner.execute("INSERT INTO m40700.identity_commitments(nonce,commitment,expiry) VALUES(%s,%s,%s)",
                          (UUID(p["nonce"]),digest,p["expiry"]))
            return digest

        p=packet()
        assert submit(p,"0"*64) is None
        digest=register(p)
        assert authority.request("prepare",p) is None
        assert authority.request("release",{**p,"tenant":str(tenant_b)}) is None
        assert authority.request("prepare",{**packet(),"tenant":str(tenant_b)}) is None
        token=authority.request("release",p)
        assert token and commitment(p,token)==digest and token!=digest
        assert authority.request("release",p) is None
        assert submit(p,digest) is None
        assert submit(p,token,"0"*64) is None
        for patch in ({"tenant":str(tenant_b)},{"nonce":str(uuid4())},{"session":str(uuid4())},
                      {"user":str(uuid4())},{"expiry":p["expiry"]+1},{"scope":"WRITE_TEST_ENTRY"},
                      {"role":"TENANT_MEMBER"},{"generation":ctx[2]+1}):
            assert submit({**p,**patch},token) is None
        result=await asyncio.gather(*(asyncio.to_thread(submit,p,token) for _ in range(2)))
        assert sum(t is not None for t in result)==1
        assert submit(p,token) is None
        row=owner.execute("SELECT commitment,consumed_at IS NOT NULL FROM m40700.identity_commitments WHERE nonce=%s",
                          (UUID(p["nonce"]),)).fetchone()
        assert row==(digest,True)
        print("M41620_BOUND_SINGLE_RELEASE_CONCURRENT_SQL_CONSUMPTION=PASS")

        def issue_authorized(digest,tenant,nonce,scope):
            if (digest,tenant,scope)!=(second_digest,tenant_a,"READ_ENTRIES"):
                return None
            p=packet(nonce)
            register(p)
            token=authority.request("release",p)
            if token is None:
                return None
            return submit(p,token)

        async def issue_ticket(session,*,scope,request_nonce):
            provider.issue_calls+=1
            digest=provider.session_digests.get((session.verified_session_id,session.user_id,session.role,session.tenant_id))
            ticket=issue_authorized(digest,UUID(session.tenant_id),request_nonce,scope)
            if ticket:
                provider.last_ticket=ticket
            return ticket

        provider.issue_ticket=issue_ticket
        responses=await asyncio.gather(*(client.get(p,headers=second_headers) for p in read_paths))
        assert all(response.status_code==200 for response in responses)
        assert (await client.get(path_a,headers=admin_headers)).status_code==401
        assert (await client.get(path_a.replace(str(tenant_a),str(tenant_b),1),headers=second_headers)).status_code==403
        # An expired/revoked commitment cannot be consumed even with its token.
        p=packet()
        register(p)
        token=authority.request("release",p)
        owner.execute("UPDATE m40700.identity_commitments SET expiry=0 WHERE nonce=%s",(UUID(p["nonce"]),))
        assert submit(p,token) is None
        assert owner.execute("SELECT consumed_at FROM m40700.identity_commitments WHERE nonce=%s",(UUID(p["nonce"]),)).fetchone()[0] is None
        print("M41620_COMMITMENT_EXPIRY_AND_SIX_READS=PASS")
        return authority,issue_authorized
    except BaseException:
        authority.close()
        raise


if __name__=="__main__":
    if len(sys.argv)!=4 or sys.argv[1]!="--worker" or not all(s.isdigit() for s in sys.argv[2:]):
        raise SystemExit(2)
    raise SystemExit(worker(int(sys.argv[2]),int(sys.argv[3])))
