"""Read-only inventory of old development prices. Never a license to delete audits."""
from dataclasses import dataclass
from typing import Callable
ITEMS=(
 ("POLICIES_BELOW","SELECT count(*)::bigint FROM public.policies WHERE contribution_per_quota<150.00"),
 ("QUOTAS_BELOW","SELECT count(*)::bigint FROM public.quotas WHERE value_brl<150.00"),
 ("CONTRIBUTIONS_BELOW","SELECT count(*)::bigint FROM public.contributions WHERE amount_due<150.00"),
 ("AUDIT_BELOW","SELECT count(*)::bigint FROM public.cycle_contribution_price_audit WHERE old_price_cents<15000 OR requested_price_cents<15000"),
 ("REGISTERED_PAYMENTS","SELECT count(*)::bigint FROM public.contributions WHERE amount_paid>0 OR paid_at IS NOT NULL OR payment_status='QUITADA'"),
 ("PIX_INTENTS","SELECT count(*)::bigint FROM public.pix_payment_intents"),
 ("LEDGER_ROWS","SELECT count(*)::bigint FROM public.ledger_transactions"),
 ("LOANS","SELECT count(*)::bigint FROM public.loans"),
)
class DevPriceAuditBlocked(ValueError): pass
@dataclass(frozen=True)
class Evidence:
 counts:tuple[int,...]
 opening_audit:int
 def clean(self)->bool: return all(x==0 for x in self.counts[:4]) and self.opening_audit==0
 def financially_sensitive(self)->bool: return any(x>0 for x in self.counts[4:])
def inspect(scalar:Callable[[str],int])->Evidence:
 try:
  counts=tuple(scalar(sql) for _,sql in ITEMS)
  exists=scalar("SELECT to_regclass('public.cycle_opening_audit') IS NOT NULL")
  if type(exists) is not bool: raise ValueError()
  opening=scalar("SELECT count(*)::bigint FROM public.cycle_opening_audit") if exists else 0
 except Exception:
  raise DevPriceAuditBlocked("READ_ONLY_CATALOG_UNAVAILABLE") from None
 if any(type(n) is not int or n<0 or n>100000000 for n in (*counts,opening)):
  raise DevPriceAuditBlocked("CATALOG_COUNT_INVALID")
 return Evidence(counts,opening)
def report(e:Evidence)->tuple[str,...]:
 if not isinstance(e,Evidence) or len(e.counts)!=len(ITEMS):
  raise DevPriceAuditBlocked("CATALOG_REPORT_INVALID")
 return (
  "=== FR FINANCE M37425 DEV READ ONLY INVENTORY ===",
  "M37425_STATUS=READ_ONLY_PASS",
  *(f"M37425_{k}={v}" for (k,_),v in zip(ITEMS,e.counts)),
  f"M37425_OPENING_AUDIT={e.opening_audit}",
  "M37425_DEV_RESET="+("NOT_REQUIRED" if e.clean() else "REQUIRED"),
  "M37425_PAYMENT_OR_LEDGER_TRACES="+("PRESENT" if e.financially_sensitive() else "NONE_OBSERVED"),
  "M37425_PRODUCTION_IMPORT_DEV_DATA=FORBIDDEN",
  "M37425_AUDIT_DELETION=NOT_AUTHORIZED",
  "M37425_DB_WRITES=NO",
  "M37425_PIX_REAL=OFF",
 )
