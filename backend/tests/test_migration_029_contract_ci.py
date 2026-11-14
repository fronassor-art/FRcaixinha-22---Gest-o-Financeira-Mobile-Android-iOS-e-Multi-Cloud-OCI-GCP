"""M1081+ — verificar integralidade SQL 029, sem acessar nenhum banco."""
from pathlib import Path
import re
import pytest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/migrations/029_member_lifecycle_review_events.sql"


def content():
    s=SQL.read_text(encoding="utf-8")
    assert 7500<len(s)<15000
    return s


def test_single_029_migration_no_truncation_or_duplicate_segments():
    s=content()
    assert s.count("CREATE TABLE public.member_lifecycle_review_events")==1
    assert s.count("CREATE FUNCTION public.lifecycle_append_review_event_sandbox")==1
    assert s.count("CREATE POLICY member_lifecycle_review_")==2
    assert s.count("CREATE POLICY member_lifecycle_subject_read")==1
    assert s.count("DO $guard$")==1
    assert s.strip().endswith("$guard$;")
    assert s.count("$fn$")==2
    assert s.count("CREATE INDEX member_lifecycle_review_")==2
    assert s.count("^[A-Za-z0-9._:-]{8,120}$")==2
    assert "GENERATED ALWAYS AS IDENTITY UNIQUE" in s
    assert "FOR UPDATE" in s
    assert "ORDER BY e.event_seq DESC LIMIT 1" in s


def test_independent_decision_and_member_contestation_are_mandatory():
    s=content()
    for phrase in (
        "v_actor=v_req.requested_by_user_id",
        "m.id=v_req.membership_id AND m.user_id=v_actor",
        "public.rls_is_tenant_admin(v_actor,p_tenant)",
        "v_role<>'TENANT_MEMBER'",
        "p_tenant<>v_ctx_tenant",
        "idempotency_key=p_idempotency",
        "v_existing.evidence_reference<>p_evidence_reference",
        "MEMBER_CONTESTED",
        "ADMIN_REVIEW_ACCEPTED_SANDBOX",
        "ADMIN_REVIEW_REJECTED_SANDBOX",
        "ADMIN_DOCUMENTS_REQUESTED",
        "BLOQUEADO: revisao exige administrador independente",
        "AND e.request_id=p_request",
        "RETURN v_existing.event_id",
    ):
        assert phrase in s


def test_no_financial_side_effect_or_broad_dml_grants():
    s=content()
    for prohibited in (
        "UPDATE public.memberships", "UPDATE public.contributions",
        "INSERT INTO public.cycle_closings",
        "DELETE FROM public.member_lifecycle_requests",
        "UPDATE public.member_lifecycle_requests",
        "INSERT INTO public.ledger_entries",
        "UPDATE public.ledger_accounts", "INSERT INTO public.pix_payment_intents",
        "GRANT UPDATE ON public.member_lifecycle_review_events",
        "GRANT DELETE ON public.member_lifecycle_review_events",
        "GRANT INSERT ON public.member_lifecycle_review_events",
    ):
        assert prohibited not in s
    assert "CHECK (financial_effect_applied=false)" in s
    assert "CHECK (bank_reconciled=false)" in s
    assert "FORCE ROW LEVEL SECURITY" in s
    assert "GRANT SELECT ON public.member_lifecycle_review_events TO frcaixinha_app_role" in s
    assert "TO frcaixinha_app_role;" in s
    assert "TO frcaixinha_auth_role;" not in s


def test_no_029_in_termux_local_migration():
    s=(ROOT/"backend/scripts/aistudio_local_migration.sh").read_text()
    assert "001-027" in s
    assert "029_member_lifecycle_review_events.sql" not in s
    assert "001-029" not in s


@pytest.mark.parametrize("role",[
    "PUBLIC","frcaixinha_auth_role","frcaixinha_verifier_role",
    "frcaixinha_app_role"
])
def test_acl_revoke_all_with_per_role_verification(role):
    s=content()
    assert f"frcaixinha_auth_role" in s
    assert f"frcaixinha_verifier_role" in s
    assert "REVOKE ALL ON public.member_lifecycle_review_events" in s
    assert "has_table_privilege(" in s
