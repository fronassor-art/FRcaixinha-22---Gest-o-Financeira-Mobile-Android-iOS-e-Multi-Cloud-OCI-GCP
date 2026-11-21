"""M40410: original FastAPI campaign lifecycle in ephemeral CI only.

No original Termux DB or external delivery. For positive-path API testing,
the sandbox predicate is monkeypatched IN THIS TEST PROCESS ONLY; all
actual env flags remain OFF. Never execute on a phone, staging or production.
"""
import os
from datetime import date,datetime,timedelta,timezone
from unittest.mock import patch
from uuid import UUID

from m40380_real_auth_credit_rls_ci import require_ci,DB,A,B,ACTORS,TABLES
from m40400_same_tenant_rls_ci import A2,GRANT_A2,CAMPAIGN_A2,RECIPIENT_A2

FIRST_CAMPAIGN=UUID("40380202-0000-4000-8000-000000000001")
FIRST_RECIPIENT=UUID("40380303-0000-4000-8000-000000000001")
GRANT_A1=UUID("40380101-0000-4000-8000-000000000001")

def main():
    require_ci()  # Must be called BEFORE any DB/client import.
    import psycopg
    from fastapi.testclient import TestClient
    from app.main import app
    from app.routers import special_credit

    assert os.getenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX")=="NO"
    assert not special_credit._enabled()
    assert not app.dependency_overrides
    with psycopg.connect(host="127.0.0.1",port=5432,dbname=DB,
            user="postgres",password="postgres",connect_timeout=3) as pg:
        proof=pg.execute(
            "SELECT current_database(),session_user,inet_server_port(),"
            "current_setting('frfinance.m40380_ci',true),"
            "current_setting('server_version_num')::int").fetchone()
        assert proof[:4]==(DB,"postgres",5432,"DISPOSABLE_ONLY")
        assert 180000<=proof[4]<190000
        assert pg.execute("SELECT count(*) FROM public.users").fetchone()[0]==6
        for table in TABLES:
            assert pg.execute("SELECT count(*) FROM public."+table).fetchone()[0]==3
            assert pg.execute(
                "SELECT relrowsecurity,relforcerowsecurity FROM pg_class "
                "WHERE oid=%s::regclass",("public."+table,)).fetchone()==(True,True)
        # Existing fixtures from M40380/M40400 use next-year cycles.
        # CI-only: convert synthetic cycles into this calendar year.
        # Never change financial cycle in Termux.
        today=date.today()
        year=today.year
        assert today < date(year,12,25),"M40410 needs seven days until year end"
        pg.execute(
            "UPDATE public.cycles "
            "SET year=%s,start_date=%s,end_date=%s,settlement_date=%s "
            "WHERE tenant_id IN (%s,%s) AND year=%s",
            (year,date(year,1,1),date(year,12,31),
             date(year+1,1,10),A,B,2027))
        pg.commit()
        assert pg.execute("SELECT count(*) FROM public.cycles "
            "WHERE tenant_id IN (%s,%s) AND status='ABERTO' "
            "AND start_date<=CURRENT_DATE AND end_date>=CURRENT_DATE",
            (A,B)).fetchone()[0]==2
        assert pg.execute("SELECT count(*) FROM public.loans").fetchone()[0]==0
        assert pg.execute("SELECT count(*) FROM public.ledger_transactions").fetchone()[0]==0

    counter=0
    def expect(resp,code,label):
        nonlocal counter
        assert resp.status_code==code,(label,resp.status_code,resp.text[:140])
        counter+=1
        return resp.json() if code<400 else None
    def login(client,name,uid,role,tenant):
        body={"usernameOrEmail":str(uid)+"@example.com",
              "password":"m40380-synthetic-password","requestedRole":role}
        if tenant is not None:body["requestedTenantId"]=str(tenant)
        data=expect(client.post("/api/v1/auth/login",json=body),200,"login:"+name)
        return {"Authorization":"Bearer "+data["token"]}
    def api(client,method,tenant,path,headers,body=None):
        kw={"headers":headers}
        if body is not None:kw["json"]=body
        return client.request(method,"/api/v1/tenants/"+str(tenant)+
                              "/special-credit"+path,**kw)

    # Test only: in-memory patch, not environment/configuration/production code.
    with patch.object(special_credit,"_enabled",return_value=True):
      with TestClient(app) as client:
        admin=login(client,"admin_a",ACTORS["admin_a"],"TENANT_ADMIN",A)
        member=login(client,"member_a",ACTORS["member_a"],"TENANT_MEMBER",A)
        member2=login(client,"member_a2",A2,"TENANT_MEMBER",A)
        other=login(client,"member_b",ACTORS["member_b"],"TENANT_MEMBER",B)

        cap=expect(api(client,"GET",A,"/capabilities",admin),
                   200,"sandbox CI capabilities")
        assert cap["sandbox_enabled"] is True
        assert cap["real_credit_enabled"] is False
        assert cap["pix_real_enabled"] is False
        assert all(not x["real_delivery_enabled"] for x in cap["channels"].values())
        counter+=4
        before=expect(api(client,"GET",A,"/campaigns",admin),200,"admin campaigns")
        assert {str(x["id"]) for x in before}>={str(FIRST_CAMPAIGN),str(CAMPAIGN_A2)}
        counter+=1
        mine=expect(api(client,"GET",A,"/opportunities",member),200,"member A")
        mine2=expect(api(client,"GET",A,"/opportunities",member2),200,"member A2")
        foreign=expect(api(client,"GET",B,"/opportunities",other),200,"member B")
        assert {x["recipient_id"] for x in mine}=={str(FIRST_RECIPIENT)}
        assert {x["recipient_id"] for x in mine2}=={str(RECIPIENT_A2)}
        assert len(foreign)==1
        counter+=3
        expect(api(client,"GET",B,"/opportunities",member),403,"wrong tenant")
        expect(api(client,"GET",A,"/campaigns",member),403,"member admin only")
        expect(api(client,"POST",A,f"/opportunities/{RECIPIENT_A2}/reply",
                   member,{"status":"INTERESTED"}),409,"member A cannot reply A2")
        expect(api(client,"POST",A,f"/opportunities/{FIRST_RECIPIENT}/reply",
                   member2,{"status":"DECLINED"}),409,"member A2 cannot reply A")

        interested=expect(
          api(client,"POST",A,f"/opportunities/{FIRST_RECIPIENT}/reply",
              member,{"status":"INTERESTED"}),200,"interested A")
        declined=expect(
          api(client,"POST",A,f"/opportunities/{RECIPIENT_A2}/reply",
              member2,{"status":"DECLINED"}),200,"declined A2")
        assert interested=={"status":"INTERESTED","loan_created":False}
        assert declined=={"status":"DECLINED","loan_created":False}
        counter+=2
        expect(api(client,"POST",A,f"/opportunities/{FIRST_RECIPIENT}/reply",
                   member,{"status":"DECLINED"}),409,"reply not reversible")
        expect(api(client,"POST",A,f"/opportunities/{RECIPIENT_A2}/reply",
                   member2,{"status":"INTERESTED"}),409,"reply cannot repeat")

        opted=expect(api(client,"POST",A,"/preferences",member,
                         {"channel":"PUSH","opted_in":False}),
                     200,"push opted out")
        assert opted["external_dispatch"] is False
        state=expect(api(client,"GET",A,"/preferences",member),
                     200,"preferences read")
        assert state["preferences"]["PUSH"] is False
        assert state["external_dispatch"] is False
        counter+=3

        current=datetime.now(timezone.utc)
        bad_grant={"member_ids":[str(RECIPIENT_A2)],
                   "ceiling_brl":"1800.00",
                   "expires_at":(current-timedelta(days=1)).isoformat(),
                   "reason":"M40410 synthetic invalid expiry never real credit",
                   "request_id":"40401010-0000-4000-8000-000000000001"}
        expect(api(client,"POST",A,"/grants",admin,bad_grant),
               422,"expired grant must fail")
        expired_campaign={"grant_ids":[str(GRANT_A1)],
           "title":"M40410 expired",
           "body":"Offline synthetic expired campaign must fail",
           "expires_at":(current-timedelta(days=1)).isoformat(),
           "request_id":"40401010-0000-4000-8000-000000000002"}
        expect(api(client,"POST",A,"/campaigns",admin,expired_campaign),
               422,"expired campaign must fail")
        after_cycle={**expired_campaign,
            "expires_at":date(year+1,1,3).isoformat()+"T12:00:00Z",
            "request_id":"40401010-0000-4000-8000-000000000003"}
        expect(api(client,"POST",A,"/campaigns",admin,after_cycle),
               422,"cross-cycle campaign must fail")

        published=expect(
          api(client,"POST",A,f"/campaigns/{CAMPAIGN_A2}/publish",admin,{}),
          200,"repeat published should be non-delivering")
        assert published["external_dispatch"] is False
        assert published["in_app"] is True
        counter+=2
        cancelled=expect(
          api(client,"POST",A,f"/campaigns/{CAMPAIGN_A2}/cancel",admin,{}),
          200,"cancel A2")
        assert cancelled["status"]=="CANCELLED"
        counter+=1
        expect(api(client,"POST",A,f"/campaigns/{CAMPAIGN_A2}/cancel",admin,{}),
               409,"cannot cancel twice")
        gone=expect(api(client,"GET",A,"/opportunities",member2),200,"cancel hides")
        assert gone==[],"Cancelled campaigns must disappear from opportunities"
        counter+=1
        revoked=expect(
          api(client,"POST",A,f"/grants/{GRANT_A2}/revoke",admin,{}),
          200,"revoke A2")
        assert revoked["status"]=="REVOKED"
        counter+=1
        expect(api(client,"POST",A,f"/grants/{GRANT_A2}/revoke",admin,{}),
               409,"cannot revoke twice")
        for who in (admin,member,member2,other):
            expect(client.post("/api/v1/auth/logout",headers=who),200,"logout")
    assert not special_credit._enabled(),"CI patch leaked outside scoped context"
    with psycopg.connect(host="127.0.0.1",port=5432,dbname=DB,
            user="postgres",password="postgres",connect_timeout=3) as verify:
        states=verify.execute(
            "SELECT user_id,response_status FROM public.special_credit_recipients "
            "WHERE id IN (%s,%s)",(FIRST_RECIPIENT,RECIPIENT_A2)).fetchall()
        assert dict(states)=={ACTORS["member_a"]:"INTERESTED",A2:"DECLINED"}
        counter+=1
        assert verify.execute(
            "SELECT count(*) FROM public.special_credit_outbox "
            "WHERE state<>'BLOCKED_EXTERNAL'").fetchone()[0]==0
        counter+=1
        assert verify.execute("SELECT count(*) FROM public.special_credit_outbox"
            ).fetchone()[0]==3
        counter+=1
        assert verify.execute("SELECT count(*) FROM public.loans").fetchone()[0]==0
        assert verify.execute("SELECT count(*) FROM public.ledger_transactions").fetchone()[0]==0
        counter+=2
        assert verify.execute("SELECT status FROM public.special_credit_campaigns"
            " WHERE id=%s",(CAMPAIGN_A2,)).fetchone()[0]=="CANCELLED"
        assert verify.execute("SELECT status FROM public.special_credit_grants"
            " WHERE id=%s",(GRANT_A2,)).fetchone()[0]=="REVOKED"
        counter+=2
    print("M40410_SANDBOX_PREDICATE=PATCHED_IN_CI_PROCESS_ONLY")
    print("M40410_CAMPAIGN_INTEREST_DECLINE_CANCEL_REVOKE=PASS")
    print("M40410_EXPIRED_AND_CROSS_CYCLE_REQUESTS=DENIED")
    print("M40410_DUPLICATE_REPLIES=DENIED")
    print("M40410_OTHER_MEMBER_AND_TENANT_ACCESS=DENIED")
    print("M40410_EXTERNAL_OUTBOX=BLOCKED")
    print("M40410_REAL_LOANS_AND_LEDGER_WRITES=NONE")
    print("M40410_CASE_ASSERTIONS="+str(counter))
    print("M40410_TERMUX_DATABASE=NOT_CONNECTED")
    print("M40410_REAL_PAYMENTS=OFF")
    print("M40410_PRODUCTION=BLOCKED")

if __name__=="__main__":
    main()
