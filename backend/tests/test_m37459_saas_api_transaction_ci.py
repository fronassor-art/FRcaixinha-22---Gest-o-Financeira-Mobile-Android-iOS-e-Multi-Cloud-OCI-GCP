"""M37459 CI-only server API adapter and disposable PostgreSQL rollback guards."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"backend/scripts/aistudio_m37459_api_transaction_ci.py"
SRC=RUNNER.read_text()
STAGING=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()
CONTRACT=(ROOT/"backend/app/saas_acceptance_api_contract_ci.py").read_text()


def load():
    spec=importlib.util.spec_from_file_location("m37459",RUNNER)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.mark.parametrize("marker",[
    "M37459_API_CONTRACT_CI=PASS",
    "M37459_TRANSACTION_FULL_ROLLBACK=PASS",
    "M37459_CONSENT_BEFORE_DRAFT=PASS",
    "M37459_IDEMPOTENT_REPLAY=PASS",
    "M37459_REAL_IDENTITY_OR_LEGAL_CONSENT=NOT_ATTESTED",
    "M37459_REAL_PAYMENT_LICENSE_PIX_ACTIVATION=OFF",
    "M37459_LOCAL_DATABASE=UNTOUCHED",
    "class IntentionalRollback",
    "raise IntentionalRollback()",
    "except IntentionalRollback:",
    "M37459_FULL_ROLLBACK_ALL_TABLES",
])
def test_transaction_and_no_financial_enablement_markers(marker):
    if marker=="M37459_FULL_ROLLBACK_ALL_TABLES":
        assert '"FULL_ROLLBACK_ALL_TABLES"' in SRC
    else:
        assert marker in SRC


def test_readonly_nonfixture_tables_and_isolated_executor():
    for forbidden in (
        "INSERT INTO public.contract_acceptances",
        "INSERT INTO public.saas_subscription_preparations",
        "INSERT INTO public.saas_payment_intents",
        "INSERT INTO public.saas_license_entitlements",
        "UPDATE public.contract_acceptances",
        "DELETE FROM public.contract_acceptances",
        "DROP DATABASE","CREATE DATABASE",
        "APIRouter",
    ):
        assert forbidden not in SRC
    assert "frcaixinha_staging" in SRC
    assert "frcaixinha_saas_preprep_ci" in SRC
    assert "CI_DRAFT_NO_PAYMENT" in SRC


def test_no_live_backend_route_or_infrastructure_change():
    main=(ROOT/"backend/app/main.py").read_text()
    assert "saas_acceptance_api_contract_ci" not in main
    assert "m37459_api_transaction_ci" not in main
    for fragment in ("include_router", "APIRouter", "import asyncpg",
                     "import psycopg", "INSERT INTO", "UPDATE public."):
        assert fragment not in CONTRACT


def test_main_fail_closed_without_environment(monkeypatch):
    m=load()
    for k in m.EXPECTED_ENV:
        monkeypatch.delenv(k,raising=False)
    assert m.main()==1
    assert not m.environment_allowed({})
    assert m.environment_allowed(dict(m.EXPECTED_ENV))


@pytest.mark.parametrize("changed",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"not-ci-test-only"},
    {"PGOPTIONS":"-c frcaixinha.saas_preprep_ci=0"},
])
def test_original_database_never_matches_allowlist(changed):
    m=load()
    assert not m.environment_allowed({**m.EXPECTED_ENV,**changed})


def test_probe_called_after_m37458_and_never_from_termux():
    assert (STAGING.index("M37458: aceite antes de rascunho")
            < STAGING.index("M37459: contrato API simulado e rollback")
            < STAGING.index("M31400-M31800: SaaS capacity"))
    assert "python backend/scripts/aistudio_m37459_api_transaction_ci.py" in STAGING
    assert "M37459_REAL_SAAS_ACTIVATION=OFF" in STAGING
    assert "m37459_api_transaction_ci.py" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()


def test_contract_is_synthetic_server_claim_not_authentication():
    for marker in (
        "CI_SYNTHETIC_SERVER_AUTH_READBACK",
        "CI_SYNTHETIC_SERVER_OFFER_READBACK",
        "CI_DISPOSABLE_EXECUTOR_REQUIRED",
        "UNEXPECTED_OR_MISSING_CLIENT_FIELD",
        "SERVER_CHALLENGE_OR_REQUEST_MISMATCH",
        "CI_CONTRACT_NOT_AVAILABLE",
        "EXPLICIT_CONTRACT_CONFIRMATION_REQUIRED",
        "CI_EXECUTOR_FAILED_CLOSED",
        "CI_TRANSACTION_DENIED",
        "real_writes_performed: bool = False",
    ):
        assert marker in CONTRACT
