"""M37443 independent read-only attestation after M37442, original PG18 only."""
from dataclasses import dataclass

IDENTITY="""SELECT current_database(),session_user,current_user,inet_server_port(),
current_setting('data_directory'),current_setting('server_version_num')::int,
current_setting('transaction_read_only')"""
CORE="""SELECT
(SELECT count(*)::int FROM public.cycles),
(SELECT count(*)::int FROM public.policies),
(SELECT count(*)::int FROM public.quotas),
(SELECT count(*)::int FROM public.contributions),
(SELECT count(*)::int FROM public.cycle_contribution_price_audit),
(SELECT count(*)::int FROM public.users),
(SELECT count(*)::int FROM public.tenants),
(SELECT count(*)::int FROM public.memberships),
(SELECT count(*)::int FROM public.audit_events),
(SELECT count(*)::int FROM pg_trigger WHERE
 tgrelid='public.cycle_contribution_price_audit'::regclass
 AND NOT tgisinternal AND tgenabled='O'
 AND tgname IN('cycle_price_immutable_row','cycle_price_immutable_truncate'))
"""
EXTRA="""SELECT
(SELECT count(*)::int FROM public.sessions),
(SELECT count(*)::int FROM public.audit_events a
 WHERE a.action='DEV_SYNTHETIC_RESET_M37437'
 AND a.object_id='M37437_SYNTHETIC_2027'
 AND a.evidence_ref='BACKUP_SHA256:714bc50de8dfc42d25f1b9bbe54e9841df883f0d606f467015c0e153b4d9b88b'
 AND EXISTS(SELECT 1 FROM public.tenants t
 WHERE t.id=a.tenant_id AND t.admin_user_id=a.actor_id)),
(SELECT count(*)::int FROM public.audit_events a
 WHERE a.tenant_id IN(
 SELECT tenant_id FROM public.audit_events
 WHERE action='DEV_SYNTHETIC_RESET_M37437')),
(SELECT count(*)::int FROM public.audit_events WHERE tenant_id IS NULL),
(SELECT count(*)::int FROM pg_constraint co
 JOIN pg_class c ON c.oid=co.conrelid
 JOIN pg_namespace ns ON ns.oid=c.relnamespace
 WHERE ns.nspname='public' AND co.contype='c' AND co.convalidated
 AND ((c.relname='policies' AND co.conname='policy_minimum_150_new')
 OR (c.relname='quotas' AND co.conname='quota_minimum_150_new'))
 AND position('150' in pg_get_constraintdef(co.oid))>0),
(SELECT count(*)::int FROM information_schema.columns
 WHERE table_schema='public' AND column_default IS NOT NULL
 AND ((table_name='policies' AND column_name='contribution_per_quota')
 OR (table_name='quotas' AND column_name='value_brl'))),
(SELECT count(*)::int FROM public.pix_payment_intents),
(SELECT count(*)::int FROM public.ledger_transactions),
(SELECT count(*)::int FROM public.ledger_entries),
(SELECT count(*)::int FROM public.loans),
(SELECT count(*)::int FROM public.cycle_opening_audit),
(SELECT count(*)::int FROM public.contributions
 WHERE amount_due<150 OR amount_paid>0 OR paid_at IS NOT NULL),
(SELECT count(*)::int FROM public.policies WHERE contribution_per_quota<150),
(SELECT count(*)::int FROM public.quotas WHERE value_brl<150),
(SELECT count(*)::int FROM public.cycle_contribution_price_audit
 WHERE old_price_cents<15000 OR requested_price_cents<15000)
"""
CORE_EXPECTED=(0,0,0,0,0,1,1,2,6,2)
EXTRA_KEYS=("SESSIONS","RESET_EVIDENCE","TENANT_AUDITS","GLOBAL_AUDITS",
 "VALIDATED_150_CHECKS","PRICE_DEFAULTS","PIX","LEDGER_TRANSACTIONS",
 "LEDGER_ENTRIES","LOANS","OPENING_AUDITS","CONTRIBUTION_ANOMALIES",
 "LEGACY_POLICIES","LEGACY_QUOTAS","LEGACY_PRICE_AUDITS")
EXTRA_EXPECTED=(None,1,4,2,2,0,0,0,0,0,0,0,0,0,0)
class AuditBlocked(ValueError):pass
@dataclass(frozen=True)
class AuditEvidence:
    core:tuple
    extra:tuple

def validate(core,extra):
    for row,length in ((core,10),(extra,15)):
        if (type(row) is not tuple or len(row)!=length or
            any(type(n) is not int or not 0<=n<=100000000 for n in row)):
            raise AuditBlocked("INVALID_READ_ONLY_AGGREGATES")
    if core!=CORE_EXPECTED:raise AuditBlocked("POST_RESET_CORE_CHANGED")
    if extra[0]<1:raise AuditBlocked("ORIGINAL_SESSION_RECORDS_MISSING")
    for key,observed,expected in zip(EXTRA_KEYS[1:],extra[1:],EXTRA_EXPECTED[1:]):
        if observed!=expected:
            raise AuditBlocked("POST_RESET_"+key+"_MISMATCH")
    return AuditEvidence(core,extra)

def examine(conn):
    try:
        identity=conn.execute(IDENTITY).fetchone()
    except Exception:raise AuditBlocked("PG18_IDENTITY_READ_FAILED") from None
    if (type(identity) is not tuple or len(identity)!=7 or
        identity[:5]!=("frcaixinha_aistudio_dev","frc_ai_owner","frc_ai_owner",
          5433,"/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18") or
        type(identity[5]) is not int or not 180000<=identity[5]<190000 or
        identity[6]!="on"):
        raise AuditBlocked("WRONG_OR_NON_READONLY_PG18")
    try:
        core=conn.execute(CORE).fetchone()
        extra=conn.execute(EXTRA).fetchone()
    except Exception:raise AuditBlocked("POST_RESET_SQL_READ_FAILED") from None
    return validate(core,extra)

def report(e):
    if not isinstance(e,AuditEvidence):raise AuditBlocked("INVALID_REPORT")
    return (
      "=== FR FINANCE M37443 READ ONLY POST RESET ===",
      "M37443_STATUS=READ_ONLY_PASS",
      "M37443_LEGACY_CYCLE=0",
      "M37443_LEGACY_POLICIES=0",
      "M37443_LEGACY_QUOTAS=0",
      "M37443_LEGACY_CONTRIBUTIONS=0",
      "M37443_LEGACY_PRICE_AUDITS=0",
      "M37443_USERS=1",
      "M37443_TENANTS=1",
      "M37443_MEMBERSHIPS=2",
      "M37443_SESSIONS_COUNT="+str(e.extra[0]),
      "M37443_AUDIT_EVENTS=6",
      "M37443_RESET_EVIDENCE=1",
      "M37443_AFFECTED_TENANT_AUDIT=4",
      "M37443_OTHER_AUDIT=2",
      "M37443_PRICE_AUDIT_TRIGGERS=2_ENABLED",
      "M37443_MINIMUM_150_CHECKS=2_VALIDATED",
      "M37443_PRICE_DEFAULTS=0",
      "M37443_PIX_LEDGER_LOANS=0",
      "M37443_CYCLE_OPENING=NOT_TESTED",
      "M37443_NEW_DATABASE=NO",
      "M37443_DB_WRITES=NONE",
      "M37443_PIX_REAL=OFF",
      "M37443_ACTIVATION_REAL=OFF"
    )
