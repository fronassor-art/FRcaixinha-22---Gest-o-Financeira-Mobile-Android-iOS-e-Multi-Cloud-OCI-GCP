"""M23600 — isolated PostgreSQL staging consent/CAS contracts, not Termux."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCHEMA=ROOT/"staging_migrations/046_mp_oauth_seller_consent_cas_staging_only.sql"
SCRIPT=ROOT/"scripts/aistudio_staging_chain_ci.sh"

def test_staging_sql_is_guarded_and_contains_no_token_columns():
    s=SCHEMA.read_text()
    assert s.count("\nBEGIN;")==1
    assert s.count("\nCOMMIT;")==1
    for term in (
        "current_database()<>'frcaixinha_staging'",
        "frcaixinha.mp_oauth_staging_authorized",
        "frcaixinha_mp_oauth_worker",
        "current_setting('is_superuser')",
        "FORCE ROW LEVEL SECURITY",
        "SECURITY DEFINER",
        "session_user<>'frcaixinha_mp_oauth_worker'",
        "CREATE UNIQUE INDEX mp_oauth_only_one_active_staging",
        "FOR UPDATE",
        "expected_generation<>c.generation",
        "c.revoked_at IS NOT NULL",
        "m.role='TENANT_ADMIN' AND m.status='ATIVA'",
        "access_sha256 char(64)",
        "refresh_sha256 char(64)",
        "status='RETIRED'",
        "p_access_hash !~ '^[a-f0-9]{64}$'",
        "GRANT EXECUTE ON FUNCTION",
    ):
        assert term in s,term
    tables=s.split("CREATE TABLE public.mp_oauth_seller_consents_staging",1)[1].split("CREATE FUNCTION",1)[0]
    for forbidden in ("access_token", "refresh_token", "code_verifier",
                      "client_secret", "pix_key", "raw_token"):
        assert forbidden not in tables
    assert "5433" in s  # warning, never an install target

def test_disposable_postgres_cas_and_revocation_are_exercised():
    s=SCRIPT.read_text()
    for check in (
        "FRCAIXINHA_CI_ISOLATED",
        "GITHUB_ACTIONS",
        'PGPORT:-}" = "5432"',
        "046_mp_oauth_seller_consent_cas_staging_only.sql",
        "040_oauth_consents_fixture_ci_only.sql",
        "041_oauth_seller_cas_probe_ci_only.sql",
        "042_oauth_revocation_probe_ci_only.sql",
        "PGUSER=frcaixinha_mp_oauth_worker",
        "M23600_DISPOSABLE_CAS_REVOKE=PASS",
        "LOCAL_MIGRATIONS=NOT_TOUCHED",
        "OCI_APPLY=NOT_EXECUTED",
        "REAL_MONEY=OFF",
    ):
        assert check in s,check
    assert "PGPORT=5433" not in s
    for path in (
        "ci_migrations/040_oauth_consents_fixture_ci_only.sql",
        "ci_migrations/041_oauth_seller_cas_probe_ci_only.sql",
        "ci_migrations/042_oauth_revocation_probe_ci_only.sql",
    ):
        assert (ROOT/path).is_file()

def test_negative_probes_cover_cas_replay_and_revocation():
    c=(ROOT/"ci_migrations/041_oauth_seller_cas_probe_ci_only.sql").read_text()
    r=(ROOT/"ci_migrations/042_oauth_revocation_probe_ci_only.sql").read_text()
    for term in ("cross-tenant seller reused","cross-actor staged",
                 "stale generation staged","activation replay",
                 "malformed fingerprint accepted","active revision lost"):
        assert term in c,term
    for term in ("revoked consent eligible","post-revocation CAS accepted",
                 "revoked credential still available",
                 "post-revocation stage allowed"):
        assert term in r,term
