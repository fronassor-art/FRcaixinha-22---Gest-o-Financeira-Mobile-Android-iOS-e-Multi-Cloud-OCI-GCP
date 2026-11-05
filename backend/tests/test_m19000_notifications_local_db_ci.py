"""M19000 physical notification local migration, PG16 and PG18 disposable."""
import os
import hashlib
import asyncpg
import pytest
from uuid import UUID

APP=os.getenv("CI_MP_NOTIFICATION_APP_URL","")
ADMIN=os.getenv("CI_MP_DISPOSABLE_DATABASE_URL","")
VALID={"postgresql://frcaixinha_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging",
"postgresql://frcaixinha_pg18_app:ci-test-only@127.0.0.1:5432/frcaixinha_staging"}
AUTH=os.getenv("CI_MP_NOTIFICATION_AUTH_URL","")
VALID_AUTH={
 "postgresql://frcaixinha_auth_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging",
 "postgresql://frcaixinha_pg18_auth:ci-test-only@127.0.0.1:5432/frcaixinha_staging",
}
READY=os.getenv("GITHUB_ACTIONS")=="true" and os.getenv("FRCAIXINHA_CI_ISOLATED")=="1" and APP in VALID and AUTH in VALID_AUTH and ADMIN=="postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
pytestmark=[pytest.mark.asyncio,pytest.mark.skipif(not READY,reason="disposable staging only")]
T=UUID("ffffffff-0000-4000-8000-000000000011")
B=UUID("ffffffff-0000-4000-8000-000000000012")
U=UUID("ffffffff-0000-4000-8000-000000000001")
V=UUID("ffffffff-0000-4000-8000-000000000002")
M=UUID("ffffffff-0000-4000-8000-000000000003")

async def app():
 c=await asyncpg.connect(APP,timeout=8,command_timeout=10)
 assert await c.fetchval("SELECT current_database()")=="frcaixinha_staging"
 return c
async def owner():return await asyncpg.connect(ADMIN,timeout=8)
async def scope(c,u=U,t=T,role="TENANT_MEMBER"):
 await c.execute("SELECT set_config('app.current_user_id',$1,true)",str(u))
 await c.execute("SELECT set_config('app.current_tenant_id',$1,true)",str(t) if t else "")
 await c.execute("SELECT set_config('app.current_role',$1,true)",role)

async def test_01_rls_and_privileges():
 c=await app()
 try:
  assert await c.fetchval("SELECT to_regclass('public.notification_inbox') IS NOT NULL")
  r=await c.fetchrow("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='public.notification_inbox'::regclass")
  assert r["relrowsecurity"] and r["relforcerowsecurity"]
  assert await c.fetchval("SELECT has_table_privilege(current_user,'public.notification_inbox','SELECT')")
  for p in ("INSERT","UPDATE","DELETE","TRUNCATE"):
   assert not await c.fetchval("SELECT has_table_privilege(current_user,'public.notification_inbox',$1)",p)
  assert not await c.fetchval("SELECT has_table_privilege(current_user,'public.users','SELECT')")
 finally:await c.close()

async def test_02_master_selftest_only_platform():
 c=await app()
 try:
  async with c.transaction():
   await scope(c,M,None,"MASTER")
   mid=await c.fetchval("SELECT public.notification_local_create_selftest()")
   r=await c.fetch("SELECT id,tenant_id,recipient_role FROM public.notification_inbox")
   assert len(r)==1 and r[0]["id"]==mid and r[0]["tenant_id"] is None and r[0]["recipient_role"]=="MASTER"
 finally:await c.close()

async def test_03_member_read_receipt():
 c=await app()
 try:
  async with c.transaction():
   await scope(c)
   mid=await c.fetchval("SELECT public.notification_local_create_selftest()")
   r=await c.fetch("SELECT id,kind,message,read_at FROM public.notification_inbox")
   assert len(r)==1 and r[0]["id"]==mid and r[0]["kind"]=="SELF_TEST"
   assert "Nenhum pagamento" in r[0]["message"] and r[0]["read_at"] is None
   assert await c.fetchval("SELECT public.notification_local_mark_read($1::uuid)",mid)=="READ"
   assert await c.fetchval("SELECT public.notification_local_mark_read($1::uuid)",mid)=="ALREADY_READ"
 finally:await c.close()

async def test_04_other_tenant_no_read_receipt():
 c=await app()
 try:
  async with c.transaction():
   await scope(c)
   original=await c.fetchval("SELECT id FROM public.notification_inbox LIMIT 1")
  async with c.transaction():
   await scope(c,V,B)
   another=await c.fetchval("SELECT public.notification_local_create_selftest()")
   assert another!=original
   r=await c.fetch("SELECT id FROM public.notification_inbox")
   assert len(r)==1 and r[0]["id"]==another
   assert await c.fetchval("SELECT public.notification_local_mark_read($1::uuid)",original)=="NOT_FOUND"
  async with c.transaction():
   await scope(c,U,B)
   assert await c.fetchval("SELECT count(*) FROM public.notification_inbox")==0
   with pytest.raises(asyncpg.PostgresError):
    async with c.transaction():
     await c.fetchval("SELECT public.notification_local_create_selftest()")
 finally:await c.close()

async def test_05_suspended_member_blocked():
 admin=await owner();c=await app()
 try:
  await admin.execute("UPDATE public.memberships SET status='SUSPENSA' WHERE tenant_id=$1 AND user_id=$2 AND role='TENANT_MEMBER'",T,U)
  async with c.transaction():
   await scope(c)
   assert await c.fetchval("SELECT count(*) FROM public.notification_inbox")==0
   with pytest.raises(asyncpg.PostgresError):
    async with c.transaction():
     await c.fetchval("SELECT public.notification_local_create_selftest()")
 finally:
  await admin.execute("UPDATE public.memberships SET status='ATIVA' WHERE tenant_id=$1 AND user_id=$2 AND role='TENANT_MEMBER'",T,U)
  await c.close();await admin.close()

async def test_06_10_notice_rate_limit():
 c=await app()
 try:
  async with c.transaction():
   await scope(c)
   for _ in range(9):
    assert await c.fetchval("SELECT public.notification_local_create_selftest()")
   with pytest.raises(asyncpg.PostgresError):
    async with c.transaction():
     await c.fetchval("SELECT public.notification_local_create_selftest()")
 finally:await c.close()

async def test_07_no_financial_claims_or_external_delivery():
 c=await owner()
 try:
  r=await c.fetch("SELECT kind,title,message FROM public.notification_inbox")
  assert len(r)>=12
  for x in r:
   assert x["kind"]=="SELF_TEST" and x["title"]=="Aviso de teste interno"
   assert "Nenhum pagamento ou envio externo" in x["message"]
 finally:await c.close()


async def test_08_server_issued_session_notice_is_real_inbox_event():
 """Synthetic bearer verified by DB. Only session service can publish."""
 owner=await asyncpg.connect(ADMIN,timeout=8)
 auth=await asyncpg.connect(AUTH,timeout=8)
 app_conn=await app()
 raw="M19000-CI-only-session-token-long-enough-20261105-01"
 try:
  session_id=await owner.fetchval(
   "INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at) "
   "VALUES($1,$2,'TENANT_MEMBER',$3,NOW()+interval '15 minutes') RETURNING id",
   hashlib.sha256(raw.encode()).hexdigest(),U,T)
  alert=await auth.fetchval(
    "SELECT public.notification_local_session_issued($1::text)",raw)
  assert alert is not None
  assert await auth.fetchval(
    "SELECT public.notification_local_session_issued($1::text)",raw)==alert
  async with app_conn.transaction():
   await scope(app_conn)
   found=await app_conn.fetchrow(
    "SELECT id,kind,title,message,event_id FROM public.notification_inbox WHERE id=$1",alert)
   assert found["event_id"]==session_id
   assert found["kind"]=="SECURITY_SESSION_ALERT"
   assert found["title"]=="Novo acesso à conta"
   assert "sessão" in found["message"]
  with pytest.raises(asyncpg.PostgresError):
   await auth.fetchval("SELECT public.notification_local_session_issued('not-a-real-token')")
 finally:
  await app_conn.close()
  await auth.close()
  await owner.close()

async def test_09_app_cannot_forge_session_event():
 c=await app()
 try:
  async with c.transaction():
   await scope(c)
   assert not await c.fetchval(
    "SELECT has_function_privilege(current_user,"
    "'public.notification_local_session_issued(text)','EXECUTE')")
 finally:await c.close()


async def test_10_master_identity_multi_role_notifications_are_isolated():
 """The same Master user can have independently authorized tenant roles."""
 admin=await owner()
 app_conn=await app()
 auth=await asyncpg.connect(AUTH,timeout=8)
 try:
  assert await admin.fetchval("SELECT is_master FROM public.users WHERE id=$1",M) is True
  for role in ("TENANT_ADMIN","TENANT_MEMBER"):
   await admin.execute(
    "INSERT INTO public.memberships(tenant_id,user_id,role,status) "
    "VALUES($1,$2,$3,'ATIVA') ON CONFLICT(tenant_id,user_id,role) DO NOTHING",
    T,M,role)
   assert await admin.fetchval(
    "SELECT EXISTS(SELECT 1 FROM public.memberships "
    "WHERE tenant_id=$1 AND user_id=$2 AND role=$3 AND status='ATIVA')",
    T,M,role) is True

  for role in ("TENANT_ADMIN","TENANT_MEMBER"):
   async with app_conn.transaction():
    await scope(app_conn,M,T,role)
    notice=await app_conn.fetchval("SELECT public.notification_local_create_selftest()")
    assert notice
    own=await app_conn.fetch(
     "SELECT id,recipient_role FROM public.notification_inbox")
    assert len(own)==1 and own[0]["id"]==notice and own[0]["recipient_role"]==role

   raw=f"M19000-CI-only-Master-three-contexts-{role}-session-token"
   session_id=await admin.fetchval(
    "INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at) "
    "VALUES($1,$2,$3,$4,NOW()+interval '15 minutes') RETURNING id",
    hashlib.sha256(raw.encode()).hexdigest(),M,role,T)
   event=await auth.fetchval(
    "SELECT public.notification_local_session_issued($1::text)",raw)
   assert event is not None
   async with app_conn.transaction():
    await scope(app_conn,M,T,role)
    observed=await app_conn.fetchrow(
     "SELECT id,event_id,kind FROM public.notification_inbox WHERE id=$1",event)
    assert observed and observed["event_id"]==session_id
    assert observed["kind"]=="SECURITY_SESSION_ALERT"

  async with app_conn.transaction():
   await scope(app_conn,M,None,"MASTER")
   own=await app_conn.fetch(
    "SELECT tenant_id,recipient_role FROM public.notification_inbox")
   assert own and all(r["tenant_id"] is None and r["recipient_role"]=="MASTER" for r in own)
  async with app_conn.transaction():
   await scope(app_conn,M,B,"TENANT_MEMBER")
   assert await app_conn.fetchval(
    "SELECT count(*) FROM public.notification_inbox")==0
 finally:
  await auth.close()
  await app_conn.close()
  await admin.close()
