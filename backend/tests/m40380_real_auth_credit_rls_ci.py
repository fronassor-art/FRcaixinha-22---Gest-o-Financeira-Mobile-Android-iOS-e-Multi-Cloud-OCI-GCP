"""M40380: ORIGINAL password login to six SQL110 FORCE RLS tables; disposable CI only."""
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID

DB="frfinance_ci_credit"
A=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
B=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
ACTORS={
 "admin_a":UUID("11111111-1111-4111-8111-111111111111"),
 "member_a":UUID("22222222-2222-4222-8222-222222222222"),
 "admin_b":UUID("33333333-3333-4333-8333-333333333333"),
 "member_b":UUID("44444444-4444-4444-8444-444444444444"),
 "master":UUID("55555555-5555-4555-8555-555555555555"),
}
LINKS={
 "admin_a":UUID("1111eeee-1111-4111-8111-111111111111"),
 "member_a":UUID("aaaaeeee-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
 "admin_b":UUID("3333eeee-3333-4333-8333-333333333333"),
 "member_b":UUID("bbbbeeee-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
}
TABLES=("special_credit_grants","special_credit_campaigns",
 "special_credit_recipients","special_credit_preferences",
 "special_credit_outbox","special_credit_audit")
SAFE={"GITHUB_ACTIONS":"true","CI_M40380_DISPOSABLE":"1",
 "PGHOST":"127.0.0.1","PGPORT":"5432","PGDATABASE":DB,
 "PGUSER":"postgres","PGPASSWORD":"postgres",
 "ENVIRONMENT":"development","FRCAIXINHA_TEST_AUTH":"1",
 "FR_FINANCE_SPECIAL_CREDIT_SANDBOX":"NO",
 "PIX_REAL":"OFF","PAGAMENTOS_REAIS":"OFF","ATIVACAO_REAL":"OFF",
 "FR_FINANCE_PIX_REAL":"OFF","FR_FINANCE_REAL_PAYMENTS":"OFF",
 "FR_FINANCE_REAL_USER_ACTIVATION":"OFF",
 "FR_FINANCE_ACCESS_MAIL_ENABLE":"OFF","FR_FINANCE_ACCESS_MAIL_WORKER":"OFF",
 "AI_STUDIO_IN_APP_NOTIFICATIONS":"NO"}
DSNS={"DATABASE_URL":("frc_ai_app","m40380-app-ci-only"),
 "AUTH_DATABASE_URL":("fr_m40380_auth","m40380-auth-ci-only"),
 "AUTH_VERIFIER_DATABASE_URL":("fr_m40380_verifier","m40380-verifier-ci-only")}

def require_ci():
 e=os.environ
 if any(e.get(k)!=v for k,v in SAFE.items()):
  raise RuntimeError("M40380_UNSAFE_ENVIRONMENT")
 if "frfinance.m40380_ci=DISPOSABLE_ONLY" not in e.get("PGOPTIONS",""):
  raise RuntimeError("M40380_MISSING_GUC")
 for key,(user,pw) in DSNS.items():
  p=urlsplit(e.get(key,""))
  if (p.scheme!="postgresql" or p.username!=user or p.password!=pw or
      p.hostname!="127.0.0.1" or p.port!=5432 or
      p.path!="/"+DB or p.query or p.fragment):
   raise RuntimeError("M40380_BAD_DSN_"+key)
 if not e.get("AUTH_RATE_LIMIT_HMAC_KEY","").startswith("m40380-ci-only"):
  raise RuntimeError("M40380_BAD_HMAC")

def seed(pg,hashed):
 with pg.transaction():
  for name,uid in ACTORS.items():
   pg.execute("INSERT INTO users(id,email,full_name,cpf,phone,is_master)"
    " VALUES(%s,%s,%s,%s,'00000000000',%s)",
    (uid,str(uid)+"@example.com","CI "+name,uid.hex[:14],name=="master"))
   pg.execute("INSERT INTO credentials(user_id,password_hash) VALUES(%s,%s)",(uid,hashed))
  for tenant,admin,suffix in ((A,"admin_a","A"),(B,"admin_b","B")):
   pg.execute("INSERT INTO tenants(id,display_name,contracting_party_id,admin_user_id)"
    " VALUES(%s,%s,%s,%s)",(tenant,"CI Tenant "+suffix,"m40380-"+suffix,ACTORS[admin]))
  for name,t,role in (("admin_a",A,"TENANT_ADMIN"),("member_a",A,"TENANT_MEMBER"),
                      ("admin_b",B,"TENANT_ADMIN"),("member_b",B,"TENANT_MEMBER")):
   pg.execute("INSERT INTO memberships(id,tenant_id,user_id,role)"
    " VALUES(%s,%s,%s,%s)",(LINKS[name],t,ACTORS[name],role))
  cycles={A:UUID("aaaacccc-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
          B:UUID("bbbbcccc-bbbb-4bbb-8bbb-bbbbbbbbbbbb")}
  for t,c in cycles.items():
   pg.execute("INSERT INTO cycles(id,tenant_id,year,start_date,end_date,settlement_date)"
    " VALUES(%s,%s,2027,'2027-01-01','2027-12-31','2028-01-10')",(c,t))
  now=datetime.now(timezone.utc)
  for t,admin,member,n in ((A,"admin_a","member_a",1),(B,"admin_b","member_b",2)):
   g=UUID(f"40380101-0000-4000-8000-00000000000{n}")
   c=UUID(f"40380202-0000-4000-8000-00000000000{n}")
   r=UUID(f"40380303-0000-4000-8000-00000000000{n}")
   pg.execute("INSERT INTO special_credit_grants(id,tenant_id,cycle_id,member_id,"
    "created_by,ceiling_brl,reason,expires_at,request_id)"
    " VALUES(%s,%s,%s,%s,%s,2000,%s,%s,%s)",
    (g,t,cycles[t],LINKS[member],ACTORS[admin],
     "M40380 synthetic, never real money",now+timedelta(days=7),
     UUID(f"40380404-0000-4000-8000-00000000000{n}")))
   pg.execute("INSERT INTO special_credit_campaigns(id,tenant_id,cycle_id,created_by,"
    "title,body,expires_at,request_id) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
    (c,t,cycles[t],ACTORS[admin],"M40380 CI only",
     "Synthetic campaign with no delivery.",now+timedelta(days=2),
     UUID(f"40380505-0000-4000-8000-00000000000{n}")))
   pg.execute("INSERT INTO special_credit_recipients(id,tenant_id,campaign_id,"
    "grant_id,member_id,user_id) VALUES(%s,%s,%s,%s,%s,%s)",
    (r,t,c,g,LINKS[member],ACTORS[member]))
   pg.execute("INSERT INTO special_credit_preferences(tenant_id,user_id,channel,opted_in)"
    " VALUES(%s,%s,'PUSH',true)",(t,ACTORS[member]))
   pg.execute("UPDATE special_credit_campaigns SET status='PUBLISHED',"
    "published_at=now() WHERE id=%s",(c,))
   pg.execute("INSERT INTO special_credit_outbox(tenant_id,campaign_id,"
    "recipient_id,channel,state) VALUES(%s,%s,%s,'PUSH','BLOCKED_EXTERNAL')",(t,c,r))
   pg.execute("INSERT INTO special_credit_audit(tenant_id,actor_id,entity_kind,"
    "entity_id,action,detail) VALUES(%s,%s,'CAMPAIGN',%s,'M40380_CI','Not delivered')",
    (t,ACTORS[admin],c))

def main():
 require_ci() # Guard must precede DB/HTTP imports.
 import psycopg
 from fastapi import Depends
 from fastapi.testclient import TestClient
 from app.main import app
 from app.database import get_rls_db_connection
 from app.dependencies import get_current_session
 from app.security import hash_password_secure
 assert not app.dependency_overrides
 with psycopg.connect(host="127.0.0.1",port=5432,dbname=DB,
      user="postgres",password="postgres",connect_timeout=3) as pg:
  x=pg.execute("SELECT current_database(),session_user,inet_server_port(),"
   "current_setting('frfinance.m40380_ci',true),"
   "current_setting('server_version_num')::int").fetchone()
  assert x[:4]==(DB,"postgres",5432,"DISPOSABLE_ONLY")
  assert 180000<=x[4]<190000
  assert pg.execute("SELECT count(*) FROM users").fetchone()[0]==0
  assert pg.execute("SELECT count(*) FROM sessions").fetchone()[0]==0
  for table in TABLES:
   x=pg.execute("SELECT relrowsecurity,relforcerowsecurity FROM pg_class"
    " WHERE oid=%s::regclass",("public."+table,)).fetchone()
   assert x==(True,True),(table,x)
  for fn in ("auth_issue_pending_session","auth_promote_pending_session",
             "auth_active_memberships","auth_refresh_session"):
   assert pg.execute("SELECT count(*) FROM pg_proc WHERE proname=%s",(fn,)).fetchone()[0]>=1
  seed(pg,hash_password_secure("m40380-synthetic-password"))
 @app.get("/__ci_m40380/credit-rls",include_in_schema=False)
 async def probe(session=Depends(get_current_session),conn=Depends(get_rls_db_connection)):
  r=await conn.fetchrow("SELECT current_user,current_setting('app.current_user_id',true),"
   "current_setting('app.current_role',true),current_setting('app.current_tenant_id',true)")
  assert tuple(r)==("frc_ai_app",session.user_id,session.role,session.tenant_id or "")
  counts={}
  for tenant in (A,B):
   counts[str(tenant)]={}
   for table in TABLES:
    counts[str(tenant)][table]=await conn.fetchval(
     "SELECT count(*) FROM public."+table+" WHERE tenant_id=$1",tenant)
  return {"role":session.role,"tenant":session.tenant_id,"counts":counts}
 checks=0
 # The marker follows the PG18 identity, GUC, RLS and seed-fixture preflight.
 app.state.frfinance_ci_disposable_read_test = True
 with TestClient(app) as client:
  for name,own,other,role in (
   ("admin_a",A,B,"TENANT_ADMIN"),("admin_b",B,A,"TENANT_ADMIN"),
   ("member_a",A,B,"TENANT_MEMBER"),("member_b",B,A,"TENANT_MEMBER"),
   ("master",None,A,"MASTER")
  ):
   body={"usernameOrEmail":str(ACTORS[name])+"@example.com",
         "password":"m40380-synthetic-password","requestedRole":role}
   if own is not None:body["requestedTenantId"]=str(own)
   login=client.post("/api/v1/auth/login",json=body)
   assert login.status_code==200,(name,login.status_code,login.text[:150])
   headers={"Authorization":"Bearer "+login.json()["token"]}
   response=client.get("/__ci_m40380/credit-rls",headers=headers)
   assert response.status_code==200,(name,response.status_code,response.text[:150])
   result=response.json()
   assert result["role"]==role and result["tenant"]==(str(own) if own else None)
   for table in TABLES:
    if role=="MASTER":
     assert result["counts"][str(A)][table]==0
     assert result["counts"][str(B)][table]==0
    else:
     allowed=role=="TENANT_ADMIN" or table not in (
      "special_credit_outbox","special_credit_audit")
     assert (result["counts"][str(own)][table]>0)==allowed,(name,table,"own")
     assert result["counts"][str(other)][table]==0,(name,table,"other")
    checks+=2
   cap=client.get(f"/api/v1/tenants/{own or A}/special-credit/capabilities",
     headers=headers)
   assert cap.status_code==(403 if role=="MASTER" else 200)
   if role!="MASTER":
    assert cap.json()["sandbox_enabled"] is False
    assert cap.json()["real_credit_enabled"] is False
    assert all(not x["real_delivery_enabled"] for x in cap.json()["channels"].values())
    spoof=client.get("/__ci_m40380/credit-rls",headers={
     **headers,"X-Tenant-ID":str(other),"X-Role":"TENANT_ADMIN"})
    assert spoof.status_code==200 and spoof.json()==result
   assert client.post("/api/v1/auth/logout",headers=headers).status_code==200
   assert client.get("/__ci_m40380/credit-rls",headers=headers).status_code==401
  assert client.get("/__ci_m40380/credit-rls").status_code==401
  invalid=client.post("/api/v1/auth/login",json={
   "usernameOrEmail":str(ACTORS["member_a"])+"@example.com",
   "password":"m40380-synthetic-password","requestedRole":"TENANT_ADMIN",
   "requestedTenantId":str(B)})
  assert invalid.status_code==401 and "token" not in invalid.json()
  # M40390 negative FastAPI checks only on disposable PostgreSQL18.
  wrong=client.post("/api/v1/auth/login",json={
   "usernameOrEmail":str(ACTORS["admin_a"])+"@example.com",
   "password":"M40390-wrong-password","requestedRole":"TENANT_ADMIN",
   "requestedTenantId":str(A)})
  assert wrong.status_code==401 and "token" not in wrong.json(),wrong.status_code
  bad=client.get(f"/api/v1/tenants/{A}/special-credit/capabilities",
    headers={"Authorization":"Bearer invalid-m40390"})
  assert bad.status_code==401
  grant={"member_ids":[str(LINKS["member_a"])],"ceiling_brl":"1800.00",
   "expires_at":"2027-06-01T12:00:00Z",
   "reason":"M40390 offline synthetic check, never real credit",
   "request_id":"40380909-0000-4000-8000-000000000001"}
  campaign={"grant_ids":["40380101-0000-4000-8000-000000000001"],
   "title":"M40390 offline test","body":"No external delivery or finance.",
   "expires_at":"2027-06-01T12:00:00Z",
   "request_id":"40380909-0000-4000-8000-000000000002"}
  cases=[
   ("admin_a",A,"TENANT_ADMIN",[
    ("GET",A,"/members",None,503),
    ("GET",A,"/campaigns",None,503),
    ("POST",A,"/grants",grant,503),
    ("POST",A,"/campaigns",campaign,503),
    ("POST",A,"/campaigns/40380202-0000-4000-8000-000000000001/publish",{},503),
    ("GET",B,"/capabilities",None,403),
    ("POST",B,"/grants",grant,403),
    ("GET",A,"/opportunities",None,403),
    ("POST",A,"/preferences",{"channel":"PUSH","opted_in":True},403),
   ]),
   ("member_a",A,"TENANT_MEMBER",[
    ("GET",A,"/opportunities",None,503),
    ("GET",A,"/preferences",None,503),
    ("POST",A,"/preferences",{"channel":"PUSH","opted_in":False},503),
    ("POST",A,"/opportunities/40380303-0000-4000-8000-000000000001/reply",
      {"status":"DECLINED"},503),
    ("GET",A,"/campaigns",None,403),
    ("POST",A,"/grants",grant,403),
    ("GET",B,"/capabilities",None,403),
    ("POST",B,"/preferences",{"channel":"PUSH","opted_in":False},403),
   ]),
   ("master",None,"MASTER",[
    ("GET",A,"/capabilities",None,403),
    ("POST",A,"/grants",grant,403),
    ("GET",B,"/opportunities",None,403),
   ]),
  ]
  decisions=0
  for name,own,role,requests in cases:
   payload={"usernameOrEmail":str(ACTORS[name])+"@example.com",
    "password":"m40380-synthetic-password","requestedRole":role}
   if own is not None:payload["requestedTenantId"]=str(own)
   logged=client.post("/api/v1/auth/login",json=payload)
   assert logged.status_code==200,(name,logged.status_code)
   headers={"Authorization":"Bearer "+logged.json()["token"]}
   for method,tenant,path,body,expected in requests:
    kwargs={"headers":headers}
    if body is not None:kwargs["json"]=body
    response=client.request(method,
      f"/api/v1/tenants/{tenant}/special-credit"+path,**kwargs)
    assert response.status_code==expected,(name,method,path,response.status_code,expected)
    decisions+=1
   assert client.post("/api/v1/auth/logout",headers=headers).status_code==200
  assert decisions==20,decisions
  with psycopg.connect(host="127.0.0.1",port=5432,dbname=DB,
       user="postgres",password="postgres",connect_timeout=3) as verify:
   for table in TABLES:
    value=verify.execute("SELECT count(*) FROM public."+table).fetchone()[0]
    assert value==2,(table,value)
   blocked=verify.execute("SELECT count(*) FROM public.special_credit_outbox "
      "WHERE state='BLOCKED_EXTERNAL'").fetchone()[0]
   assert blocked==2,blocked
  print("M40390_REAL_FASTAPI_NEGATIVE_HTTP=PASS_20_OF_20")
  print("M40390_WRONG_PASSWORD_BEARER_AND_CROSS_TENANT=DENIED")
  print("M40390_SANDBOX_MUTATIONS=DENIED_NO_CREDIT_WRITES")
  print("M40390_SQL110_SIX_TABLES=UNCHANGED")

 assert checks==60,checks
 print("M40380_REAL_PASSWORD_AUTH_SQL_FUNCTIONS=PASS")
 print("M40380_SQL110_FORCE_RLS=PASS_6_OF_6")
 print("M40380_AUTHENTICATED_TWO_TENANT=PASS_60_OF_60")
 print("M40380_HEADER_IMPERSONATION=DENIED")
 print("M40380_EXTERNAL_COMMUNICATIONS=OFF")
 print("M40380_TERMUX_DATABASE=NOT_CONNECTED")
 print("M40380_PRODUCTION=BLOCKED")
if __name__=="__main__": main()
