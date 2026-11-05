"""M16000 disposable PG16/18: synthetic inbox/outbox and restricted role checks."""
import asyncio
import os
from uuid import UUID
import asyncpg
import pytest

T=UUID("ffffffff-0000-4000-8000-000000000011")
B=UUID("ffffffff-0000-4000-8000-000000000012")
AUSER=UUID("ffffffff-0000-4000-8000-000000000001")
BUSER=UUID("ffffffff-0000-4000-8000-000000000002")
MASTER=UUID("ffffffff-0000-4000-8000-000000000003")
ADMIN=os.getenv("CI_MP_DISPOSABLE_DATABASE_URL","")
PRODUCER=os.getenv("CI_MP_NOTIFICATION_PRODUCER_URL","")
APP=os.getenv("CI_MP_NOTIFICATION_APP_URL","")
EXPECTED_ADMIN="postgresql://postgres:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
EXPECTED_WORKER="postgresql://frcaixinha_notify_producer_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging"
VALID_APPS={
 "postgresql://frcaixinha_ci:ci-test-only@127.0.0.1:5432/frcaixinha_staging",
 "postgresql://frcaixinha_pg18_app:ci-test-only@127.0.0.1:5432/frcaixinha_staging",
}
CI=(os.getenv("GITHUB_ACTIONS")=="true"
    and os.getenv("FRCAIXINHA_CI_ISOLATED")=="1"
    and ADMIN==EXPECTED_ADMIN and PRODUCER==EXPECTED_WORKER and APP in VALID_APPS)
pytestmark=(pytest.mark.asyncio,pytest.mark.skipif(not CI,reason="disposable CI only"))

def eid(n:int):return UUID(f"eeeeeeee-0000-4000-8000-{n:012d}")

async def connect(dsn,who):
 c=await asyncpg.connect(dsn,timeout=8,command_timeout=12)
 assert await c.fetchval("SELECT current_database()")=="frcaixinha_staging"
 assert await c.fetchval("SELECT session_user")==who
 await c.execute("SELECT set_config('frcaixinha.notifications_staging_ci','1',false)")
 return c

async def producer():return await connect(PRODUCER,"frcaixinha_notify_producer_ci")
async def app():return await connect(APP,"frcaixinha_ci" if "/frcaixinha_ci:" in APP else "frcaixinha_pg18_app")
async def admin():return await connect(ADMIN,"postgres")

async def emit(c,n,tenant=T,user=AUSER,role="TENANT_MEMBER",
               kind="CONTRIBUTION_DUE_INFO",cycle=2027,sha="a"*64):
 return await c.fetchval(
  "SELECT public.notification_enqueue_staging_ci("
  "$1::uuid,$2::integer,$3::uuid,$4::uuid,$5::varchar,$6::varchar,$7::varchar)",
  tenant,cycle,eid(n),user,role,kind,sha)

async def context(c,user,tenant,role):
 await c.execute("SELECT set_config('app.current_user_id',$1,true)",str(user))
 await c.execute("SELECT set_config('app.current_tenant_id',$1,true)",str(tenant) if tenant else "")
 await c.execute("SELECT set_config('app.current_role',$1,true)",role)

async def inbox(c):
 return await c.fetch(
   "SELECT id,kind,title,message,read_at,created_at FROM "
   "public.notification_inbox_staging ORDER BY created_at DESC,id DESC LIMIT 100")

async def test_01_concurrent_identical_event_exactly_once():
 async def one():
  c=await producer()
  try:return await emit(c,1)
  finally:await c.close()
 replies=await asyncio.gather(*[one() for _ in range(10)])
 assert sum(x.startswith("NEW:") for x in replies)==1
 assert sum(x.startswith("REPLAY:") for x in replies)==9
 assert len({x.split(":",1)[1] for x in replies})==1
 c=await admin()
 try:
  assert await c.fetchval("SELECT count(*) FROM public.notification_outbox_staging WHERE event_id=$1",eid(1))==1
  assert await c.fetchval(
   "SELECT count(*) FROM public.notification_inbox_staging i JOIN "
   "public.notification_outbox_staging o ON i.outbox_id=o.id WHERE o.event_id=$1",
   eid(1))==1
 finally:await c.close()

async def test_02_conflicting_replay_rejected():
 c=await producer()
 try:
  assert (await emit(c,2)).startswith("NEW:")
  with pytest.raises(asyncpg.PostgresError):
   await emit(c,2,sha="b"*64)
  with pytest.raises(asyncpg.PostgresError):
   await emit(c,2,kind="FINANCIAL_STATUS_UNVERIFIED")
 finally:await c.close()

async def test_03_cross_tenant_wrong_role_year_rejected():
 c=await producer()
 try:
  for args in (
   {"tenant":B,"user":AUSER},{"tenant":T,"user":BUSER},
   {"role":"TENANT_ADMIN"},{"cycle":2028},
   {"tenant":None,"role":"MASTER","cycle":None},
  ):
   with pytest.raises(asyncpg.PostgresError):
    await emit(c,3,**args)
 finally:await c.close()

async def test_04_recipient_only_select_with_independent_tenants():
 c=await producer()
 try:
  assert (await emit(c,4,tenant=B,user=BUSER)).startswith("NEW:")
 finally:await c.close()
 a=await app()
 try:
  async with a.transaction():
   await context(a,BUSER,B,"TENANT_MEMBER")
   items=await inbox(a)
   assert len(items)==1
  async with a.transaction():
   await context(a,AUSER,B,"TENANT_MEMBER")
   assert await inbox(a)==[]
  async with a.transaction():
   await context(a,AUSER,T,"TENANT_ADMIN")
   assert await inbox(a)==[]
  async with a.transaction():
   await context(a,AUSER,T,"TENANT_MEMBER")
   items=await inbox(a)
   assert len(items)==2
 finally:await a.close()

async def test_05_no_direct_app_write_and_worker_read():
 a=await app();p=await producer()
 try:
  for privilege in ("INSERT","UPDATE","DELETE","TRUNCATE"):
   assert await a.fetchval(
    "SELECT has_table_privilege(current_user,'public.notification_inbox_staging',$1)",privilege
   ) is False
  assert await a.fetchval(
   "SELECT has_table_privilege(current_user,'public.notification_outbox_staging','SELECT')"
  ) is False
  for privilege in ("SELECT","INSERT","UPDATE","DELETE"):
   for table in ("notification_inbox_staging","notification_outbox_staging"):
    assert await p.fetchval(
      f"SELECT has_table_privilege(current_user,'public.{table}',$1)",privilege
    ) is False
  with pytest.raises(asyncpg.InsufficientPrivilegeError):
   await p.fetchval("SELECT count(*) FROM public.notification_inbox_staging")
 finally:await a.close();await p.close()

async def test_06_mark_read_is_monotonic_and_scoped():
 p=await producer()
 try:assert (await emit(p,6)).startswith("NEW:")
 finally:await p.close()
 a=await app()
 try:
  async with a.transaction():
   await context(a,AUSER,T,"TENANT_MEMBER")
   notice=await a.fetchrow(
    "SELECT i.id,i.read_at FROM public.notification_inbox_staging i "
    "JOIN public.notification_outbox_staging o ON i.outbox_id=o.id "
    "WHERE o.event_id=$1",eid(6))
   # Direct outbox SELECT is forbidden even in the same tenant; use inbox alone.
 except asyncpg.InsufficientPrivilegeError:
  pass
 finally:await a.close()
 a=await app()
 try:
  async with a.transaction():
   await context(a,AUSER,T,"TENANT_MEMBER")
   items=await inbox(a)
   notice_id=next(x["id"] for x in items if x["title"]=="Contribuição a conferir")
   assert await a.fetchval(
      "SELECT public.notification_mark_read_staging_ci($1::uuid)",notice_id
   ) in ("READ","ALREADY_READ")
   assert await a.fetchval(
      "SELECT public.notification_mark_read_staging_ci($1::uuid)",notice_id
   )=="ALREADY_READ"
  async with a.transaction():
   await context(a,BUSER,B,"TENANT_MEMBER")
   assert await a.fetchval(
      "SELECT public.notification_mark_read_staging_ci($1::uuid)",notice_id
   )=="NOT_FOUND"
 finally:await a.close()

async def test_07_keyset_page_limit_scope():
 p=await producer()
 try:
  for n in range(70,76):
   assert (await emit(p,n)).startswith("NEW:")
 finally:await p.close()
 a=await app()
 try:
  async with a.transaction():
   await context(a,AUSER,T,"TENANT_MEMBER")
   first=await a.fetch(
    "SELECT id,created_at FROM public.notification_inbox_staging "
    "ORDER BY created_at DESC,id DESC LIMIT 3")
   assert len(first)==3
   last=first[-1]
   second=await a.fetch(
    "SELECT id,created_at FROM public.notification_inbox_staging "
    "WHERE (created_at,id)<($1::timestamptz,$2::uuid) "
    "ORDER BY created_at DESC,id DESC LIMIT 3",
    last["created_at"],last["id"])
   assert len(second)==3
   assert not {x["id"] for x in first}&{x["id"] for x in second}
  async with a.transaction():
   await context(a,BUSER,B,"TENANT_MEMBER")
   assert len(await inbox(a))==1
 finally:await a.close()

async def test_08_master_platform_only():
 c=await admin()
 try:
  await c.execute(
   "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master) "
   "VALUES($1,'master-notification-ci@example.invalid','Master CI',"
   "'88888888888833','00000000003',true) ON CONFLICT(id) DO NOTHING",MASTER)
 finally:await c.close()
 p=await producer()
 try:
  assert (await emit(p,8,None,MASTER,"MASTER","SECURITY_SESSION_ALERT",None)).startswith("NEW:")
  with pytest.raises(asyncpg.PostgresError):
   await emit(p,9,None,MASTER,"MASTER","CONTRIBUTION_DUE_INFO",None)
 finally:await p.close()
 a=await app()
 try:
  async with a.transaction():
   await context(a,MASTER,None,"MASTER")
   items=await inbox(a)
   assert len(items)==1 and items[0]["kind"]=="SECURITY_SESSION_ALERT"
  async with a.transaction():
   await context(a,MASTER,T,"MASTER")
   assert await inbox(a)==[]
 finally:await a.close()

async def test_09_rollback_cancels_outbox_and_inbox():
 p=await producer()
 try:
  with pytest.raises(RuntimeError):
   async with p.transaction():
    assert (await emit(p,10)).startswith("NEW:")
    raise RuntimeError("CI crash")
 finally:await p.close()
 c=await admin()
 try:
  assert await c.fetchval(
   "SELECT count(*) FROM public.notification_outbox_staging WHERE event_id=$1",eid(10))==0
 finally:await c.close()

async def test_10_no_financial_or_delivery_effects():
 c=await admin()
 try:
  data=await c.fetch(
   "SELECT delivery_status,event_authenticated,bank_reconciled,"
   "financial_effect_applied FROM public.notification_outbox_staging")
  assert data
  for r in data:
   assert r["delivery_status"]=="HELD_CI_NO_DELIVERY"
   assert not r["event_authenticated"]
   assert not r["bank_reconciled"]
   assert not r["financial_effect_applied"]
  assert await c.fetchval("SELECT count(*) FROM public.notification_inbox_staging")==len(data)
 finally:await c.close()
