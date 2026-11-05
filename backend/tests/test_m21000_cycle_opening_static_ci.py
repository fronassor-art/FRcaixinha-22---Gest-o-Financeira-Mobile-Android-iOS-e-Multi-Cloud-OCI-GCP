"""M21000 SQL boundaries, read-only legacy and no real finance."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_only_tenant_admin_can_open_future_cycle():
 s=(ROOT/"backend/local_migrations/044_cycle_opening_audit.sql").read_text()
 for x in ("frcaixinha_aistudio_dev","frcaixinha.cycle_open_local_ci",
 "cycle_price_admin_actor","CREATE TABLE public.cycle_opening_audit",
 "ENABLE ROW LEVEL SECURITY","FORCE ROW LEVEL SECURITY",
 "cycle_opening_immutable_row","cycle_opening_immutable_truncate",
 "UNIQUE(tenant_id,idempotency_key)","FOR UPDATE",
 "p_amount_cents NOT BETWEEN 15000 AND 1000000","'REPLAY'::text"):
  assert x in s,x
 for bad in ("UPDATE public.contributions","DELETE FROM public.contributions",
 "UPDATE public.quotas","INSERT INTO public.contributions",
 "INSERT INTO public.ledger_transactions"):
  assert bad not in s
