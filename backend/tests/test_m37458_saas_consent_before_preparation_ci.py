"""M37458 CI-only pre-preparation consent ledger safety contract."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/tests/sql/m37458_saas_consent_before_preparation_ci.sql").read_text()
RUNNER=ROOT/"backend/scripts/aistudio_m37458_preprep_transaction_ci.py"
CODE=RUNNER.read_text()
STAGING=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()


@pytest.mark.parametrize("guard",[
    "M37458_DISPOSABLE_CI_ONLY",
    "current_database()<>'frcaixinha_staging'",
    "session_user<>'postgres'",
    "current_setting('is_superuser')<>'on'",
    "frcaixinha.saas_preprep_ci",
    "frcaixinha_saas_preprep_ci",
    "NOT rolsuper AND NOT rolbypassrls",
    "M37458_WORKER_CI_ONLY",
    "session_user<>'frcaixinha_saas_preprep_ci'",
])
def test_disposable_worker_scope_guard(guard):
    assert guard in SQL


@pytest.mark.parametrize("table",[
    "saas_preprep_sessions_m37458_ci",
    "saas_preprep_challenges_m37458_ci",
    "saas_preprep_receipts_m37458_ci",
    "saas_preprep_drafts_m37458_ci",
])
def test_every_synthetic_table_force_rls_and_append_only(table):
    assert f"CREATE TABLE public.{table}" in SQL
    assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY" in SQL
    assert f"ALTER TABLE public.{table} FORCE ROW LEVEL SECURITY" in SQL
    assert table in SQL
    assert "m37455_reject_mutation_ci" in SQL


@pytest.mark.parametrize("fragment",[
    "p_action IS NULL OR p_action NOT IN ('ISSUE','ACCEPT','PREPARE')",
    "p_action='ISSUE'",
    "p_action='ACCEPT'",
    "CONSENT_BEFORE_PREPARATION_REQUIRED",
    "CHALLENGE_ISSUED_CI",
    "CONSENT_RECORDED_CI_NO_LEGAL_PROOF",
    "DRAFT_PREPARED_CI_NO_PAYMENT",
    "REPLAY_ISSUE_CI_NO_WRITE",
    "REPLAY_ACCEPT_CI_NO_WRITE",
    "REPLAY_PREPARE_CI_NO_WRITE",
    "ON CONFLICT DO NOTHING",
    "FOR UPDATE",
    "clock_timestamp()",
    "rr.server_recorded_at>=cc.server_expires_at",
    "rr.server_recorded_at<cc.server_issued_at",
    "p_confirmation IS DISTINCT FROM 'ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE'",
])
def test_server_side_state_machine_and_single_use(fragment):
    assert fragment in SQL


@pytest.mark.parametrize("fragment",[
    "public.tenants",
    "public.users",
    "public.memberships",
    "public.contract_documents",
    "public.platform_license_price_versions",
    "public.platform_license_plans",
    "d.document_kind='PLATFORM_LICENSE'",
    "d.published_at<=clock_timestamp()",
    "v.annual_price=10*v.monthly_price",
    "p.status='ACTIVE'",
    "s.email_verified",
    "m.role='TENANT_ADMIN'",
    "EXISTS(",
    "public.saas_payment_intents",
    "public.saas_license_entitlements",
])
def test_authoritative_ci_tables_read_before_draft(fragment):
    # Session is a synthetic server fixture: never claim a real identity.
    if fragment=="s.email_verified":
        assert "ss.email_verified" in SQL
    else:
        assert fragment in SQL


@pytest.mark.parametrize("guard",[
    "CHECK(NOT legal_consent_verified)",
    "CHECK(NOT payment_authorized)",
    "CHECK(NOT license_authorized)",
    "CHECK(NOT activation_authorized)",
    "CI_DRAFT_NO_PAYMENT",
    "CI_SYNTHETIC_NOT_LEGAL_CONSENT",
    "REVOKE ALL ON public.saas_preprep_sessions_m37458_ci",
    "TO frcaixinha_saas_preprep_ci;",
])
def test_no_real_activation_possible_in_ci_table(guard):
    assert guard in SQL


def test_no_existing_financial_table_writes_or_prod_routes():
    script=SQL.lower()
    for name in (
        "contract_acceptances","saas_subscription_preparations",
        "saas_payment_intents","saas_license_entitlements",
        "ledger_entries","memberships","tenants","users",
    ):
        for op in ("insert into public.","update public.","delete from public.",
                   "truncate public."):
            assert op+name not in script
    assert "GRANT INSERT" not in SQL
    assert "GRANT SELECT" not in SQL
    assert SQL.rstrip().endswith("COMMIT;")


def load_runner():
    spec=importlib.util.spec_from_file_location("m37458_probe",RUNNER)
    assert spec and spec.loader
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_runner_denies_untrusted_environment_without_connecting(monkeypatch):
    module=load_runner()
    for key in module.CI_ENV:
        monkeypatch.delenv(key,raising=False)
    assert not module.environment_allowed({})
    assert module.main()==1


@pytest.mark.parametrize("change",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"non-ci"},
    {"PGOPTIONS":"-c frcaixinha.saas_preprep_ci=0"},
])
def test_original_db_and_production_env_never_allowed(change):
    module=load_runner()
    assert module.environment_allowed(dict(module.CI_ENV))
    assert not module.environment_allowed({**module.CI_ENV,**change})


def test_ci_orchestrator_after_chronology_before_capacity():
    assert (STAGING.index("M37457: bloquear aceite posterior")
      < STAGING.index("M37458: aceite antes de rascunho")
      < STAGING.index("M31400-M31800: SaaS capacity"))
    assert "CREATE ROLE frcaixinha_saas_preprep_ci LOGIN" in STAGING
    assert "BLOCKED=M37458_WRONG_DATABASE_ACCEPTED" in STAGING
    assert "backend/tests/sql/m37458_saas_consent_before_preparation_ci.sql" in STAGING
    assert "python backend/scripts/aistudio_m37458_preprep_transaction_ci.py" in STAGING


def test_probe_proves_single_draft_not_real_subscription():
    for marker in (
        "ThreadPoolExecutor",
        "M37458_DISPOSABLE_PREPARATION_AFTER_CONSENT=PASS",
        "M37458_CONCURRENT_SINGLE_DRAFT=PASS",
        "M37458_ORIGINAL_ACCEPTANCE=UNMODIFIED",
        "M37458_REAL_PAYMENT_LICENSE_PIX_ACTIVATION=OFF",
        "M37458_LOCAL_DATABASE=UNTOUCHED",
        "M37458_WORKER_RAW_DRAFT_READ_ALLOWED",
        "M37458_APPEND_ONLY_BYPASS",
        "CONSENT_BEFORE_PREPARATION_REQUIRED",
    ):
        assert marker in CODE


def test_catalog_migration_count_not_changed_by_ci_fixture():
    catalog=(ROOT/"backend/migration_catalog_ai_studio.json").read_text()
    assert "m37458_saas_consent_before_preparation_ci.sql" not in catalog
    assert "/backend/tests/sql/m37458_saas_consent_before_preparation_ci.sql" not in STAGING
    assert "CREATE DATABASE" not in CODE
    assert "DROP DATABASE" not in CODE
