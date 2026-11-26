"""M40400: original password/session/SQL110 RLS inside ONE tenant, CI-only.

Creates a second synthetic member in tenant A. No Termux connection, real user,
financial transaction, push or production path. Must run only AFTER M40380/M40390
in the same ephemeral GitHub PostgreSQL18 database on port 5432.
"""
import os
from datetime import datetime, timedelta, timezone
from uuid import UUID
from m40380_real_auth_credit_rls_ci import (
    require_ci, DB, A, B, ACTORS, LINKS, TABLES
)

A2=UUID("66666666-6666-4666-8666-666666666666")
MEMBERSHIP_A2=UUID("6666eeee-6666-4666-8666-666666666666")
GRANT_A2=UUID("40400101-0000-4000-8000-000000000001")
CAMPAIGN_A2=UUID("40400202-0000-4000-8000-000000000001")
RECIPIENT_A2=UUID("40400303-0000-4000-8000-000000000001")
CYCLE_A=UUID("aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
FINGERPRINT={
 "special_credit_grants":("id",{
   A:{str(UUID("40380101-0000-4000-8000-000000000001")),str(GRANT_A2)},
   B:{str(UUID("40380101-0000-4000-8000-000000000002"))}}),
 "special_credit_campaigns":("id",{
   A:{str(UUID("40380202-0000-4000-8000-000000000001")),str(CAMPAIGN_A2)},
   B:{str(UUID("40380202-0000-4000-8000-000000000002"))}}),
 "special_credit_recipients":("id",{
   A:{str(UUID("40380303-0000-4000-8000-000000000001")),str(RECIPIENT_A2)},
   B:{str(UUID("40380303-0000-4000-8000-000000000002"))}}),
 "special_credit_preferences":("user_id",{
   A:{str(ACTORS["member_a"]),str(A2)},
   B:{str(ACTORS["member_b"])}}),
}

def seed_same_tenant(pg,hashed):
    # PostgreSQL superuser in the disposable runner only; never target device.
    with pg.transaction():
        pg.execute(
            "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master)"
            " VALUES(%s,%s,'CI M40400 member A2',%s,'00000000000',false)",
            (A2,str(A2)+"@example.com",A2.hex[:14]))
        pg.execute(
            "INSERT INTO public.credentials(user_id,password_hash) VALUES(%s,%s)",
            (A2,hashed))
        pg.execute(
            "INSERT INTO public.memberships(id,tenant_id,user_id,role)"
            " VALUES(%s,%s,%s,'TENANT_MEMBER')",
            (MEMBERSHIP_A2,A,A2))
        now=datetime.now(timezone.utc)
        pg.execute(
            "INSERT INTO public.special_credit_grants"
            "(id,tenant_id,cycle_id,member_id,created_by,ceiling_brl,reason,expires_at,request_id)"
            " VALUES(%s,%s,%s,%s,%s,3500,%s,%s,%s)",
            (GRANT_A2,A,CYCLE_A,MEMBERSHIP_A2,ACTORS["admin_a"],
             "M40400 synthetic member-specific privilege test, no real funds",
             now+timedelta(days=7),
             UUID("40400404-0000-4000-8000-000000000001")))
        pg.execute(
            "INSERT INTO public.special_credit_campaigns"
            "(id,tenant_id,cycle_id,created_by,title,body,expires_at,request_id)"
            " VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
            (CAMPAIGN_A2,A,CYCLE_A,ACTORS["admin_a"],
             "M40400 member A2 only",
             "Synthetic second recipient; never deliver to real contacts.",
             now+timedelta(days=2),
             UUID("40400505-0000-4000-8000-000000000001")))
        pg.execute(
            "INSERT INTO public.special_credit_recipients"
            "(id,tenant_id,campaign_id,grant_id,member_id,user_id)"
            " VALUES(%s,%s,%s,%s,%s,%s)",
            (RECIPIENT_A2,A,CAMPAIGN_A2,GRANT_A2,MEMBERSHIP_A2,A2))
        pg.execute(
            "INSERT INTO public.special_credit_preferences"
            "(tenant_id,user_id,channel,opted_in) VALUES(%s,%s,'PUSH',true)",
            (A,A2))
        pg.execute(
            "UPDATE public.special_credit_campaigns"
            " SET status='PUBLISHED',published_at=now() WHERE id=%s",
            (CAMPAIGN_A2,))
        pg.execute(
            "INSERT INTO public.special_credit_outbox"
            "(tenant_id,campaign_id,recipient_id,channel,state)"
            " VALUES(%s,%s,%s,'PUSH','BLOCKED_EXTERNAL')",
            (A,CAMPAIGN_A2,RECIPIENT_A2))
        pg.execute(
            "INSERT INTO public.special_credit_audit"
            "(tenant_id,actor_id,entity_kind,entity_id,action,detail)"
            " VALUES(%s,%s,'CAMPAIGN',%s,'M40400_CI','No external delivery')",
            (A,ACTORS["admin_a"],CAMPAIGN_A2))

def main():
    require_ci()  # Absolute fail-closed, before importing database/application.
    import psycopg
    from fastapi import Depends
    from fastapi.testclient import TestClient
    from app.main import app
    from app.database import get_rls_db_connection
    from app.dependencies import get_current_session
    from app.security import hash_password_secure

    with psycopg.connect(host="127.0.0.1",port=5432,dbname=DB,
            user="postgres",password="postgres",connect_timeout=3) as pg:
        version=pg.execute(
            "SELECT current_database(),session_user,inet_server_port(),"
            "current_setting('frfinance.m40380_ci',true),"
            "current_setting('server_version_num')::int").fetchone()
        assert version[:4]==(DB,"postgres",5432,"DISPOSABLE_ONLY")
        assert 180000<=version[4]<190000
        assert pg.execute("SELECT count(*) FROM public.users").fetchone()[0]==5
        assert pg.execute("SELECT count(*) FROM public.special_credit_grants").fetchone()[0]==2
        for table in TABLES:
            policy=pg.execute(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                "WHERE oid=%s::regclass",("public."+table,)).fetchone()
            assert policy==(True,True),(table,policy)
        seed_same_tenant(pg,hash_password_secure("m40380-synthetic-password"))

    # Reuse the M40380 disposable fixture only after checking its PG18 identity.
    app.state.frfinance_ci_disposable_read_test = True
    @app.get("/__ci_m40400/same-tenant-rows",include_in_schema=False)
    async def probe(session=Depends(get_current_session),
                    conn=Depends(get_rls_db_connection)):
        context=await conn.fetchrow(
            "SELECT current_user,current_setting('app.current_user_id',true),"
            "current_setting('app.current_role',true),"
            "current_setting('app.current_tenant_id',true)")
        assert tuple(context)==(
            "frc_ai_app",session.user_id,session.role,session.tenant_id or "")
        rows={}
        for tenant in (A,B):
            rows[str(tenant)]={}
            for table in TABLES:
                key="user_id" if table=="special_credit_preferences" else "id"
                data=await conn.fetch(
                    "SELECT "+key+"::text AS entity "
                    "FROM public."+table+" WHERE tenant_id=$1",tenant)
                rows[str(tenant)][table]=sorted(item["entity"] for item in data)
        return {"role":session.role,"user":session.user_id,
                "tenant":session.tenant_id,"rows":rows}

    actor_cases=(
        ("admin_a",ACTORS["admin_a"],A,"TENANT_ADMIN"),
        ("member_a",ACTORS["member_a"],A,"TENANT_MEMBER"),
        ("member_a2",A2,A,"TENANT_MEMBER"),
        ("admin_b",ACTORS["admin_b"],B,"TENANT_ADMIN"),
        ("member_b",ACTORS["member_b"],B,"TENANT_MEMBER"),
        ("master",ACTORS["master"],None,"MASTER"),
    )
    checks=0
    with TestClient(app) as client:
        for name,uid,own,role in actor_cases:
            body={"usernameOrEmail":str(uid)+"@example.com",
                  "password":"m40380-synthetic-password",
                  "requestedRole":role}
            if own is not None:body["requestedTenantId"]=str(own)
            login=client.post("/api/v1/auth/login",json=body)
            assert login.status_code==200,(name,login.status_code)
            headers={"Authorization":"Bearer "+login.json()["token"]}
            result=client.get("/__ci_m40400/same-tenant-rows",
                              headers=headers)
            assert result.status_code==200,(name,result.status_code)
            data=result.json()
            assert data["role"]==role and data["user"]==str(uid)
            assert data["tenant"]==(str(own) if own else None)
            for tenant in (A,B):
                for table in TABLES:
                    actual=set(data["rows"][str(tenant)][table])
                    if own!=tenant or role=="MASTER":
                        expected=set()
                    elif role=="TENANT_ADMIN":
                        if table in FINGERPRINT:
                            expected=FINGERPRINT[table][1][tenant]
                        else:
                            expected_count=2 if tenant==A else 1
                            assert len(actual)==expected_count,(name,table)
                            expected=actual
                    elif table in ("special_credit_outbox","special_credit_audit"):
                        expected=set()
                    else:
                        if tenant==A:
                            index=1 if uid==A2 else 0
                        else:
                            index=0
                        expected={sorted(FINGERPRINT[table][1][tenant])[index]}
                    assert actual==expected,(name,table,tenant,actual,expected)
                    checks+=1
            assert client.post("/api/v1/auth/logout",headers=headers).status_code==200
            assert client.get("/__ci_m40400/same-tenant-rows",
                              headers=headers).status_code==401

    assert checks==72,checks
    with psycopg.connect(host="127.0.0.1",port=5432,dbname=DB,
           user="postgres",password="postgres",connect_timeout=3) as verify:
        for table in TABLES:
            count=verify.execute(
                "SELECT count(*) FROM public."+table).fetchone()[0]
            assert count==3,(table,count)
        dispatched=verify.execute(
            "SELECT count(*) FROM public.special_credit_outbox "
            "WHERE state <> 'BLOCKED_EXTERNAL'").fetchone()[0]
        assert dispatched==0,dispatched

    print("M40400_AUTHENTIC_LOGIN_SAME_TENANT=PASS")
    print("M40400_MEMBER_A_VS_MEMBER_A2_RLS=ISOLATED")
    print("M40400_CROSS_TENANT_MASTER_RLS=DENIED")
    print("M40400_SIX_TABLE_ROW_LEVEL_PROOFS=PASS_72_OF_72")
    print("M40400_OUTBOX_EXTERNAL_DISPATCH=BLOCKED")
    print("M40400_TERMUX_PG_5433=NOT_CONNECTED")
    print("M40400_PRODUCTION=BLOCKED")

if __name__=="__main__":
    main()
