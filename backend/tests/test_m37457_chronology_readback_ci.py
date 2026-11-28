"""M37457 read-only PostgreSQL chronology test and isolation contract."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/aistudio_m37457_chronology_readback_ci.py"
STAGING=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
SRC=SCRIPT.read_text()


def load():
    spec=importlib.util.spec_from_file_location("m37457_readback",SCRIPT)
    assert spec is not None and spec.loader is not None
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("key,value",[
    ("GITHUB_ACTIONS","false"),("FRCAIXINHA_CI_ISOLATED","0"),
    ("PGHOST","localhost"),("PGPORT","5433"),
    ("PGDATABASE","frcaixinha_aistudio_dev"),
    ("PGDATABASE","frcaixinha_ci"),("PGUSER","frc_ai_owner"),
    ("PGPASSWORD","real-password"),("PGOPTIONS","-c frcaixinha.saas_consent_ci=0"),
])
def test_wrong_environment_never_connects(key,value):
    m=load()
    assert m.environment_allowed(dict(m.EXPECTED_ENV))
    assert not m.environment_allowed({**m.EXPECTED_ENV,key:value})


def test_main_refuses_termux_without_db_access(monkeypatch):
    m=load()
    for key in m.EXPECTED_ENV:
        monkeypatch.delenv(key,raising=False)
    assert m.main()==1


@pytest.mark.parametrize("fragment",[
    "saas_enrollment_requests_staging",
    "saas_subscription_preparations",
    "saas_consent_challenges_m37455_ci",
    "saas_consent_receipts_m37455_ci",
    "saas_consent_preparation_links_m37456_ci",
    "contract_acceptances",
    "saas_payment_intents",
    "saas_license_entitlements",
    "ledger_entries",
    "WHERE e.request_id=%s AND e.tenant_id=%s AND e.admin_user_id=%s",
    "LIMIT 2",
])
def test_database_query_is_scoped_and_read_only(fragment):
    m=load()
    assert fragment in m.READ_SQL
    assert m.READ_SQL.count("%s")==3
    for bad in ("INSERT INTO ","UPDATE public.","DELETE FROM ","TRUNCATE ",
                "CREATE TABLE ","DROP TABLE ","ALTER TABLE "):
        assert bad not in m.READ_SQL


def test_script_is_explicitly_read_only_and_does_not_migrate():
    assert "default_transaction_read_only=on" in SRC
    assert "M37457_POST_PREPARATION_CONSENT=DENIED_AS_AUTHORITY" in SRC
    assert "M37457_LOCAL_ORIGINAL_DB=UNTOUCHED" in SRC
    assert "M37457_BLOCKED=RETROACTIVE_CONSENT_NOT_DENIED" in SRC
    assert "M37457_REAL_CONSENT=NOT_ATTESTED" in SRC
    assert "PREPARATION_PRECEDED_CONSENT_DENIED" in SRC
    assert "recorded_at AS receipt_recorded_at" in SRC
    assert "created_at AS prepared_at" in SRC
    assert "M37457_CI_HISTORICAL_CHRONOLOGY_READBACK=PASS" in SRC
    assert "INSERT INTO " not in SRC
    assert "UPDATE public." not in SRC
    assert "DELETE FROM " not in SRC


def test_pipeline_order_and_catalog_unchanged():
    assert STAGING.index("M37455: atomic synthetic consent") < STAGING.index(
        "M37456: vinculo consentimento/preparacao") < STAGING.index(
        "M37457: bloquear aceite posterior") < STAGING.index(
        "M31400-M31800: SaaS capacity")
    assert "python backend/scripts/aistudio_m37457_chronology_readback_ci.py" in STAGING
    assert "M37457_REAL_SAAS_ACTIVATION=OFF" in STAGING
    catalog=(ROOT/"backend/migration_catalog_ai_studio.json").read_text()
    assert "m37457" not in catalog


def test_no_new_prod_routes_or_executor():
    from app.saas_preparation_chronology_ci import PreparationConsentDecision
    assert not any((
        PreparationConsentDecision("PROBE").real_identity_verified,
        PreparationConsentDecision("PROBE").legal_consent_verified,
        PreparationConsentDecision("PROBE").payment_authorized,
        PreparationConsentDecision("PROBE").license_authorized,
        PreparationConsentDecision("PROBE").production_authorized,
        PreparationConsentDecision("PROBE").writes_performed,
    ))
