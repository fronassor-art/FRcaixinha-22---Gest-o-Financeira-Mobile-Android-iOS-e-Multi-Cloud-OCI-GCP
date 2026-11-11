"""M38651-M38700: repository-only regression guard for R$150 minimum per quota.

This does not query PostgreSQL or claim that local migration 043/044 ran.
The historical R$100 ledger must remain unchanged and readable.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "backend/local_migrations"
SQL_042 = BASE / "042_cycle_contribution_price_audit.sql"
SQL_043 = BASE / "043_cycle_contribution_contract_minimum.sql"
SQL_044 = BASE / "044_cycle_opening_audit.sql"
CATALOG = ROOT / "backend/migration_catalog_ai_studio.json"


def source(p: Path) -> str:
    assert p.is_file(), f"missing source {p.name}"
    return p.read_text(encoding="utf-8")


def _function(sql: str, name: str) -> str:
    marker = f"CREATE FUNCTION public.{name}("
    assert sql.count(marker) == 1, f"missing or duplicate {name} function"
    return sql.split(marker, 1)[1].split("END $fn$;", 1)[0]


def test_catalog_marks_043_044_as_local_candidates_not_execution_evidence():
    catalog = json.loads(source(CATALOG))
    assert catalog["not_authority_to_deploy"] is True
    assert catalog["rules"]["mandatory_local_backup_and_post_apply_verification"] is True
    assert catalog["rules"]["do_not_claim_local_applied_from_CI"] is True
    by_id = {e["id"]: e for e in catalog["entries"]}
    for n, suffix in (
        ("043", "043_cycle_contribution_contract_minimum.sql"),
        ("044", "044_cycle_opening_audit.sql"),
    ):
        item = by_id[f"local_migrations:{n}"]
        assert item["classification"] == "LOCAL_CANDIDATE_REQUIRES_PROOF"
        assert item["source_path"] == "backend/local_migrations/" + suffix
        assert item["local_evidence"] is None
        assert item["requires_local_equivalent_before_use"] is False


@pytest.mark.parametrize("path", [SQL_043, SQL_044])
def test_local_migrations_have_strict_termux_and_disposable_ci_guard(path):
    sql = source(path)
    assert "current_database()='frcaixinha_aistudio_dev'" in sql
    assert "current_database()='frcaixinha_ci'" in sql
    assert "session_user='frc_ai_owner'" in sql
    assert "inet_server_port()=5433" in sql
    assert "current_setting('server_version_num')::int BETWEEN 180000 AND 189999" in sql
    assert "session_user='postgres'" in sql
    assert "current_setting('is_superuser')='on'" in sql
    assert "RAISE EXCEPTION" in sql
    assert "DROP DATABASE" not in sql


def test_043_removes_100_brl_defaults_and_guards_new_policy_quota_rows():
    sql = source(SQL_043)
    for required in (
        "ALTER TABLE public.policies ALTER COLUMN contribution_per_quota DROP DEFAULT",
        "ALTER TABLE public.quotas ALTER COLUMN value_brl DROP DEFAULT",
        "ADD CONSTRAINT policy_minimum_150_new",
        "CHECK (contribution_per_quota >= 150.00) NOT VALID",
        "ADD CONSTRAINT quota_minimum_150_new",
        "CHECK (value_brl >= 150.00) NOT VALID",
    ):
        assert required in sql
    assert "VALIDATE CONSTRAINT" not in sql
    assert "UPDATE public.policies SET" not in sql
    assert "UPDATE public.quotas SET" not in sql
    assert "DELETE FROM public." not in sql
    assert "TRUNCATE public." not in sql


def test_043_price_change_rejects_below_15000_cents_before_legacy_call():
    sql = source(SQL_043)
    body = _function(sql, "cycle_price_change")
    assert "p_amount_cents IS NULL" in body
    assert "p_amount_cents NOT BETWEEN 15000 AND 1000000" in body
    assert "RAISE EXCEPTION 'M20700 minimum R$150 per quota'" in body
    assert "public.cycle_price_change_legacy_m20400(" in body
    assert body.index("NOT BETWEEN 15000 AND 1000000") < body.index(
        "public.cycle_price_change_legacy_m20400("
    )
    assert "RENAME TO cycle_price_change_legacy_m20400;" in sql
    assert "REVOKE ALL ON FUNCTION public.cycle_price_change_legacy_m20400" in sql
    assert "FROM PUBLIC,frcaixinha_app_role,frcaixinha_auth_role,frcaixinha_verifier_role" in sql
    assert "GRANT EXECUTE ON FUNCTION public.cycle_price_change(" in sql
    assert "TO frcaixinha_app_role;" in sql


def test_044_admin_defined_opening_amount_is_exact_and_minimum_15000():
    sql = source(SQL_044)
    body = _function(sql, "cycle_open_create")
    for marker in (
        "p_amount_cents IS NULL",
        "p_amount_cents NOT BETWEEN 15000 AND 1000000",
        "v_actor:=public.cycle_price_admin_actor(p_token,p_tenant)",
        "p_idempotency IS NULL",
        "v_prior.amount_cents<>p_amount_cents",
        "p_amount_cents::numeric/100",
        "p_amount_cents,p_idempotency,btrim(p_reason)",
    ):
        assert marker in body
    assert "CREATE TABLE public.cycle_opening_audit(" in sql
    assert "amount_cents bigint NOT NULL CHECK(amount_cents BETWEEN 15000 AND 1000000)" in sql
    assert "UNIQUE(tenant_id,idempotency_key)" in sql
    assert "UNIQUE(tenant_id,cycle_year)" in sql
    assert "ALTER TABLE public.cycle_opening_audit FORCE ROW LEVEL SECURITY" in sql
    assert "BEFORE UPDATE OR DELETE" in sql
    assert "BEFORE TRUNCATE" in sql
    assert "GRANT EXECUTE ON FUNCTION public.cycle_open_create(" in sql
    assert "TO frcaixinha_app_role;" in sql


def test_no_100_brl_floor_allowed_in_new_043_044_entrypoints():
    for path in (SQL_043, SQL_044):
        sql = source(path)
        for bad in (
            "BETWEEN 10000 AND 1000000",
            "BETWEEN 100 AND 1000000",
            "contribution_per_quota >= 100.00",
            "value_brl >= 100.00",
            "DEFAULT 100",
        ):
            assert bad not in sql
    # Historical version remains present but is not an app-facing write entrypoint.
    historical = source(SQL_042)
    assert "requested_price_cents BETWEEN 100 AND 1000000" in historical
    assert "CREATE TABLE public.cycle_contribution_price_audit" in historical
    assert "public.cycle_price_audit_immutable()" in historical


def test_contract_floor_static_proof_is_not_production_authorization():
    text = source(SQL_043) + source(SQL_044)
    assert "GRANT EXECUTE ON FUNCTION" in text
    assert "INSERT INTO public.contributions" not in text
    assert "INSERT INTO public.ledger" not in text
    assert "insert into public.pix" not in text.lower()
    assert "sendmail(" not in text
    assert "smtplib" not in text
