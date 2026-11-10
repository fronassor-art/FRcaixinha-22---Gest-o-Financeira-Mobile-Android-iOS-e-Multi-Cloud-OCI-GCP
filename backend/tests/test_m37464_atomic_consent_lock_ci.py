"""M37464: enforce session row-lock atomicity, nonprod role and rollback."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
SQL=(ROOT/"backend/tests/sql/m37464_atomic_consent_lock_ci.sql").read_text()
RUNNER=ROOT/"backend/scripts/aistudio_m37464_atomic_consent_ci.py"
SRC=RUNNER.read_text()
CHAIN=(ROOT/"backend/scripts/aistudio_staging_chain_ci.sh").read_text()


def load():
    spec=importlib.util.spec_from_file_location("m37464",RUNNER)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("marker",[
    "M37464_DISPOSABLE_POSTGRES_ONLY",
    "current_database()<>'frcaixinha_staging'",
    "session_user<>'postgres'",
    "current_setting('is_superuser')<>'on'",
    "frcaixinha.saas_atomic_ci",
    "frcaixinha.saas_preprep_ci",
    "M37464_WORKER_DISPOSABLE_CI_ONLY",
    "session_user<>'frcaixinha_saas_preprep_ci'",
    "CREATE ROLE frcaixinha_auth_atomic_ci LOGIN INHERIT",
    "NOSUPERUSER NOBYPASSRLS",
    "GRANT frcaixinha_auth_role TO frcaixinha_auth_atomic_ci",
    "M37464_CI_ROLE_PRIVILEGE_ISOLATION",
    "COMMIT;",
])
def test_ci_scoping_and_revoker_worker_roles(marker):
    assert marker in SQL


@pytest.mark.parametrize("marker",[
    "CREATE FUNCTION public.m37464_atomic_consent_ci(",
    "LANGUAGE plpgsql SECURITY DEFINER",
    "SET search_path=pg_catalog,public,pg_temp",
    "FOR UPDATE OF s",
    "s.token_hash=p_token_hash",
    "s.revoked_at IS NULL",
    "s.expires_at>clock_timestamp()",
    "p_action NOT IN ('ISSUE','ACCEPT','PREPARE')",
    "'DENIED_CI_TOKEN_REVOKED_OR_SCOPE'",
    "p_confirmation IS DISTINCT FROM",
    "'ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE'",
    "p_action<>'ACCEPT' AND p_confirmation IS NOT NULL",
    "public.m37458_transition_ci(",
    "GRANT EXECUTE ON FUNCTION public.m37464_atomic_consent_ci(",
])
def test_token_proof_and_row_lock_same_db_transaction(marker):
    assert marker in SQL


@pytest.mark.parametrize("marker",[
    "p_token_hash !~ '^[0-9a-f]{64}$'",
    "u.is_master=false",
    "u.status='ACTIVE'",
    "t.admin_user_id=p_admin",
    "t.status='ATIVO'",
    "m.role='TENANT_ADMIN' AND m.status='ATIVA'",
    "p_session='00000000-0000-0000-0000-000000000000'::uuid",
    "REVOKE ALL ON FUNCTION public.m37464_atomic_consent_ci(",
    "frcaixinha_app_role,frcaixinha_auth_role",
    "frcaixinha_auth_atomic_ci",
    "has_column_privilege('frcaixinha_saas_preprep_ci','public.sessions','token_hash','SELECT')",
])
def test_roles_digest_scope_minimal_privilege(marker):
    assert marker in SQL


def test_no_raw_bearer_or_payment_authorization_in_security_definer():
    lower=SQL.lower()
    for s in (
        "insert into public.saas_payment_intents",
        "insert into public.saas_license_entitlements",
        "insert into public.contract_acceptances",
        "update public.contract_acceptances",
        "update public.saas_payment_intents",
        "update public.ledger_entries",
        "grant update on public.sessions",
        "grant select on public.sessions",
        "grant insert on public.sessions",
    ):
        assert s not in lower
    assert "CREATE TABLE" not in SQL
    assert SQL.rstrip().endswith("COMMIT;")


@pytest.mark.parametrize("marker",[
    "M37464_ATOMIC_TOKEN_SESSION_LOCK=PASS",
    "M37464_CONCURRENT_REVOKER_BLOCKED_UNTIL_COMMIT=PASS",
    "M37464_REVOKE_FIRST_BLOCKS_ACCEPTANCE=PASS",
    "M37464_ROLLBACK_ALL_THREE_STAGES=PASS",
    "M37464_IDEMPOTENT_PREPARATION=PASS",
    "M37464_FINANCIAL_TABLES_UNCHANGED=PASS",
    "M37464_REAL_LEGAL_CONSENT_AND_IDENTITY=NOT_ATTESTED",
    "M37464_PAYMENT_LICENSE_PIX_ACTIVATION=OFF",
    "M37464_TERMUX_LOCAL_DATABASE=UNTOUCHED",
    "class SyntheticRollback(Exception):",
    "raise SyntheticRollback()",
    "psycopg.errors.LockNotAvailable",
    "'55P03'",
    "SET LOCAL lock_timeout = '350ms'",
    "default",
])
def test_probe_concurrency_error_replay_rollback_and_off(marker):
    if marker == "default":
        assert "def connect(" in SRC
    else:
        assert marker in SRC


@pytest.mark.parametrize("marker",[
    "saas_preprep_challenges_m37458_ci",
    "saas_preprep_receipts_m37458_ci",
    "saas_preprep_drafts_m37458_ci",
    "saas_payment_intents",
    "saas_license_entitlements",
    "ledger_entries",
    "SELECT evidence_hash FROM public.contract_acceptances",
    "ORIGINAL_CONTRACT_UNMODIFIED",
    "NO_REAL_AUTHORIZATION",
    "NO_POST_REVOKE_RECORDS",
    "NO_PRE_REVOKED_RECORDS",
])
def test_financial_immutable_readback(marker):
    assert marker in SRC


def test_no_money_or_production_credentials_or_migrations_in_probe():
    for marker in (
        "INSERT INTO public.",
        "UPDATE public.",
        "DELETE FROM public.",
        "ALTER TABLE public.",
        "DROP DATABASE","CREATE DATABASE",
        "APIRouter(","include_router",
        "httpx.post(","requests.post(",
    ):
        assert marker not in SRC
    assert "frcaixinha_aistudio_dev" not in SRC
    assert "PGPORT" in SRC and '"5432"' in SRC
    assert "frcaixinha_staging" in SRC


def test_local_termux_must_not_open_ci_database(monkeypatch):
    m=load()
    for k in m.ENV:
        monkeypatch.delenv(k,raising=False)
    assert m.main()==1
    assert not m.environment_allowed({})
    assert m.environment_allowed(dict(m.ENV))


@pytest.mark.parametrize("difference",[
    {"GITHUB_ACTIONS":"false"},
    {"FRCAIXINHA_CI_ISOLATED":"0"},
    {"PGHOST":"localhost"},
    {"PGPORT":"5433"},
    {"PGDATABASE":"frcaixinha_aistudio_dev"},
    {"PGDATABASE":"frcaixinha_ci"},
    {"PGUSER":"frc_ai_owner"},
    {"PGPASSWORD":"different"},
    {"PGOPTIONS":"-c frcaixinha.saas_atomic_ci=0"},
    {"FR_FINANCE_PIX_REAL":"ON"},
    {"FR_FINANCE_SAAS_REAL":"ON"},
])
def test_ci_environment_allowlist_fail_closed(difference):
    m=load()
    assert not m.environment_allowed({**m.ENV,**difference})


def test_pytest_never_calls_live_runner():
    assert "aistudio_m37464_atomic_consent_ci.py" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()
    assert "m37464_atomic_consent_lock_ci.sql" not in (
        ROOT/"backend/migration_catalog_ai_studio.json").read_text()


def test_chain_places_m37464_before_financial_staging_and_m37462():
    assert "BLOCKED=M37464_WRONG_DATABASE_ACCEPTED" in CHAIN
    assert "backend/tests/sql/m37464_atomic_consent_lock_ci.sql" in CHAIN
    assert "python backend/scripts/aistudio_m37464_atomic_consent_ci.py" in CHAIN
    assert (CHAIN.index("M37459: contrato API simulado e rollback")
            < CHAIN.index("M37464: validar revogacao concorrente")
            < CHAIN.index("M37461: servidor PostgreSQL")
            < CHAIN.index("M37462: verificar token hash"))
