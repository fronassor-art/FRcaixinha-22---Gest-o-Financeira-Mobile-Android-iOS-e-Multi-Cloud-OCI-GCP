"""M20400: local 042 guard and price API fail-closed; no cash writes."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[2]

def test_local_042_static_contract():
 sql=(ROOT/"backend/local_migrations/042_cycle_contribution_price_audit.sql").read_text()
 for term in (
 "DO $guard$","frcaixinha_aistudio_dev","frcaixinha.cycle_price_local_ci",
 "cycle_contribution_price_audit","ENABLE ROW LEVEL SECURITY","FORCE ROW LEVEL SECURITY",
 "cycle_price_immutable_row","cycle_price_immutable_truncate",
 "SECURITY DEFINER","public.digest(p_raw_token,'sha256')",
 "s.active_role='TENANT_ADMIN'","m.status='ATIVA'",
 "change_status IN('APPLIED','PENDING_REVIEW')",
 "contribution_per_quota=(p_amount_cents::numeric/100)",
 "SELECT 1 FROM public.contributions",
 "old_price_cents","requested_price_cents","idempotency_key",
 "REVOKE ALL ON FUNCTION public.cycle_price_admin_actor",
 ):
  assert term in sql,term
 assert "UPDATE public.contributions" not in sql
 assert "UPDATE public.quotas" not in sql
 assert "INSERT INTO public.ledger" not in sql
 assert "pix_payment_intents" not in sql

def test_installer_backup_fails_closed():
 file=ROOT/"backend/scripts/aistudio_cycle_price_042.sh"
 subprocess.run(["bash","-n",str(file)],check=True)
 p=subprocess.run(["bash",str(file),"audit"],capture_output=True,text=True,timeout=15)
 assert p.returncode!=0 and "M20400_BLOQUEADO" in p.stderr
 s=file.read_text()
 for x in ("AI_STUDIO_APPROVED_SHA","AUTORIZO_POLITICA_COTA_042",
   "age --passphrase","age --decrypt","pg_restore --list","pg_dump",
   "M20400_BACKUP_VERIFIED=PASS","--single-transaction",
   "M20400_LOCAL_042_APPLIED=PASS","M20400_LOCAL_042_VERIFY=PASS"):
  assert x in s,x

def test_api_is_admin_only_and_never_reprices_existing():
 s=(ROOT/"backend/app/routers/cycle_contribution_price.py").read_text()
 assert 'session.role!="TENANT_ADMIN"' in s
 assert "bearer_token(request)" in s
 assert "cycle_price_change" in s
 assert "existing_contributions_repriced" in s
 assert "real_payments_enabled" in s
 assert "cycle_contribution_price.router" in (ROOT/"backend/app/main.py").read_text()
