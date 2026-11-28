"""M25700 — static defense against accidental migrations on Android Termux."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_wrapper_never_applies_any_migration():
    shell = (ROOT / "backend/scripts/aistudio_macro_25700_checkpoint.sh").read_text()
    assert "aistudio_migration_inventory.py repo-check" in shell
    assert "aistudio_migration_inventory.py local-readonly" in shell
    assert "AI_STUDIO_APPROVED_SHA" in shell
    assert "frcaixinha-aistudio-mobile" in shell
    assert "aistudio_local_migration.sh" not in shell
    assert "aistudio_db_local.sh apply" not in shell
    assert "psql -f" not in shell
    assert "pg_restore" not in shell
    assert "M25700_NO_MIGRATIONS_APPLIED=PASS" in shell


def test_canonical_inventory_contains_staged_objects_and_pg18_guard():
    source = (ROOT / "backend/scripts/aistudio_migration_inventory.py").read_text()
    assert 'mode=="repo-check"' in source
    assert 'local_readonly()' in source
    assert 'SET TRANSACTION READ ONLY' in source
    assert 'port=5433' in source
    assert 'frcaixinha_aistudio_dev' in source
    assert 'M20700_LOCAL_043=OBJECTS_AND_MINIMUM_VERIFIED' in source
    assert 'M21000_LOCAL_044=OBJECTS_AND_ROLE_BOUNDARY_VERIFIED' in source
    assert 'M20200_LOCAL_028_030=OBJECTS_RLS_VERIFIED' in source


def test_staging_and_ci_sql_never_in_new_wrapper():
    source = (ROOT / "backend/scripts/aistudio_macro_25700_checkpoint.sh").read_text()
    assert "ci_migrations/" not in source
    assert "staging_migrations/" not in source
    assert "M25700_LOCAL_DATABASE_ATTESTATION=PASS" in source
