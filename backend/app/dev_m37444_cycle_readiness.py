"""M37444 — original PG18 cycle-opening READINESS, never opens a cycle.

No data identifiers or tokens are returned; no DB writes or live auth attempts.
"""
from __future__ import annotations
from dataclasses import dataclass

IDENTITY_SQL="""SELECT current_database(),session_user,current_user,
inet_server_port(),current_setting('data_directory'),
current_setting('server_version_num')::int,current_setting('transaction_read_only')"""
READINESS_SQL="""
SELECT
 (SELECT count(*)::int FROM public.cycles),
 (SELECT count(*)::int FROM public.policies),
 (SELECT count(*)::int FROM public.quotas),
 (SELECT count(*)::int FROM public.contributions),
 (SELECT count(*)::int FROM public.cycle_contribution_price_audit),
 (SELECT count(*)::int FROM public.cycle_opening_audit),
 (SELECT count(*)::int FROM public.users),
 (SELECT count(*)::int FROM public.tenants),
 (SELECT count(*)::int FROM public.memberships),
 (SELECT count(*)::int FROM public.sessions),
 (SELECT count(*)::int FROM public.audit_events),
 (SELECT count(*)::int FROM public.tenants t WHERE t.status='ATIVO'),
 (SELECT count(*)::int FROM public.memberships m
   JOIN public.tenants t ON t.id=m.tenant_id AND t.admin_user_id=m.user_id
   WHERE t.status='ATIVO' AND m.role='TENANT_ADMIN' AND m.status='ATIVA'),
 (SELECT count(*)::int FROM pg_catalog.pg_class c
   WHERE c.oid='public.cycle_opening_audit'::regclass
   AND c.relrowsecurity AND c.relforcerowsecurity),
 (SELECT count(*)::int FROM pg_catalog.pg_trigger tr
   WHERE tr.tgrelid='public.cycle_opening_audit'::regclass AND NOT tr.tgisinternal
   AND tr.tgenabled='O'
   AND tr.tgname IN('cycle_opening_immutable_row','cycle_opening_immutable_truncate')),
 (SELECT count(*)::int FROM pg_catalog.pg_proc p
   WHERE p.oid=to_regprocedure('public.cycle_open_create(text,uuid,integer,bigint,text,uuid)')
   AND p.prosecdef),
 (SELECT count(*)::int FROM pg_catalog.pg_proc p
   WHERE p.oid=to_regprocedure('public.cycle_price_admin_actor(text,uuid)')
   AND p.prosecdef),
 (SELECT count(*)::int FROM pg_catalog.pg_constraint co
   JOIN pg_catalog.pg_class c ON c.oid=co.conrelid
   JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
   WHERE n.nspname='public' AND co.contype='c' AND co.convalidated
     AND position('150' in pg_get_constraintdef(co.oid))>0
     AND ((c.relname='policies' AND co.conname='policy_minimum_150_new')
       OR (c.relname='quotas' AND co.conname='quota_minimum_150_new'))),
 (SELECT count(*)::int FROM information_schema.columns
   WHERE table_schema='public' AND column_default IS NOT NULL
     AND ((table_name='policies' AND column_name='contribution_per_quota')
       OR (table_name='quotas' AND column_name='value_brl'))),
 (SELECT count(*)::int FROM public.pix_payment_intents),
 (SELECT count(*)::int FROM public.ledger_transactions),
 (SELECT count(*)::int FROM public.ledger_entries),
 (SELECT count(*)::int FROM public.loans)
"""
PERMISSIONS_SQL="""
SELECT
 COALESCE(has_function_privilege('frcaixinha_app_role',
   to_regprocedure('public.cycle_open_create(text,uuid,integer,bigint,text,uuid)'),'EXECUTE'),false),
 COALESCE(has_function_privilege('frcaixinha_auth_role',
   to_regprocedure('public.cycle_open_create(text,uuid,integer,bigint,text,uuid)'),'EXECUTE'),false),
 COALESCE(has_table_privilege('frcaixinha_app_role',
   'public.cycle_opening_audit','INSERT'),false),
 COALESCE(has_table_privilege('frcaixinha_auth_role',
   'public.cycle_opening_audit','SELECT'),false)
"""
EXPECTED=(0,0,0,0,0,0,1,1,2,None,6,1,1,1,2,1,1,2,0,0,0,0,0)
KEYS=("CYCLES","POLICIES","QUOTAS","CONTRIBUTIONS","PRICE_AUDITS",
      "OPENING_AUDITS","USERS","TENANTS","MEMBERSHIPS","SESSIONS",
      "GENERAL_AUDITS","ACTIVE_TENANT","ACTIVE_TENANT_ADMIN",
      "OPENING_AUDIT_RLS_FORCE","OPENING_AUDIT_IMMUTABLE_TRIGGERS",
      "OPENING_FUNCTION_SECURITY_DEFINER","ADMIN_AUTH_FUNCTION_SECURITY_DEFINER",
      "VALIDATED_MINIMUM_150_CHECKS","PRICE_DEFAULTS","PIX",
      "LEDGER_TRANSACTIONS","LEDGER_ENTRIES","LOANS")
EXPECTED_PERMISSIONS=(True,False,False,False)

class CycleReadinessBlocked(ValueError):
    pass

@dataclass(frozen=True)
class CycleReadiness:
    counts:tuple[int,...]
    permissions:tuple[bool,...]

def validate(counts,permissions):
    if (type(counts) is not tuple or len(counts)!=len(EXPECTED)
        or any(type(v) is not int or not 0<=v<=100000000 for v in counts)):
        raise CycleReadinessBlocked("INVALID_READINESS_COUNT_RESPONSE")
    if (type(permissions) is not tuple or len(permissions)!=4
        or any(type(x) is not bool for x in permissions)):
        raise CycleReadinessBlocked("INVALID_ROLE_PRIVILEGE_RESPONSE")
    for index,(actual,expected) in enumerate(zip(counts,EXPECTED)):
        if index==9:
            if actual<1:
                raise CycleReadinessBlocked("EXISTING_SESSIONS_NOT_PRESENT")
        elif actual!=expected:
            raise CycleReadinessBlocked("READINESS_"+KEYS[index]+"_MISMATCH")
    if permissions!=EXPECTED_PERMISSIONS:
        raise CycleReadinessBlocked("CYCLE_OPEN_ROLE_PRIVILEGES_UNSAFE")
    return CycleReadiness(counts,permissions)

def examine(conn):
    try:
        identity=conn.execute(IDENTITY_SQL).fetchone()
    except Exception:
        raise CycleReadinessBlocked("ORIGINAL_PG18_IDENTITY_READ_FAILED") from None
    if (type(identity) is not tuple or len(identity)!=7
        or identity[:5]!=("frcaixinha_aistudio_dev","frc_ai_owner","frc_ai_owner",
          5433,"/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18")
        or type(identity[5]) is not int or not 180000<=identity[5]<190000
        or identity[6]!="on"):
        raise CycleReadinessBlocked("WRONG_OR_WRITABLE_POSTGRES18")
    try:
        counts=conn.execute(READINESS_SQL).fetchone()
        permissions=conn.execute(PERMISSIONS_SQL).fetchone()
    except Exception:
        raise CycleReadinessBlocked("CYCLE_READINESS_CATALOG_READ_FAILED") from None
    return validate(counts,permissions)

def report(r):
    if not isinstance(r,CycleReadiness):
        raise CycleReadinessBlocked("INVALID_READINESS_REPORT")
    return (
        "=== FR FINANCE M37444 CYCLE OPENING ORIGINAL PG18 READ ONLY ===",
        "M37444_STATUS=READ_ONLY_PASS",
        "M37444_OLD_CYCLE_AND_FINANCIAL_FIXTURES=ZERO",
        "M37444_USERS=1",
        "M37444_TENANT=1_ACTIVE",
        "M37444_MEMBERSHIPS=2_PRESERVED",
        "M37444_TENANT_ADMIN=1_ACTIVE",
        "M37444_SESSIONS_PRESENT=YES",
        "M37444_SESSIONS_COUNT="+str(r.counts[9]),
        "M37444_GENERAL_AUDITS=6_PRESERVED",
        "M37444_CYCLE_OPENING_AUDIT=RLS_FORCE",
        "M37444_CYCLE_OPENING_AUDIT_TRIGGERS=2_ENABLED",
        "M37444_SERVER_OPENING_FUNCTION=SECURITY_DEFINER_PRESENT",
        "M37444_ADMIN_AUTH_FUNCTION=SECURITY_DEFINER_PRESENT",
        "M37444_APP_ROLE_EXECUTE=YES",
        "M37444_AUTH_ROLE_EXECUTE=NO",
        "M37444_DIRECT_AUDIT_INSERT=DENIED",
        "M37444_MINIMUM_150_SQL_CONSTRAINTS=2_VALIDATED",
        "M37444_QUOTA_PRICE_DEFAULTS=0",
        "M37444_PIX_LEDGER_LOANS=NONE",
        "M37444_NEW_CYCLE=NOT_CREATED",
        "M37444_REAL_ADMIN_LOGIN=NOT_TESTED",
        "M37444_REAL_PAYMENT=OFF",
        "M37444_DB_WRITES=NONE",
        "M37444_NEW_DATABASE=NO"
    )
