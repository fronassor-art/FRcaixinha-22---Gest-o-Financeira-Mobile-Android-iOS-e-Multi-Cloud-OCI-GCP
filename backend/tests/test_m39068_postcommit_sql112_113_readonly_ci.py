"""M39068 — testes offline do diagnóstico pós-COMMIT, sem PostgreSQL real."""
from pathlib import Path

import pytest

from backend.scripts.frfinance_m39068_postcommit_sql112_113_readonly_diagnostic import (
    search_path_is_restricted, inspect_schema,
)

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"backend/scripts/frfinance_m39068_postcommit_sql112_113_readonly_diagnostic.py"


@pytest.mark.parametrize("config", [
    ["search_path=pg_catalog,pg_temp"],
    ["search_path=pg_catalog, pg_temp"],
    ("other=1", "search_path = pg_catalog, pg_temp"),
])
def test_restricted_pg_catalog_and_pg_temp(config):
    # PostgreSQL normalmente grava 'search_path=pg_catalog, pg_temp'.
    # Uma configuração com espaços antes do '=' é rejeitada por segurança.
    assert search_path_is_restricted(config) is (not any("search_path =" in c for c in config))


@pytest.mark.parametrize("config", [
    None, "", [], {}, ["search_path=public,pg_catalog"],
    ["search_path=pg_catalog"], ["search_path=pg_catalog,public,pg_temp"],
    ["search_path=pg_catalog,pg_temp", "search_path=public"],
    ["search_path=pg_temp,pg_catalog"], ["search_path=pg_catalog,pg_temp,public"],
    ["search_path=pg_catalog, pg_temp","search_path=pg_catalog, pg_temp"],
])
def test_reject_noncanonical_or_untrusted_search_path(config):
    assert search_path_is_restricted(config) is False


def test_sql112_sql113_checks_are_only_reads():
    source=SOURCE.read_text()
    assert "SET TRANSACTION READ ONLY" in source
    assert "database_identity(identity)" in source
    assert "validate_context()" in source
    assert "validate_sql113_hash()" in source
    assert "getpass.getpass(" in source
    assert 'port=5433' in source
    assert 'dbname=DB' in source
    assert "M39067_POSTCHECK_EXACT_TEXT" in source
    assert "M39068_DATABASE_WRITES=NONE" in source
    for needle in (
        "DROP TABLE", "ALTER TABLE", "CREATE ROLE",
        "INSERT INTO", "TRUNCATE", "pg_ctl", "os.kill(",
        "subprocess.Popen(", "print(password)", "print(metadata[1])",
    ):
        assert needle not in source


def test_diagnostic_only_prints_boolean_states():
    source=SOURCE.read_text()
    assert "flags.items()" in source
    assert "'PASS' if status else 'FAIL'" in source
    assert "print(identity)" not in source
    assert "print(privileges)" not in source
    assert "print(metadata)" not in source
