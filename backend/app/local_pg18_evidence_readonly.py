"""FR Finance M37361-M37370: local PG18 schema evidence, catalog only.

No DDL, data rows, token values, payments, or migration execution.
The audit reports structural presence, NOT per-migration execution history.
"""
from __future__ import annotations
from dataclasses import dataclass

PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
DBNAME="frcaixinha_aistudio_dev"
PORT=5433
ROLE="frc_ai_owner"

class LocalEvidenceBlocked(ValueError):
    """Fixed, non-sensitive reason codes only."""

IDENTITY_SQL="""
SELECT current_database(),current_user,inet_server_port(),
 current_setting('server_version_num')::integer,
 current_setting('data_directory'),
 current_setting('transaction_read_only')
"""
LIFECYCLE_SQL="""
SELECT COUNT(*)=2 AND COALESCE(bool_and(c.relrowsecurity AND c.relforcerowsecurity),false)
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p')
 AND c.relname IN ('member_lifecycle_requests','member_lifecycle_review_events')
"""
ROUND_INDEX_SQL="""
SELECT EXISTS (SELECT 1 FROM pg_indexes
 WHERE schemaname='public' AND indexname='member_lifecycle_case_round_lookup')
"""
PARITY_SQL="""
SELECT COUNT(*)=8 AND COALESCE(bool_and(
 c.relrowsecurity AND c.relforcerowsecurity
 AND NOT has_table_privilege('frc_ai_app',c.oid,'SELECT')
 AND NOT has_table_privilege('frc_ai_app',c.oid,'INSERT')
 AND NOT has_table_privilege('frc_ai_auth',c.oid,'SELECT')
 AND NOT has_table_privilege('frc_ai_auth',c.oid,'UPDATE')
),false)
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p')
 AND c.relname IN (
 'local_m034_webhook_evidence','local_m035_pix_dryrun',
 'local_m036_orders_inbox','local_m037_order_evidence',
 'local_m038_order_reservation','local_m039_reconciliation_hold',
 'local_m040_incident_audit','local_m041_notification_outbox')
"""
INBOX_SQL="""
SELECT COUNT(*)=1 AND COALESCE(bool_and(c.relrowsecurity AND c.relforcerowsecurity),false)
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relkind IN ('r','p')
 AND c.relname='notification_inbox'
"""
PRICE_SQL="""
SELECT
 (SELECT COUNT(*) FROM pg_constraint co
  JOIN pg_class c ON c.oid=co.conrelid
  JOIN pg_namespace n ON n.oid=c.relnamespace
  WHERE n.nspname='public' AND co.contype='c'
  AND NOT co.convalidated
  AND ((c.relname='policies' AND co.conname='policy_minimum_150_new')
    OR (c.relname='quotas' AND co.conname='quota_minimum_150_new'))
  AND position('150' in pg_get_constraintdef(co.oid))>0)=2
 AND
 (SELECT COUNT(*) FROM information_schema.columns
  WHERE table_schema='public' AND column_default IS NOT NULL
  AND ((table_name='policies' AND column_name='contribution_per_quota')
    OR (table_name='quotas' AND column_name='value_brl')))=0
 AND to_regprocedure('public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)') IS NOT NULL
 AND to_regprocedure('public.cycle_price_change_legacy_m20400(text,uuid,uuid,bigint,text,uuid)') IS NOT NULL
 AND COALESCE(has_function_privilege('frcaixinha_app_role',
  to_regprocedure('public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)'),'EXECUTE'),false)
 AND NOT COALESCE(has_function_privilege('frcaixinha_app_role',
  to_regprocedure('public.cycle_price_change_legacy_m20400(text,uuid,uuid,bigint,text,uuid)'),'EXECUTE'),true)
"""

@dataclass(frozen=True)
class LocalEvidence:
    lifecycle: bool
    synthetic_parity: bool
    inbox: bool
    price_043: bool
    auth_baseline: bool
    catalog_read_only: bool=True
    per_file_migration_history_verified: bool=False
    db_writes: bool=False
    payments_authorized: bool=False
    users_authorized: bool=False

def _one(conn,sql):
    try:
        row=conn.execute(sql).fetchone()
    except Exception:
        raise LocalEvidenceBlocked("LOCAL_CATALOG_READ_FAILED") from None
    if not isinstance(row,(tuple,list)) or len(row)!=1 or type(row[0]) is not bool:
        raise LocalEvidenceBlocked("LOCAL_CATALOG_RESULT_INVALID")
    return row[0]

def audit_local_catalog(conn,auth_checker)->LocalEvidence:
    try:
        identity=conn.execute(IDENTITY_SQL).fetchone()
    except Exception:
        raise LocalEvidenceBlocked("LOCAL_DB_IDENTITY_QUERY_FAILED") from None
    if (not isinstance(identity,(tuple,list)) or len(identity)!=6
            or identity[0]!=DBNAME or identity[1]!=ROLE
            or type(identity[2]) is not int or identity[2]!=PORT
            or type(identity[3]) is not int or not 180000<=identity[3]<190000
            or identity[4]!=PGDATA or identity[5]!="on"):
        raise LocalEvidenceBlocked("LOCAL_PG18_IDENTITY_OR_READ_ONLY_DENIED")
    lifecycle_tables=_one(conn,LIFECYCLE_SQL)
    lifecycle_index=_one(conn,ROUND_INDEX_SQL)
    lifecycle=lifecycle_tables and lifecycle_index
    parity=_one(conn,PARITY_SQL)
    inbox=_one(conn,INBOX_SQL)
    price=_one(conn,PRICE_SQL)
    try:
        auth=auth_checker(conn)
    except Exception:
        raise LocalEvidenceBlocked("LOCAL_AUTH_BASELINE_NOT_ATTESTED") from None
    auth_ok=isinstance(auth,(tuple,list)) and len(auth)==6 and all(
        type(value) is str for value in auth
    )
    return LocalEvidence(lifecycle,parity,inbox,price,auth_ok)

def format_local_evidence(result:LocalEvidence)->tuple[str,...]:
    if not isinstance(result,LocalEvidence):
        raise LocalEvidenceBlocked("LOCAL_EVIDENCE_TYPE_INVALID")
    flags=(
        ("M37370_LOCAL_028_030",result.lifecycle),
        ("M37370_LOCAL_034_041",result.synthetic_parity),
        ("M37370_LOCAL_031",result.inbox),
        ("M37370_LOCAL_043",result.price_043),
        ("M37370_AUTH_BASELINE",result.auth_baseline),
    )
    if any(type(flag) is not bool for _,flag in flags):
        raise LocalEvidenceBlocked("LOCAL_EVIDENCE_FLAG_INVALID")
    return (
        "=== FR FINANCE M37370 LOCAL PG18 READ ONLY ===",
        "M37370_STATUS=READ_ONLY_PASS",
        *(f"{key}="+("STRUCTURAL_PRESENT" if value else "NOT_ATTESTED")
          for key,value in flags),
        "M37370_MIGRATION_EXECUTION_HISTORY=NOT_ATTESTED",
        "M37370_DB_WRITES=NONE",
        "M37370_LOCAL_SQL_APPLIED=NO",
        "M37370_PIX_REAL=OFF",
        "M37370_REAL_USER_ACTIVATION=OFF",
    )
