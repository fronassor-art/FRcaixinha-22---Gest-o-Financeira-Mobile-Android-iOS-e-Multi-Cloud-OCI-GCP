"""M37467: contract SHA/version/cent amount frozen under DB row locks in CI."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from uuid import UUID
import pytest

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/tests/sql/m37467_frozen_offer_idempotence_ci.sql").read_text()
SCRIPT=(ROOT/"backend/scripts/aistudio_m37467_frozen_offer_ci.py").read_text()
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()


def runner():
    path=ROOT/"backend/scripts/aistudio_m37467_frozen_offer_ci.py"
    spec=importlib.util.spec_from_file_location("m37467",path)
    assert spec and spec.loader
    x=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(x)
    return x


@pytest.mark.parametrize("marker",[
    "M37467_DISPOSABLE_CI_ONLY",
    "current_database()<>'frcaixinha_staging'",
    "session_user<>'postgres'",
    "current_setting('is_superuser')<>'on'",
    "frcaixinha.saas_frozen_ci",
    "frcaixinha.saas_atomic_ci",
    "frcaixinha.saas_preprep_ci",
    "to_regprocedure('public.m37464_atomic_consent_ci",
    "session_user<>'frcaixinha_saas_preprep_ci'",
    "M37467_WRONG_CI_WORKER",
])
def test_database_and_worker_guards(marker):
    assert marker in SQL


@pytest.mark.parametrize("marker",[
    "CREATE TABLE public.saas_frozen_offer_m37467_ci",
    "request_id uuid PRIMARY KEY",
    "challenge_id uuid NOT NULL UNIQUE",
    "document_sha text NOT NULL",
    "frozen_price_cents bigint NOT NULL CHECK(frozen_price_cents>0)",
    "recorded_at timestamptz NOT NULL DEFAULT clock_timestamp()",
    "CI_FROZEN_SYNTHETIC_NOT_LEGAL",
    "ENABLE ROW LEVEL SECURITY",
    "FORCE ROW LEVEL SECURITY",
    "REVOKE ALL ON public.saas_frozen_offer_m37467_ci",
    "m37467_frozen_no_update_delete_ci",
    "m37467_frozen_no_truncate_ci",
    "public.m37455_reject_mutation_ci()",
])
def test_immutable_frozen_snapshot_table(marker):
    assert marker in SQL


@pytest.mark.parametrize("marker",[
    "CREATE FUNCTION public.m37467_frozen_offer_transition_ci(",
    "RETURNS text LANGUAGE plpgsql SECURITY DEFINER",
    "SET search_path=pg_catalog,public,pg_temp",
    "FOR SHARE OF d,v",
    "v_offer.sha256 IS DISTINCT FROM p_document_sha",
    "v_offer.annual_price<>10*v_offer.monthly_price",
    "v_cents<>trunc(v_cents)",
    "v_cents<>p_expected_price_cents",
    "DENIED_CI_FROZEN_PUBLISHED_OFFER_DRIFT",
    "DENIED_CI_FROZEN_REQUEST_COLLISION",
    "DENIED_CI_NO_FROZEN_ISSUE",
    "v_frozen.frozen_price_cents<>p_expected_price_cents",
    "public.m37464_atomic_consent_ci(",
    "INSERT INTO public.saas_frozen_offer_m37467_ci(",
    "ON CONFLICT DO NOTHING",
    "M37467_ATOMIC_FROZEN_RECEIPT_MISMATCH",
])
def test_authoritative_offer_and_atomic_session_lock(marker):
    assert marker in SQL


@pytest.mark.parametrize("marker",[
    "has_table_privilege('frcaixinha_app_role'",
    "has_table_privilege('frcaixinha_saas_preprep_ci'",
    "'public.saas_frozen_offer_m37467_ci','UPDATE'",
    "'public.saas_frozen_offer_m37467_ci','INSERT'",
    "M37467_FROZEN_WORKER_PRIVILEGES",
    "REVOKE ALL ON FUNCTION public.m37467_frozen_offer_transition_ci(",
    "GRANT EXECUTE ON FUNCTION public.m37467_frozen_offer_transition_ci(",
])
def test_no_direct_mutation_or_app_readback_grants(marker):
    assert marker in SQL


@pytest.mark.parametrize("marker",[
    "M37467_FROZEN_DOCUMENT_PRICE_CENTS=PASS",
    "M37467_SAME_REQUEST_REPLAY_NO_DUPLICATE=PASS",
    "M37467_CHANGED_PRICE_SHA_OR_CHALLENGE=DENIED",
    "M37467_CONCURRENT_PRICE_AND_DOCUMENT_UPDATES=LOCKED_OUT",
    "M37467_REVOKED_SESSION_REPLAY=DENIED",
    "M37467_APPEND_ONLY_QUOTE_AFTER_COMMIT=PASS",
    "M37467_FINANCIAL_TABLES_UNCHANGED=PASS",
    "M37467_IDENTITY_AND_LEGAL_CONSENT=CI_SYNTHETIC_NOT_REAL",
    "M37467_LICENSE_PAYMENT_PIX_ACTIVATION=OFF",
    "M37467_TERMUX_ORIGINAL_DATABASE=UNTOUCHED",
])
def test_integrated_disposable_runner_checkpoints(marker):
    assert marker in SCRIPT


@pytest.mark.parametrize("marker",[
    "LockNotAvailable",
    "SET LOCAL lock_timeout = '350ms'",
    "55P03",
    "UPDATE public.platform_license_price_versions",
    "UPDATE public.contract_documents",
    "REPLAY_ISSUE_CI_NO_WRITE",
    "REPLAY_ACCEPT_CI_NO_WRITE",
    "REPLAY_PREPARE_CI_NO_WRITE",
    "DENIED_CI_FROZEN_REQUEST_COLLISION",
    "DENIED_CI_FROZEN_PUBLISHED_OFFER_DRIFT",
    "DENIED_CI_TOKEN_REVOKED_OR_SCOPE",
    "FINANCIAL_UNCHANGED",
    "AFTER_REVOKE_NO_MONEY",
    "REAL_PERMISSIONS_ALL_OFF",
])
def test_concurrency_replay_and_no_payment(marker):
    assert marker in SCRIPT


def test_sql_is_not_a_product_migration_and_enforces_valid_amount():
    assert SQL.lstrip().startswith("-- M37467: disposable only")
    assert SQL.rstrip().endswith("COMMIT;")
    assert "m37467_frozen_offer_idempotence_ci.sql" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()
    assert "INSERT INTO public.saas_payment_intents" not in SQL
    assert "INSERT INTO public.saas_license_entitlements" not in SQL
    assert "INSERT INTO public.contract_acceptances" not in SQL
    assert "CREATE ROLE" not in SQL
    assert "SELECT * INTO v_frozen" in SQL


def test_function_definer_does_not_trust_client_digest_without_sql_check():
    assert "s.token_hash=p_token_hash" not in SQL  # done inside M37464
    assert "public.m37464_atomic_consent_ci(" in SQL
    assert "p_document_sha !~ '^[0-9a-f]{64}$'" in SQL
    assert "p_expected_price_cents>999999999999" in SQL


def test_canonical_offer_rows_are_locked_before_acceptance_transition():
    a=SQL.index("FOR SHARE OF d,v")
    b=SQL.index("SELECT * INTO v_frozen")
    c=SQL.index("v_result:=public.m37464_atomic_consent_ci(")
    assert a<b<c


def test_disposable_runner_only_reads_published_version_from_postgres():
    assert "FROM public.saas_enrollment_requests_staging q " in SCRIPT
    assert "JOIN public.platform_license_price_versions v" in SCRIPT
    assert "JOIN public.contract_documents d ON d.id=%s" in SCRIPT
    assert "cents=amount*Decimal" in SCRIPT
    assert "P=UUID(" not in SCRIPT


def test_termux_and_local_postgres_always_blocked(monkeypatch):
    x=runner()
    for k in x.ENV:
        monkeypatch.delenv(k,raising=False)
    assert x.main()==1
    assert not x.allowed({})
    assert x.allowed(dict(x.ENV))


@pytest.mark.parametrize("wrong",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"real-secret"},
    {"PGOPTIONS":"-c frcaixinha.saas_frozen_ci=0"},
    {"FR_FINANCE_PIX_REAL":"ON"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
    {"FR_FINANCE_LICENSE_REAL":"ON"},
])
def test_environment_allowlist(wrong):
    x=runner()
    assert not x.allowed({**x.ENV,**wrong})


def test_stage_order_and_no_local_ci_sql_execution():
    assert "m37467_frozen_offer_idempotence_ci.sql" in CHAIN
    assert "aistudio_m37467_frozen_offer_ci.py" in CHAIN
    assert "BLOCKED=M37467_WRONG_DATABASE_ACCEPTED" in CHAIN
    assert (CHAIN.index("aistudio_m37466_post_commit_readback_ci.py")
            <CHAIN.index("aistudio_m37467_frozen_offer_ci.py")
            <CHAIN.index("M37461: servidor PostgreSQL"))


def test_dynamic_sql_uses_allowlisted_constant_table_names():
    x=runner()
    assert set(x.STAGES)=={
        "saas_preprep_challenges_m37458_ci",
        "saas_preprep_receipts_m37458_ci",
        "saas_preprep_drafts_m37458_ci",
    }
    assert set(x.MONEY)=={
        "saas_payment_intents","saas_license_entitlements","ledger_entries"
    }
    assert type(x.R) is UUID and type(x.C) is UUID
    assert x.R!=x.C and x.S!=x.C


def test_request_consent_token_is_ci_only_and_not_source_for_prod():
    x=runner()
    assert "NEVER-REAL" in x.TOKEN
    assert x.CONFIRM=="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
    assert "app.include_router(" not in SCRIPT
    assert "APIRouter(" not in SCRIPT
