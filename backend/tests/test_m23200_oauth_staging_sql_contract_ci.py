"""M23200: staging OAuth state DB must not use Termux or leak token values."""
from pathlib import Path
R=Path(__file__).resolve().parents[1]
M=(R/"staging_migrations/045_mp_oauth_attempts_staging_only.sql").read_text()
CI=(R/"scripts/aistudio_staging_chain_ci.sh").read_text()
P=(R/"ci_migrations/039_oauth_state_atomic_probe_ci_only.sql").read_text()

def test_strict_guard_and_absent_sensitive_columns():
    assert M.startswith("-- AI Studio M23200")
    assert M.count("\nBEGIN;")==1 and M.count("\nCOMMIT;")==1
    for item in (
        "current_database()<>'frcaixinha_staging'",
        "frcaixinha.mp_oauth_staging_authorized",
        "frcaixinha_mp_oauth_worker",
        "NOT rolbypassrls", "SECURITY DEFINER",
        "FORCE ROW LEVEL SECURITY", "REVOKE ALL",
        "consumed_at IS NULL",
        "expires_at>clock_timestamp()",
        "state_sha256 char(64) NOT NULL UNIQUE",
    ):
        assert item in M,item
    table=M.split("CREATE TABLE public.mp_oauth_attempts_staging",1)[1].split(
        "CREATE INDEX",1)[0]
    for prohibited in ("access_token","refresh_token","code_verifier text",
                       "raw_token","payment_confirmed","bank_reconciled"):
        assert prohibited not in table
    assert "pkce_verifier_secret_ocid" in table

def test_ci_isolation_and_single_use_probe():
    for item in (
        "FRCAIXINHA_CI_ISOLATED", "GITHUB_ACTIONS",
        'PGPORT:-}" = "5432"',
        "PGDATABASE:-}\" = \"frcaixinha_ci\"",
        "CREATE ROLE frcaixinha_mp_oauth_worker",
        "045_mp_oauth_attempts_staging_only.sql",
        "038_oauth_admins_fixture_ci_only.sql",
        "039_oauth_state_atomic_probe_ci_only.sql",
        "PGUSER=frcaixinha_mp_oauth_worker",
    ):
        assert item in CI,item
    for item in ("cross-tenant consume","cross-actor consume",
                 "wrong redirect consumed","replay accepted",
                 "duplicate state accepted","foreign admin accepted"):
        assert item in P,item
    assert "5433" not in CI
