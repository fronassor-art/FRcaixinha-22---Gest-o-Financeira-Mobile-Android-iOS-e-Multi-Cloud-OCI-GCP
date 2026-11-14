"""M37435: read-only FK dependencies of obsolete dev prices; existing DB only."""
from __future__ import annotations
from dataclasses import dataclass
import re
from psycopg import sql

PREDICATES={
 "policies":"dst.contribution_per_quota<150",
 "quotas":"dst.value_brl<150",
 "contributions":"dst.amount_due<150",
 "cycle_contribution_price_audit":
 "(dst.old_price_cents<15000 OR dst.requested_price_cents<15000)",
}
BASELINE="""
SELECT (SELECT count(*)::int FROM public.policies WHERE contribution_per_quota<150),
 (SELECT count(*)::int FROM public.quotas WHERE value_brl<150),
 (SELECT count(*)::int FROM public.contributions WHERE amount_due<150),
 (SELECT count(*)::int FROM public.cycle_contribution_price_audit
    WHERE old_price_cents<15000 OR requested_price_cents<15000),
 (SELECT count(*)::int FROM public.contributions
    WHERE amount_paid>0 OR paid_at IS NOT NULL OR payment_status='QUITADA'),
 (SELECT count(*)::int FROM public.pix_payment_intents),
 (SELECT count(*)::int FROM public.ledger_transactions),
 (SELECT count(*)::int FROM public.loans)
"""
TRIGGERS="""
SELECT count(*)::int FROM pg_catalog.pg_trigger
WHERE tgrelid='public.cycle_contribution_price_audit'::regclass
 AND NOT tgisinternal AND tgenabled='O'
 AND tgname IN('cycle_price_immutable_row','cycle_price_immutable_truncate')
"""
FKS="""
SELECT src.relname,dst.relname,fk.conname,
 array_agg(sa.attname ORDER BY ord.n)::text[],
 array_agg(da.attname ORDER BY ord.n)::text[]
FROM pg_catalog.pg_constraint fk
JOIN pg_catalog.pg_class src ON src.oid=fk.conrelid
JOIN pg_catalog.pg_class dst ON dst.oid=fk.confrelid
JOIN pg_catalog.pg_namespace sn ON sn.oid=src.relnamespace
JOIN pg_catalog.pg_namespace dn ON dn.oid=dst.relnamespace
JOIN LATERAL generate_subscripts(fk.conkey,1) ord(n) ON true
JOIN pg_catalog.pg_attribute sa
 ON sa.attrelid=src.oid AND sa.attnum=fk.conkey[ord.n]
JOIN pg_catalog.pg_attribute da
 ON da.attrelid=dst.oid AND da.attnum=fk.confkey[ord.n]
WHERE fk.contype='f' AND sn.nspname='public' AND dn.nspname='public'
 AND dst.relname IN('policies','quotas','contributions','cycle_contribution_price_audit')
GROUP BY src.relname,dst.relname,fk.conname
ORDER BY dst.relname,src.relname,fk.conname
"""
class DependencyBlocked(ValueError): pass
@dataclass(frozen=True)
class Reference:
 source:str
 target:str
 constraint:str
 matches:int
@dataclass(frozen=True)
class Evidence:
 counts:tuple[int,...]
 triggers:int
 links:tuple[Reference,...]

def name(v):
 if type(v) is not str or not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}",v):
  raise DependencyBlocked("UNSAFE_CATALOG_NAME")
 return v

def count_sql(source,target,src_cols,dst_cols):
 name(source)
 if target not in PREDICATES: raise DependencyBlocked("UNKNOWN_TARGET")
 if (type(src_cols) is not list or type(dst_cols) is not list or
     not 1<=len(src_cols)==len(dst_cols)<=12):
  raise DependencyBlocked("INVALID_FOREIGN_KEY")
 expr=sql.SQL(" AND ").join(
  sql.SQL("src.{}=dst.{}").format(sql.Identifier(name(a)),sql.Identifier(name(b)))
  for a,b in zip(src_cols,dst_cols))
 return sql.SQL("SELECT count(*)::int FROM {} src JOIN {} dst ON {} WHERE {}").format(
  sql.Identifier("public",source),sql.Identifier("public",target),
  expr,sql.SQL(PREDICATES[target]))

def examine(conn):
 try:
  baseline=conn.execute(BASELINE).fetchone()
  trigger=conn.execute(TRIGGERS).fetchone()
  refs=conn.execute(FKS).fetchall()
 except Exception: raise DependencyBlocked("CATALOG_READ_FAILED") from None
 if (not isinstance(baseline,tuple) or len(baseline)!=8 or
     any(type(x) is not int or x<0 for x in baseline)):
  raise DependencyBlocked("BASELINE_INVALID")
 if baseline[:4]!=(1,1,12,1): raise DependencyBlocked("BASELINE_CHANGED")
 if any(x>0 for x in baseline[4:]): raise DependencyBlocked("FINANCIAL_TRACE_REVIEW_REQUIRED")
 if not isinstance(trigger,tuple) or trigger!=(2,):
  raise DependencyBlocked("IMMUTABLE_AUDIT_TRIGGERS_NOT_VERIFIED")
 if not isinstance(refs,list) or len(refs)>100:
  raise DependencyBlocked("FOREIGN_KEY_CATALOG_UNEXPECTED")
 links=[]
 for ref in refs:
  if type(ref) is not tuple or len(ref)!=5: raise DependencyBlocked("FOREIGN_KEY_INVALID")
  source,target,constraint,src_cols,dst_cols=ref
  name(constraint)
  query=count_sql(source,target,src_cols,dst_cols)
  try: row=conn.execute(query).fetchone()
  except Exception: raise DependencyBlocked("FOREIGN_KEY_COUNT_FAILED") from None
  if (not isinstance(row,tuple) or len(row)!=1 or
      type(row[0]) is not int or not 0<=row[0]<=100000000):
   raise DependencyBlocked("FOREIGN_KEY_COUNT_INVALID")
  links.append(Reference(source,target,constraint,row[0]))
 return Evidence(baseline,trigger[0],tuple(links))

def report(result):
 if not isinstance(result,Evidence): raise DependencyBlocked("REPORT_INVALID")
 return (
  "=== FR FINANCE M37435 EXISTING DB DEPENDENCY READ ONLY ===",
  "M37435_STATUS=READ_ONLY_PASS",
  "M37435_LEGACY_COUNTS=1_POLICY_1_QUOTA_12_CONTRIBUTIONS_1_AUDIT",
  "M37435_AUDIT_IMMUTABLE_TRIGGERS="+str(result.triggers),
  "M37435_INCOMING_FK_CONSTRAINTS="+str(len(result.links)),
  "M37435_FK_MATCHES="+str(sum(l.matches for l in result.links)),
  *(f"M37435_FK_{i+1}_{r.source.upper()}_TO_{r.target.upper()}={r.matches}"
    for i,r in enumerate(result.links)),
  "M37435_NON_FK_RELATIONSHIPS=NOT_ATTESTED",
  "M37435_AUDIT_DELETION=NOT_AUTHORIZED",
  "M37435_MIGRATION_EXECUTED=NO",
  "M37435_DB_WRITES=NONE",
  "M37435_NEW_DATABASE=NO",
  "M37435_PIX_REAL=OFF",
  "M37435_REAL_USERS=OFF",
 )
