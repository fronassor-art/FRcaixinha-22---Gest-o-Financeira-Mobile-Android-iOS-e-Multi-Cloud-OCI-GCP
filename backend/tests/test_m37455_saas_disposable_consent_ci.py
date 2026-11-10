"""M37455: CI-only staging consent SQL and test runner static safety checks."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/tests/sql/m37455_saas_consent_disposable_ci.sql").read_text()
SCRIPT=ROOT/"backend/scripts/aistudio_m37455_saas_disposable_ci.py"
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()


@pytest.mark.parametrize("guard",[
    "M37455_DISPOSABLE_CI_ONLY",
    "current_database() <> 'frcaixinha_staging'",
    "session_user <> 'postgres'",
    "current_setting('is_superuser') <> 'on'",
    "frcaixinha.saas_consent_ci",
    "frcaixinha_saas_consent_ci",
    "M37455_WORKER_CI_ONLY",
    "session_user<>'frcaixinha_saas_consent_ci'",
])
def test_disposable_and_worker_scope_guards(guard):
    assert guard in SQL


@pytest.mark.parametrize("contract",[
    "ENABLE ROW LEVEL SECURITY",
    "FORCE ROW LEVEL SECURITY",
    "saas_consent_challenges_m37455_ci",
    "saas_consent_receipts_m37455_ci",
    "REFERENCES public.saas_enrollment_requests_staging(request_id)",
    "CHECK(confirmation_text='ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE')",
    "UNIQUE REFERENCES public.saas_enrollment_requests_staging(request_id)",
    "ON CONFLICT DO NOTHING",
    "FOR UPDATE",
    "M37455_APPEND_ONLY_CI",
    "M37455_REPLAY",
])
def test_atomic_idempotency_and_append_only_contract(contract):
    if contract == "M37455_REPLAY":
        assert "REPLAY_CI_NO_WRITE" in SQL
    elif contract == "UNIQUE REFERENCES public.saas_enrollment_requests_staging(request_id)":
        assert "request_id uuid NOT NULL UNIQUE REFERENCES public.saas_enrollment_requests_staging(request_id)" in SQL
    else:
        assert contract in SQL


@pytest.mark.parametrize("value",[
    "p_tenant", "p_admin", "p_session", "p_document", "p_document_sha",
    "p_price", "p_challenge", "p_request", "p_confirmation", "p_digest",
])
def test_scope_is_server_checked(value):
    assert value in SQL


def test_all_real_writes_absent():
    lower=SQL.lower()
    for real_table in (
        "contract_acceptances","saas_subscription_preparations",
        "saas_payment_intents","saas_license_entitlements",
        "ledger_entries","memberships","users",
    ):
        for method in ("insert into public.","update public.","delete from public.",
                       "truncate public."):
            assert method+real_table not in lower
    assert SQL.startswith("-- M37455: synthetic SaaS")
    assert SQL.rstrip().endswith("COMMIT;")
    assert SQL.count("CREATE FUNCTION public.m37455_")==3


def test_no_direct_worker_table_privileges():
    assert "REVOKE ALL ON public.saas_consent_challenges_m37455_ci" in SQL
    assert "TO frcaixinha_saas_consent_ci;" in SQL
    assert "GRANT INSERT" not in SQL
    assert "GRANT SELECT" not in SQL
    assert "GRANT UPDATE" not in SQL


def _module():
    spec=importlib.util.spec_from_file_location("m37455_probe",SCRIPT)
    assert spec is not None and spec.loader is not None
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_exact_isolated_environment():
    m=_module()
    assert m.environment_allowed(dict(m.CI_ENV))
    assert not m.environment_allowed({})
    assert not m.environment_allowed({"GITHUB_ACTIONS":"true"})


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"other"},
    {"PGOPTIONS":"-c frcaixinha.saas_consent_ci=0"},
])
def test_local_termux_and_unexpected_db_never_allowed(change):
    m=_module()
    assert not m.environment_allowed({**m.CI_ENV,**change})


def test_main_refuses_termux_without_db_connection(monkeypatch):
    m=_module()
    for k in m.CI_ENV:
        monkeypatch.delenv(k,raising=False)
    assert m.main()==1


def test_staging_pipeline_is_not_termux_installer():
    assert "CREATE ROLE frcaixinha_saas_consent_ci LOGIN" in CHAIN
    assert "backend/tests/sql/m37455_saas_consent_disposable_ci.sql" in CHAIN
    assert "backend/scripts/aistudio_m37455_saas_disposable_ci.py" in CHAIN
    assert "M37455_WRONG_DATABASE_ACCEPTED" in CHAIN
    assert CHAIN.index("M37453: readback de preparacao") < CHAIN.index("M37455: atomic synthetic consent")
    assert CHAIN.index("M37455: atomic synthetic consent") < CHAIN.index("M31400-M31800: SaaS capacity")


def test_runner_validates_concurrency_original_acceptance_and_no_money():
    text=SCRIPT.read_text()
    for name in (
        "ThreadPoolExecutor",
        "M37455_DUPLICATE_AND_CONCURRENT_REPLAY=PASS",
        "M37455_ORIGINAL_LOCAL_DATABASE=UNTOUCHED",
        "M37455_SAAS_PAYMENT_AND_LICENSE=OFF",
        "M37455_EXISTING_CONTRACT_ACCEPTANCE=UNMODIFIED",
        "M37455_APPEND_ONLY_NOT_ENFORCED",
        "M37455_WORKER_CAN_INSERT_RAW_RECEIPTS",
    ):
        assert name in text
    for forbidden in ("DROP DATABASE", "CREATE DATABASE",
                      "UPDATE public.contract_acceptances",
                      "DELETE FROM public.contract_acceptances"):
        assert forbidden not in text


def test_catalog_remains_unchanged_and_sql_fixture_is_not_a_migration():
    manifest=(ROOT/"backend/migration_catalog_ai_studio.json").read_text()
    assert "m37455_saas_consent_disposable_ci.sql" not in manifest
    assert "/backend/tests/sql/m37455_saas_consent_disposable_ci.sql" not in CHAIN
