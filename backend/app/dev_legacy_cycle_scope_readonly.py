"""M37436 — scope of old 2027 synthetic cycle; READ ONLY, same PG18 database.

Collects counts only. No DML, no FK or audit changes, no new database.
A matching count is NOT consent or authorization to purge records.
"""
from dataclasses import dataclass
from psycopg import sql
from app.dev_legacy_dependency_readonly import name,DependencyBlocked

LEGACY_CYCLE_PREDICATE=(
 "dst.id IN (SELECT p.cycle_id FROM public.policies p "
 "WHERE p.contribution_per_quota<150)"
)
SCOPE_SQL="""
WITH legacy AS (
 SELECT DISTINCT tenant_id,cycle_id
 FROM public.policies WHERE contribution_per_quota<150
), tenants AS (SELECT DISTINCT tenant_id FROM legacy)
SELECT
 (SELECT count(*)::int FROM legacy),
 (SELECT count(*)::int FROM public.cycles c JOIN legacy l
   ON c.id=l.cycle_id AND c.tenant_id=l.tenant_id
   WHERE c.year=2027 AND c.status='ABERTO'),
 (SELECT count(*)::int FROM public.cycles c JOIN tenants t
   ON t.tenant_id=c.tenant_id),
 (SELECT count(*)::int FROM public.policies p JOIN legacy l
   ON p.cycle_id=l.cycle_id AND p.tenant_id=l.tenant_id),
 (SELECT count(*)::int FROM public.contributions c JOIN legacy l
   ON c.cycle_id=l.cycle_id AND c.tenant_id=l.tenant_id),
 (SELECT count(*)::int FROM public.cycle_contribution_price_audit a
   JOIN legacy l ON a.cycle_id=l.cycle_id AND a.tenant_id=l.tenant_id),
 (SELECT count(*)::int FROM public.quotas q
   JOIN tenants t ON q.tenant_id=t.tenant_id),
 (SELECT count(*)::int FROM public.audit_events a
   JOIN tenants t ON a.tenant_id=t.tenant_id),
 (SELECT count(*)::int FROM public.contributions c JOIN legacy l
   ON c.cycle_id=l.cycle_id AND c.tenant_id=l.tenant_id
   WHERE c.amount_due>=150),
 (SELECT count(*)::int FROM public.loans p JOIN legacy l
   ON p.cycle_id=l.cycle_id AND p.tenant_id=l.tenant_id)
"""
CYCLE_FKS="""
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
 AND dst.relname='cycles'
GROUP BY src.relname,dst.relname,fk.conname
ORDER BY src.relname,fk.conname
"""
LABELS=(
 "OLD_POLICY_CYCLES","ACTIVE_2027_CYCLES","CYCLES_IN_AFFECTED_TENANT",
 "POLICIES_IN_LEGACY_CYCLE","CONTRIBUTIONS_IN_LEGACY_CYCLE",
 "PRICE_AUDIT_IN_LEGACY_CYCLE","QUOTAS_IN_AFFECTED_TENANT",
 "GENERAL_AUDIT_EVENTS_IN_AFFECTED_TENANT",
 "NEW_PRICE_CONTRIBUTIONS_IN_OLD_CYCLE","LOANS_IN_LEGACY_CYCLE",
)

class CycleScopeBlocked(ValueError): pass

@dataclass(frozen=True)
class CycleScope:
 counts:tuple[int,...]
 incoming_fk:tuple[tuple[str,int],...]
 @property
 def review_required(self):
  return (
   self.counts[:2]!=(1,1) or self.counts[3:6]!=(1,12,1)
   or self.counts[8]!=0 or self.counts[9]!=0
   or any(n>0 for _,n in self.incoming_fk
          if _ not in ("policies","contributions","cycle_contribution_price_audit"))
  )

def cycle_count_query(source,src_columns,dst_columns):
 name(source)
 if (type(src_columns) is not list or type(dst_columns) is not list
  or not 1<=len(src_columns)==len(dst_columns)<=12):
  raise CycleScopeBlocked("INVALID_CYCLE_FK")
 pairs=sql.SQL(" AND ").join(
  sql.SQL("src.{}=dst.{}").format(sql.Identifier(name(a)),sql.Identifier(name(b)))
  for a,b in zip(src_columns,dst_columns)
 )
 return sql.SQL(
  "SELECT count(*)::int FROM {} src JOIN {} dst ON {} WHERE {}"
 ).format(sql.Identifier("public",source),sql.Identifier("public","cycles"),
          pairs,sql.SQL(LEGACY_CYCLE_PREDICATE))

def examine(conn):
 try:
  row=conn.execute(SCOPE_SQL).fetchone()
  fks=conn.execute(CYCLE_FKS).fetchall()
 except Exception:
  raise CycleScopeBlocked("CYCLE_CATALOG_QUERY_FAILED") from None
 if not isinstance(row,tuple) or len(row)!=len(LABELS) or any(
  type(v) is not int or not 0<=v<=100000000 for v in row
 ):
  raise CycleScopeBlocked("CYCLE_SCOPE_INVALID")
 if row[0]!=1 or row[1]!=1 or row[3]!=1 or row[4]!=12 or row[5]!=1:
  raise CycleScopeBlocked("CYCLE_LEGACY_COUNTS_CHANGED")
 if not isinstance(fks,list) or len(fks)>100:
  raise CycleScopeBlocked("CYCLE_FK_CATALOG_INVALID")
 links=[]
 for fk in fks:
  if not isinstance(fk,tuple) or len(fk)!=5:
   raise CycleScopeBlocked("CYCLE_FK_SHAPE_INVALID")
  src,dst,constraint,src_cols,dst_cols=fk
  if dst!="cycles":raise CycleScopeBlocked("CYCLE_FK_WRONG_TARGET")
  try:
   name(constraint)
   query=cycle_count_query(src,src_cols,dst_cols)
   count=conn.execute(query).fetchone()
  except (DependencyBlocked,CycleScopeBlocked):
   raise CycleScopeBlocked("CYCLE_FK_IDENTIFIER_INVALID") from None
  except Exception:
   raise CycleScopeBlocked("CYCLE_FK_COUNT_FAILED") from None
  if (not isinstance(count,tuple) or len(count)!=1 or
       type(count[0]) is not int or not 0<=count[0]<=100000000):
   raise CycleScopeBlocked("CYCLE_FK_COUNT_INVALID")
  links.append((src,count[0]))
 return CycleScope(row,tuple(links))

def report(result):
 if not isinstance(result,CycleScope):raise CycleScopeBlocked("CYCLE_REPORT_INVALID")
 return (
  "=== FR FINANCE M37436 ORIGINAL DB CYCLE SCOPE READ ONLY ===",
  "M37436_STATUS=READ_ONLY_PASS",
  *(f"M37436_{label}={v}" for label,v in zip(LABELS,result.counts)),
  "M37436_CYCLE_FK_CONSTRAINTS="+str(len(result.incoming_fk)),
  *(f"M37436_CYCLE_FK_{i+1}_{source.upper()}={count}"
    for i,(source,count) in enumerate(result.incoming_fk)),
  "M37436_SAFE_TO_PURGE=NOT_AUTHORIZED",
  "M37436_SCOPE_EXTRA_REVIEW="+("YES" if result.review_required else "STANDARD_REVIEW_REQUIRED"),
  "M37436_AUDIT_TRIGGER_CHANGES=NONE",
  "M37436_DATABASE_WRITES=NONE",
  "M37436_NEW_DATABASE=NO",
  "M37436_PIX_REAL=OFF",
 )
