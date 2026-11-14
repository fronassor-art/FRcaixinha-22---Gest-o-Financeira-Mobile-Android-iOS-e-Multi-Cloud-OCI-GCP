"""FR Finance M39066 — SQL112 synthetic-only, no database connections."""
from pathlib import Path
import json
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "backend/migrations/112_frfinance_master_independent_saas_prices.sql"


def test_original_sql112_immutable_legacy_values_and_only_target_column():
    sql = SQL.read_text()
    assert "ALTER COLUMN annual_price DROP EXPRESSION" in sql
    assert "ALTER COLUMN annual_price SET NOT NULL" in sql
    assert "GRANT INSERT (annual_price)" in sql
    assert "platform_license_annual_price_positive" in sql
    assert "M39066_WRONG_ORIGINAL_POSTGRESQL_IDENTITY" in sql
    assert "current_setting('data_directory')" in sql
    assert "public.platform_license_price_versions" in sql
    for forbidden in (
        "UPDATE public.platform_license_price_versions",
        "DELETE FROM public.platform_license_price_versions",
        "INSERT INTO public.platform_license_price_versions",
        "CREATE DATABASE", "CREATE ROLE", "ALTER ROLE",
        "COPY public", "frcaixinha_2_2_dev",
    ):
        assert forbidden not in sql


def test_migration_registered_exact_blob_sha():
    data=json.loads((ROOT/"backend/migration_catalog_ai_studio.json").read_text())
    item=next(e for e in data["entries"] if e["id"]=="migrations:112")
    assert item["source_path"]==str(SQL.relative_to(ROOT))
    assert item["classification"]=="LOCAL_CANDIDATE_REQUIRES_PROOF"
    assert item["do_not_apply_source_to_termux"] is False
    digest=subprocess.check_output(["git","hash-object",str(SQL)],text=True).strip()
    assert item["source_blob_sha"]==digest


def test_master_api_has_independent_prices_rbac_and_stale_guard():
    route=(ROOT/"backend/app/routers/master.py").read_text()
    assert "expected_version_id: uuid.UUID" in route
    assert "annual_price: Decimal = Field(" in route
    assert "Depends(require_master)" in route
    assert "pg_advisory_xact_lock" in route
    assert "status_code=409" in route
    assert "attgenerated=''" in route
    assert "annual_price_computed" not in route
    assert "(plan_tier,monthly_price,annual_price,changed_by,reason)" in route
    assert "SAAS_PRICE_VERSION_CREATED" in route
    assert "OFF_NO_PROVIDER_NO_CHARGE" in route


def test_android_ui_allows_two_independent_fields_and_stale_guard():
    ui=(ROOT/"src/components/MasterLicensingView.tsx").read_text()
    api=(ROOT/"src/services/financialApiService.ts").read_text()
    assert 'id="master-license-monthly-price"' in ui
    assert 'id="master-license-annual-price"' in ui
    assert "newAnnualPrice" in ui
    assert "editingVersionId" in ui
    assert "priceSaving" in ui
    assert "response.billing_status !== 'OFF_NO_PROVIDER_NO_CHARGE'" in ui
    assert "annual_price_computed" not in ui+api
    assert "newMonthlyPrice * 10" not in ui
    assert "annual_price, expected_version_id, reason" in api
    assert "R$ 150,00 por ciclo" in ui


def test_saas_checkout_uses_frozen_independent_annual_cents():
    code=(ROOT/"backend/app/saas_checkout_chain_ci.py").read_text()
    assert "offer.annual_cents != offer.monthly_cents * 10" not in code
    assert "offer.expected_cents !=" in code
    assert 'offer.monthly_cents if offer.period == "MONTHLY"' in code
    assert "else offer.annual_cents" in code


def test_termux_migration_runner_has_safety_guards():
    code=(ROOT/"backend/scripts/frfinance_m39066_master_prices_sql112_termux.py").read_text()
    assert "verify_original()" in code
    assert 'modes.add_argument("--inspect"' in code
    assert 'modes.add_argument("--apply"' in code
    assert "APLICAR_SQL112_FR_FINANCE" in code
    assert "pg_dump" in code and "pg_restore" in code
    assert "SQL112_HASH_MISMATCH" in code
    assert "SELECT attgenerated" in code
    assert "SQL112_ATOMIC_VERIFICATION_FAILED" in code
    for forbidden in ("createdb", "dropdb", "os.system(", "os.kill(", 
                      "subprocess.Popen(", "print(password)", "print(source)",
                      "ALTER ROLE ", "pg_ctl stop"):
        assert forbidden not in code


def test_database_identity_pure_contract():
    from backend.scripts import frfinance_m39066_master_prices_sql112_termux as m
    good=(m.DB,m.OWNER,m.OWNER,"127.0.0.1",5433,str(m.PGDATA),180006)
    assert m.database_identity(good)
    assert not m.database_identity((m.DB,m.OWNER,m.OWNER,"127.0.0.1",
                                    5432,str(m.PGDATA),180006))
    assert not m.database_identity((m.DB,m.OWNER,m.OWNER,"127.0.0.1",
                                    5433,str(m.PGDATA),170005))
    assert not m.database_identity(("frcaixinha_2_2_dev",m.OWNER,m.OWNER,
                                    "127.0.0.1",5433,str(m.PGDATA),180006))
