"""M33900-M34300 static fail-closed registry and legacy DML patch."""
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/local_migrations/046_saas_membership_quota_write_lock.sql").read_text()
WF=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
PREVIEW=(ROOT/"backend/app/saas_member_admission_readiness.py").read_text()

@pytest.mark.parametrize("token",[
 "M33900_WRITE_LOCK_MIGRATION_NOT_AUTHORIZED",
 "frcaixinha_aistudio_dev","frcaixinha_ci",
 "frcaixinha.local_migration_046_approved",
 "REVOKE INSERT,UPDATE,DELETE,TRUNCATE",
 "public.memberships,public.quotas",
 "CREATE TRIGGER memberships_unlicensed_write_lock",
 "CREATE TRIGGER quotas_unlicensed_write_lock",
 "M34300_MEMBER_QUOTA_WRITE_GATE_CLOSED",
 "SECURITY INVOKER","session_user",
 "FORCE ROW LEVEL SECURITY","M34100_UNSAFE_DIRECT_WRITE_PRIVILEGES",
 "M34200_RLS_NOT_FORCED",
])
def test_migration_guards(token):
    assert token in SQL

def test_ci_has_two_disposable_migration_paths_and_probe():
    assert WF.count("046_saas_membership_quota_write_lock.sql")==2
    assert "test_m33900_m34300_saas_write_lock_static_ci.py" in WF
    assert "test_m34300_saas_write_lock_pg_ci.py" in CHAIN
    assert "M34300_MEMBER_QUOTA_WRITES_CLOSED=PASS" in CHAIN

def test_public_preflight_cannot_activate_or_mutate():
    assert '"status": "BLOCKED"' in PREVIEW
    assert '"writes_performed": False' in PREVIEW
    assert '"activation_authorized": False' in PREVIEW
    assert '"membership_created": False' in PREVIEW
    assert '"quota_created": False' in PREVIEW
    assert "INSERT INTO " not in PREVIEW
    assert "UPDATE public." not in PREVIEW
