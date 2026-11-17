"""M40340. Real FastAPI auth + six actual SQL110 RLS policies, disposable CI only.

Synthetic bearer hashes are pre-seeded; synthetic auth helper functions are
NOT official production implementations. No payment or notification dispatch.
"""
from __future__ import annotations
import os
from urllib.parse import urlsplit

DB = "frfinance_ci_credit"
APP_DSN = "postgresql://frc_ai_app:m40340-app-ci-only@127.0.0.1:5432/" + DB
AUTH_DSN = "postgresql://fr_m40340_auth:m40340-auth-ci-only@127.0.0.1:5432/" + DB
EXPECTED = {
 "GITHUB_ACTIONS": "true", "CI_M40340_DISPOSABLE": "1",
 "PGHOST": "127.0.0.1", "PGPORT": "5432", "PGDATABASE": DB,
 "PGUSER": "postgres", "PGPASSWORD": "postgres",
 "ENVIRONMENT": "development", "FRCAIXINHA_TEST_AUTH": "1",
 "DATABASE_URL": APP_DSN, "AUTH_DATABASE_URL": AUTH_DSN,
 "PIX_REAL": "OFF", "PAGAMENTOS_REAIS": "OFF", "ATIVACAO_REAL": "OFF",
 "FR_FINANCE_PIX_REAL": "OFF", "FR_FINANCE_REAL_PAYMENTS": "OFF",
 "FR_FINANCE_REAL_USER_ACTIVATION": "OFF",
 "FR_FINANCE_SPECIAL_CREDIT_SANDBOX": "NO",
 "FR_FINANCE_ACCESS_MAIL_ENABLE": "OFF",
 "FR_FINANCE_ACCESS_MAIL_WORKER": "OFF",
}
TABLES = (
 "special_credit_grants","special_credit_campaigns",
 "special_credit_recipients","special_credit_preferences",
 "special_credit_outbox","special_credit_audit",
)
TOKENS = {k: "m40340-" + k.replace("_", "-")
          for k in ("admin_a","admin_b","member_a","member_b",
                    "master","expired","revoked","invalid")}


def require_disposable_ci(e=None):
 e = os.environ if e is None else e
 if any(e.get(k)!=v for k,v in EXPECTED.items()):
  raise RuntimeError("M40340_BLOCKED_UNSAFE_ENVIRONMENT")
 if "frfinance.m40340_ci=DISPOSABLE_ONLY" not in e.get("PGOPTIONS",""):
  raise RuntimeError("M40340_BLOCKED_GUC")
 for k in ("DATABASE_URL","AUTH_DATABASE_URL"):
  d = urlsplit(e[k])
  if (d.scheme!="postgresql" or d.hostname!="127.0.0.1"
      or d.port!=5432 or d.path!="/"+DB):
   raise RuntimeError("M40340_BLOCKED_WRONG_DSN")


def main():
 require_disposable_ci()  # Before importing any database or HTTP clients.
 from uuid import UUID
 import psycopg
 from fastapi import Depends, HTTPException
 from fastapi.testclient import TestClient
 from app.main import app
 from app.database import get_db_pool, get_rls_db_connection
 from app.dependencies import AuthenticatedSession, get_current_session, require_tenant_access

 A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
 B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
 assert not app.dependency_overrides
 assert not any(getattr(r,"path","").startswith("/__ci_m40340") for r in app.routes)
 with psycopg.connect(host="127.0.0.1",port=5432,dbname=DB,user="postgres",
       password="postgres",connect_timeout=3) as check:
  c=check.execute("SELECT current_database(),session_user,inet_server_port(),"
    "current_setting('frfinance.m40340_ci',true),"
    "current_setting('server_version_num')::int").fetchone()
  assert c[:4]==(DB,"postgres",5432,"DISPOSABLE_ONLY")
  assert 180000<=c[4]<190000
  assert check.execute("SELECT count(*) FROM public.sessions").fetchone()[0]==7
  for table in TABLES:
   for tenant in (A,B):
    n=check.execute("SELECT count(*) FROM public."+table+" WHERE tenant_id=%s",
                    (tenant,)).fetchone()[0]
    assert n>0,(table,"fixture missing")

 # Extra endpoints exist only in the CI process, never in deployed app code.
 @app.get("/__ci_m40340/rls",include_in_schema=False)
 async def probe(session=Depends(get_current_session),
                 conn=Depends(get_rls_db_connection)):
  context=await conn.fetchrow(
   "SELECT current_user,current_setting('app.current_user_id',true),"
   "current_setting('app.current_role',true),"
   "current_setting('app.current_tenant_id',true)")
  assert tuple(context)==("frc_ai_app",str(session.user_id),
                          session.role,str(session.tenant_id or ""))
  data={}
  for tenant in (A,B):
   data[str(tenant)]={}
   for table in TABLES:
    data[str(tenant)][table]=await conn.fetchval(
     "SELECT count(*) FROM public."+table+" WHERE tenant_id=$1",tenant)
  return {"role":session.role,"tenant":session.tenant_id,"counts":data}

 @app.get("/__ci_m40340/tenants/{tenant_id}/scope",include_in_schema=False)
 async def scope(tenant_id:str,session=Depends(get_current_session)):
  require_tenant_access(str(tenant_id),session)
  return {"authorized":True}

 # Reuse the same ORIGINAL asyncpg connection pool, never a new DB.
 # Probe directly, without the RLS dependency, AFTER prior requests released
 # their transaction-scoped credentials. No SQL modifications are allowed.
 @app.get("/__ci_m40340/pool-clean",include_in_schema=False)
 async def pool_clean(session=Depends(get_current_session)):
  pool=await get_db_pool()
  async with pool.acquire() as connection:
   values=await connection.fetchrow(
    "SELECT current_setting('app.current_user_id',true),"
    "current_setting('app.current_role',true),"
    "current_setting('app.current_tenant_id',true)")
   clean=all(v is None or v=="" for v in values)
   if not clean:
    raise HTTPException(409,"M40350_RLS_CONTEXT_POOL_LEAK")
   return {"clean":True}

 @app.get("/__ci_m40340/abort",include_in_schema=False)
 async def abort_probe(session=Depends(get_current_session),
                       conn=Depends(get_rls_db_connection)):
  await conn.fetchval("SELECT count(*) FROM public.special_credit_grants")
  raise HTTPException(409,"M40350_SYNTHETIC_ROLLBACK")

 def token(name):
  return {"Authorization":"Bearer "+TOKENS[name]}

 checks=0
 with TestClient(app) as client:
  for actor,own,other,role in (
   ("admin_a",A,B,"TENANT_ADMIN"),("admin_b",B,A,"TENANT_ADMIN"),
   ("member_a",A,B,"TENANT_MEMBER"),("member_b",B,A,"TENANT_MEMBER")):
   response=client.get("/__ci_m40340/rls",headers=token(actor))
   assert response.status_code==200,(actor,response.status_code,response.text[:150])
   body=response.json()
   assert body["role"]==role and body["tenant"]==str(own)
   cleaned=client.get("/__ci_m40340/pool-clean",headers=token(actor))
   assert cleaned.status_code==200 and cleaned.json()=={"clean":True},actor
   for table in TABLES:
    may_read=role=="TENANT_ADMIN" or table not in (
       "special_credit_outbox","special_credit_audit")
    assert (body["counts"][str(own)][table]>0)==may_read,(actor,table,"own")
    assert body["counts"][str(other)][table]==0,(actor,table,"other")
    checks+=2
   assert client.get(
    "/__ci_m40340/tenants/"+str(own)+"/scope",headers=token(actor)
   ).status_code==200
   assert client.get(
    "/__ci_m40340/tenants/"+str(other)+"/scope",
    headers={**token(actor),"X-Tenant-ID":str(other),"X-Role":"TENANT_ADMIN"}
   ).status_code==403
   cap=client.get(f"/api/v1/tenants/{own}/special-credit/capabilities",
                  headers=token(actor))
   assert cap.status_code==200,(actor,cap.status_code)
   assert cap.json()["real_credit_enabled"] is False
   assert cap.json()["pix_real_enabled"] is False
   assert cap.json()["sandbox_enabled"] is False
   assert client.get(
    f"/api/v1/tenants/{other}/special-credit/capabilities",
    headers=token(actor)).status_code==403

  # Verify cleanup after an exception while a real RLS transaction is open.
  denied=client.get("/__ci_m40340/abort",headers=token("member_b"))
  assert denied.status_code==409,denied.status_code
  after_abort=client.get("/__ci_m40340/pool-clean",headers=token("admin_a"))
  assert after_abort.status_code==200 and after_abort.json()=={"clean":True}
  # Cross-user sequence A -> B -> member -> Master -> A has no inherited GUC.
  for actor in ("admin_a","admin_b","member_a","master","admin_a"):
   cleaner=client.get("/__ci_m40340/pool-clean",headers=token(actor))
   assert cleaner.status_code==200 and cleaner.json()=={"clean":True},actor
  print("M40350_POOL_GUC_CLEAN_AFTER_CROSS_USER_AND_ROLLBACK=PASS")

  master=client.get("/__ci_m40340/rls",headers=token("master"))
  assert master.status_code==200
  assert master.json()["role"]=="MASTER"
  for values in master.json()["counts"].values():
   for table in TABLES:
    assert values[table]==0,("master",table)
    checks+=1
  assert client.get("/__ci_m40340/tenants/"+str(A)+"/scope",
                    headers=token("master")).status_code==403
  for actor in ("expired","revoked","invalid"):
   assert client.get("/__ci_m40340/rls",headers=token(actor)).status_code==401
  assert client.get("/__ci_m40340/rls").status_code==401
  assert client.get("/__ci_m40340/rls",
   headers={"X-Role":"TENANT_ADMIN","X-Tenant-ID":str(A)}).status_code==401

 assert checks==60,checks
 print("M40340_AUTH_REAL_FASTAPI_DEPENDENCY=PASS")
 print("M40340_CREDIT_RLS=PASS_6_OF_6")
 print("M40340_SESSION_BOUND_VISIBILITY=PASS_60_OF_60")
 print("M40350_ORIGINAL_POOL_REUSED=YES")
 print("M40350_SQL_SESSION_SETTING_LEAK=DENIED")
 print("M40350_LOCAL_SERVICES_RESTARTED=NO")
 print("M40340_EXPIRED_REVOKED_ANONYMOUS=DENIED")
 print("M40340_REAL_LOGIN=NOT_TESTED")
 print("M40340_AUTH_SQL_HELPERS=SYNTHETIC_NOT_PRODUCTION_PROOF")
 print("M40340_TERMUX_DB_5433=NOT_CONNECTED")
 print("M40340_LOCAL_MIGRATIONS=NONE")
 print("M40340_PIX_REAL=OFF")
 print("M40340_PRODUCTION=BLOCKED")


if __name__=="__main__":
 main()
