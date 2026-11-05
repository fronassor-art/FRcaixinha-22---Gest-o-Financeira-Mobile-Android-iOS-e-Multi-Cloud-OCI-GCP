"""M5700–M5900 migration chain must only run in disposable GitHub CI."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/aistudio_staging_chain_ci.sh"

def test_sql_chain_scripts_isolated_and_ordered():
    s=SCRIPT.read_text()
    for guard in (
        "FRCAIXINHA_CI_ISOLATED",
        "GITHUB_ACTIONS",
        "127.0.0.1",
        'PGPORT:-}" = "5432"',
        'PGDATABASE:-}" = "frcaixinha_ci"',
        "pg_database WHERE datname='frcaixinha_staging'",
        "createdb -T frcaixinha_ci frcaixinha_staging",
        "NOSUPERUSER NOBYPASSRLS",
        "033_staging_orders_fixture_ci_only.sql",
        "034_staging_orders_worker_probe_ci_only.sql",
        "035_staging_webhook_probe_ci_only.sql",
    ):
        assert guard in s,guard
    previous=-1
    for mig in ("034_mp_signed_webhook_staging_only.sql",
                "035_pix_payment_automation_staging_only.sql",
                "036_signed_orders_inbox_staging_only.sql",
                "037_orders_payment_link_staging_only.sql",
                "038_orders_reservation_staging_only.sql"):
        location=s.index(mig)
        assert location>previous
        previous=location
    assert "ALTER USER postgres PASSWORD" not in s
    assert "ALTER DATABASE frcaixinha_aistudio_dev" not in s
    assert "pg_dump -h 127.0.0.1 -p 5433" not in s

def test_m034_atomic_and_not_termux():
    script=(ROOT/"staging_migrations/034_mp_signed_webhook_staging_only.sql").read_text()
    assert script.count("BEGIN;")==1
    assert script.count("COMMIT;")==1
    assert script.index("BEGIN;")<script.index("DO $guard$")
    assert script.index("COMMIT;")>script.index("GRANT EXECUTE")
    assert "frcaixinha.mp_staging_authorized" in script

def test_no_staging_files_in_local_migration_directory():
    for n in range(34,39):
        assert not list((ROOT/"migrations").glob(f"{n:03}_*"))
    assert not list((ROOT/"migrations").glob("039_mp_*"))
    for p in ("033_staging_orders_fixture_ci_only.sql",
              "034_staging_orders_worker_probe_ci_only.sql",
              "035_staging_webhook_probe_ci_only.sql"):
        f=ROOT/"ci_migrations"/p
        assert f.is_file()
        assert "ocid1.secret.oc1.ci-fake-only" in f.read_text() or "CI" in f.read_text()
