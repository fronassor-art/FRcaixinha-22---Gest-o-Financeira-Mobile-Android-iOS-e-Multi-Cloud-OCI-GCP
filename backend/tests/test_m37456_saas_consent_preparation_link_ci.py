"""M37456 checks: disposable-only SaaS consent/preparation link, no real payments."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCHEMA=(ROOT/"backend/tests/sql/m37456_saas_consent_preparation_link_ci.sql").read_text()
RUNNER=ROOT/"backend/scripts/aistudio_m37456_saas_preparation_link_ci.py"
SCRIPT=RUNNER.read_text()
STAGING=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()


@pytest.mark.parametrize("marker",[
    "M37456_DISPOSABLE_CI_ONLY",
    "current_database() <> 'frcaixinha_staging'",
    "session_user <> 'postgres'",
    "current_setting('is_superuser') <> 'on'",
    "frcaixinha.saas_consent_ci",
    "M37456_WORKER_CI_ONLY",
    "session_user<>'frcaixinha_saas_consent_ci'",
    "NOT rolsuper AND NOT rolbypassrls",
])
def test_worker_and_database_guard(marker):
    assert marker in SCHEMA


@pytest.mark.parametrize("marker",[
    "saas_consent_preparation_links_m37456_ci",
    "request_id uuid NOT NULL UNIQUE",
    "preparation_id uuid NOT NULL UNIQUE",
    "challenge_id uuid NOT NULL UNIQUE",
    "REFERENCES public.saas_subscription_preparations(id)",
    "REFERENCES public.saas_consent_receipts_m37455_ci(challenge_id)",
    "ENABLE ROW LEVEL SECURITY",
    "FORCE ROW LEVEL SECURITY",
    "REVOKE ALL ON public.saas_consent_preparation_links_m37456_ci",
    "m37456_link_no_update_delete_ci",
    "m37456_link_no_truncate_ci",
    "m37455_reject_mutation_ci",
    "ON CONFLICT DO NOTHING",
    "FOR UPDATE",
    "REPLAY_CI_NO_WRITE",
])
def test_one_to_one_append_only_fk_and_rls(marker):
    assert marker in SCHEMA


@pytest.mark.parametrize("marker",[
    "a.document_kind='PLATFORM_LICENSE'",
    "a.evidence_method='CI_VERIFIED_IDENTITY'",
    "a.evidence_hash<>r.evidence_digest",
    "r.recorded_at>=c.issued_at",
    "r.recorded_at<c.expires_at",
    "c.issued_at>=s.created_at",
    "s.status='PENDING_PAYMENT'",
    "p.status='ACTIVE'",
    "e.payment_created=false",
    "e.entitlement_created=false",
    "saas_payment_intents",
    "saas_license_entitlements",
    "m.role='TENANT_ADMIN'",
    "a.accepted_at<=s.created_at",
    "r.confirmation_text='ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE'",
])
def test_scope_and_timeline_are_checked_before_link(marker):
    assert marker in SCHEMA


@pytest.mark.parametrize("marker",[
    "CHECK(NOT legal_consent_verified)",
    "CHECK(NOT payment_authorized)",
    "CHECK(NOT license_authorized)",
    "CHECK(NOT real_activation_authorized)",
    "POST_PREPARATION_CI_UNATTESTED",
    "LINKED_POST_PREPARATION_CI_UNATTESTED",
    "DENIED_CI_UNATTESTED_OR_SCOPE_MISMATCH",
])
def test_never_authorize_real_financial_effects(marker):
    assert marker in SCHEMA


def test_no_trusted_existing_table_writes():
    lowered=SCHEMA.lower()
    for name in (
        "contract_acceptances","saas_subscription_preparations",
        "saas_payment_intents","saas_license_entitlements",
        "ledger_entries","tenants","users","memberships",
    ):
        for command in ("insert into public.","update public.",
                        "delete from public.","truncate public."):
            assert command+name not in lowered
    assert "GRANT INSERT" not in SCHEMA
    assert "GRANT SELECT" not in SCHEMA
    assert SCHEMA.startswith("-- FR Finance M37456")
    assert SCHEMA.rstrip().endswith("COMMIT;")


def load():
    spec=importlib.util.spec_from_file_location("m37456_guard",RUNNER)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_runner_default_denies_connection_without_ci(monkeypatch):
    module=load()
    for key in module.CI_ENV:
        monkeypatch.delenv(key,raising=False)
    assert module.environment_allowed({}) is False
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
    {"PGOPTIONS":"-c frcaixinha.saas_consent_ci=0"},
])
def test_termux_db_and_oci_never_match_allowlist(change):
    module=load()
    assert module.environment_allowed(dict(module.CI_ENV)) is True
    assert module.environment_allowed({**module.CI_ENV,**change}) is False


def test_ci_script_execute_after_m37455_before_capacity():
    assert "backend/tests/sql/m37456_saas_consent_preparation_link_ci.sql" in STAGING
    assert "backend/scripts/aistudio_m37456_saas_preparation_link_ci.py" in STAGING
    assert "BLOCKED=M37456_WRONG_DATABASE_ACCEPTED" in STAGING
    assert (STAGING.index("M37455: atomic synthetic consent")
            < STAGING.index("M37456: vinculo consentimento/preparacao")
            < STAGING.index("M31400-M31800: SaaS capacity"))


def test_runner_tests_race_and_ban_on_real_activity():
    for marker in (
        "ThreadPoolExecutor",
        "M37456_CONCURRENT_IDEMPOTENCY=PASS",
        "M37456_ORIGINAL_ACCEPTANCE=UNMODIFIED",
        "M37456_PAYMENT_LICENSE_ACTIVATION_PIX_REAL=OFF",
        "M37456_WORKER_CAN_INSERT_RAW_LINK",
        "M37456_APPEND_ONLY_NOT_ENFORCED",
        "M37456_LOCAL_DATABASE=UNTOUCHED",
        "POST_PREPARATION_CI_UNATTESTED",
    ):
        assert marker in SCRIPT


def test_no_new_migration_or_live_api_endpoint():
    catalog=(ROOT/"backend/migration_catalog_ai_studio.json").read_text()
    assert "m37456_saas_consent_preparation_link_ci.sql" not in catalog
    assert "/backend/tests/sql/m37456_saas_consent_preparation_link_ci.sql" not in STAGING
    for bad in ("APIRouter", "httpx.", "requests.", "INSERT INTO public.contract_acceptances",
                "UPDATE public.contract_acceptances"):
        assert bad not in SCRIPT
