"""M20100: local 034-041 DDL must remain strictly synthetic and inaccessible."""
import subprocess
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
TABLES=["webhook_evidence","pix_dryrun","orders_inbox","order_evidence",
        "order_reservation","reconciliation_hold","incident_audit","notification_outbox"]
@pytest.mark.parametrize("n,suffix",zip(range(34,42),TABLES))
def test_local_ddl_is_guarded(n,suffix):
    files=list((ROOT/"backend/local_migrations").glob(f"{n:03d}_*.sql"))
    assert len(files)==1
    s=files[0].read_text()
    table=f"local_m{n:03d}_{suffix}"
    for part in ("DO $local_guard$","frcaixinha_aistudio_dev","frcaixinha_ci",
                 "frcaixinha.local_parity_ci","inet_server_port()=5433",
                 f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY",
                 f"REVOKE ALL ON TABLE public.{table}","CHECK(NOT "):
        assert part in s,part
    assert "CREATE POLICY " not in s
    assert "GRANT " not in s
    assert "INSERT INTO public.ledger" not in s
    assert "UPDATE public.memberships" not in s
def test_local_040_is_immutable():
    s=next((ROOT/"backend/local_migrations").glob("040_*.sql")).read_text()
    assert "BEFORE UPDATE OR DELETE" in s
    assert "BEFORE TRUNCATE" in s
def test_termux_install_is_guarded_and_backup_first():
    path=ROOT/"backend/scripts/aistudio_local_parity_034_041.sh"
    subprocess.run(["bash","-n",str(path)],check=True)
    result=subprocess.run(["bash",str(path),"audit"],capture_output=True,text=True,timeout=10)
    assert result.returncode!=0 and "M20100_BLOQUEADO" in result.stderr
    s=path.read_text()
    for value in ("AI_STUDIO_APPROVED_SHA","AUTORIZO_ESQUEMA_SINTETICO_034_041",
                  "AI_STUDIO_LOCAL_PARITY_034_041","pg_dump",
                  "age --passphrase","age --decrypt","pg_restore --list",
                  "M20100_BACKUP_VERIFIED=PASS","--single-transaction",
                  "M20100_LOCAL_034_041_POST_VERIFY=PASS"):
        assert value in s,value
    assert s.index("M20100_BACKUP_VERIFIED=PASS")<s.index("psql_local --single-transaction")
    assert "backend/staging_migrations/" not in s
def test_ci_runner_is_disposable():
    p=ROOT/"backend/scripts/aistudio_local_parity_034_041_ci.sh"
    subprocess.run(["bash","-n",str(p)],check=True)
    s=p.read_text()
    assert "GITHUB_ACTIONS" in s and "frcaixinha_ci" in s
    assert "M20100_LOCAL_PARITY_PG_CI=PASS" in s
