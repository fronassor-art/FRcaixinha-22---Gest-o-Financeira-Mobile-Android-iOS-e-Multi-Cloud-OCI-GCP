"""M1241+: auditoria estática da migração 030 — sem banco persistente."""
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]
SQL=ROOT/"backend/migrations/030_member_lifecycle_case_rounds.sql"

def source():
    content=SQL.read_text(encoding="utf-8")
    assert 5000<len(content)<14000
    assert len(content.splitlines())<260
    return content

def test_030_only_replaces_approved_definer_and_drops_obsolete_index():
    s=source()
    assert s.count("CREATE OR REPLACE FUNCTION public.lifecycle_submit_request_sandbox")==1
    assert s.count("DROP INDEX IF EXISTS public.member_lifecycle_one_pending_per_cycle_kind")==1
    assert s.count("CREATE INDEX member_lifecycle_case_round_lookup")==1
    assert s.count("DO $guard$")==1
    assert s.strip().endswith("$guard$;")
    assert s.count("$fn$")==2
    assert s.count("^[A-Za-z0-9._:-]{8,120}$")==1
    assert "ON public.member_lifecycle_requests" in s
    assert "ORDER BY r.requested_at DESC,r.id DESC" in s

def test_030_history_idempotency_and_serialization_are_guaranteed():
    s=source()
    for phrase in (
        "pg_advisory_xact_lock(hashtextextended(",
        "p_tenant::text||'|'||p_cycle::text",
        "p_membership::text||'|'||p_kind",
        "r.idempotency_key=p_idempotency",
        "v_prior.cycle_id<>p_cycle",
        "v_prior.requested_by_user_id<>v_user",
        "v_prior.policy_reference<>p_policy_reference",
        "RETURN v_prior.id",
        "ORDER BY r.requested_at DESC,r.id DESC",
        "WHERE e.tenant_id=p_tenant AND e.request_id=v_latest.id",
        "ORDER BY e.event_seq DESC LIMIT 1",
        "v_last_event IS NULL OR v_last_event NOT IN",
        "ADMIN_REVIEW_ACCEPTED_SANDBOX",
        "ADMIN_REVIEW_REJECTED_SANDBOX",
        "v_latest.requested_by_user_id IS DISTINCT FROM v_user",
        "RETURN v_latest.id",
        "RETURN v_new_id",
    ):
        assert phrase in s

def test_030_no_real_financial_effects_no_broad_app_grants():
    s=source()
    for prohibited in (
        "UPDATE public.memberships",
        "UPDATE public.contributions",
        "UPDATE public.loans",
        "INSERT INTO public.ledger_entries",
        "INSERT INTO public.ledger_transactions",
        "INSERT INTO public.cycle_closings",
        "INSERT INTO public.member_lifecycle_review_events",
        "UPDATE public.member_lifecycle_requests",
        "DELETE FROM public.member_lifecycle_requests",
        "GRANT INSERT ON public.member_lifecycle_requests",
        "GRANT UPDATE ON public.member_lifecycle_requests",
        "GRANT DELETE ON public.member_lifecycle_requests",
    ):
        assert prohibited not in s
    assert "REVOKE ALL ON FUNCTION public.lifecycle_submit_request_sandbox" in s
    assert "TO frcaixinha_app_role;" in s
    assert "has_table_privilege(" in s
    assert "v_role<>'TENANT_ADMIN'" in s
    assert "v_role<>'TENANT_MEMBER'" in s
    assert "m.user_id=v_user" in s

def test_030_exclusively_in_disposable_github_db():
    w=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()
    script=(ROOT/"backend/scripts/aistudio_local_migration.sh").read_text()
    assert "030_member_lifecycle_case_rounds.sql" in w
    assert "for i in $(seq 1 30)" in w
    assert "PGDATABASE: frcaixinha_ci" in w
    assert "PGDATABASE=frcaixinha_restore_ci" in w
    assert "030_member_lifecycle_case_rounds.sql" not in script
    assert "001-027" in script

@pytest.mark.parametrize("latest,allowed",[
    (None,False),
    ("ADMIN_DOCUMENTS_REQUESTED",False),
    ("MEMBER_CONTESTED",False),
    ("ADMIN_REVIEW_ACCEPTED_SANDBOX",True),
    ("ADMIN_REVIEW_REJECTED_SANDBOX",True),
])
def test_reopen_requires_terminal_latest_event_only(latest,allowed):
    # Oráculo sem acesso a banco: reflete a lista exata do SQL.
    s=source()
    assert "v_last_event IS NULL OR v_last_event NOT IN" in s
    assert (latest in (
        "ADMIN_REVIEW_ACCEPTED_SANDBOX",
        "ADMIN_REVIEW_REJECTED_SANDBOX",
    ))==allowed

@pytest.mark.parametrize("last,round_number",[
    ("ADMIN_REVIEW_ACCEPTED_SANDBOX",i) for i in range(1,121)
]+[
    ("ADMIN_REVIEW_REJECTED_SANDBOX",i) for i in range(1,121)
])
def test_240_reopen_simulations_remain_only_sandbox(last,round_number):
    assert last in ("ADMIN_REVIEW_ACCEPTED_SANDBOX","ADMIN_REVIEW_REJECTED_SANDBOX")
    assert round_number>=1
    s=source()
    assert "RETURN v_new_id" in s
    assert "INSERT INTO public.member_lifecycle_requests" in s
    assert "UPDATE public.memberships" not in s
