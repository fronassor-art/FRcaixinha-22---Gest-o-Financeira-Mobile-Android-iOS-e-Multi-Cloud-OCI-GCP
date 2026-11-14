"""M921+: regression guard for migration 028. No PostgreSQL required.

The SQL file must be one self-contained migration, not a duplicated or
unterminated SQL fragment. Operational Termux 5433 is out-of-scope.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/migrations/028_member_lifecycle_sandbox_requests.sql"


def sql():
    return SCRIPT.read_text(encoding="utf-8")


def test_exactly_one_create_table_and_function_no_duplicated_fragments():
    s=sql()
    assert 4000 < len(s) < 15000
    assert len(s.splitlines()) < 260
    assert len(re.findall(r"(?im)^CREATE TABLE public\.member_lifecycle_requests\s*\(",s))==1
    assert len(re.findall(r"(?im)^CREATE FUNCTION public\.lifecycle_submit_request_sandbox\s*\(",s))==1
    assert len(re.findall(r"(?im)^CREATE UNIQUE INDEX member_lifecycle_one_pending",s))==1
    assert len(re.findall(r"(?im)^CREATE POLICY member_lifecycle_",s))==2
    assert len(re.findall(r"(?im)^DO \$guard\$",s))==1
    assert s.rstrip().endswith("END $guard$;")
    assert s.count("$$")==2
    assert len(re.findall(r"(?im)^CREATE INDEX ",s))==2


def test_both_sql_regexes_are_complete_not_terminated_mid_clause():
    s=sql()
    p="^[A-Za-z0-9._:-]{8,120}$"
    assert s.count(p)==2
    assert f"CHECK (policy_reference ~ '{p}')" in s
    assert f"OR p_policy_reference !~ '{p}'" in s
    assert not re.search(r"\{8,120\}\s*\n",s)


def test_no_unauthorized_financial_effect_or_acl():
    s=sql()
    for expected in (
        "CHECK (financial_effect_applied = false)",
        "CHECK (bank_reconciled = false)",
        "FORCE ROW LEVEL SECURITY",
        "GRANT SELECT ON public.member_lifecycle_requests TO frcaixinha_app_role;",
        "p_kind='VOLUNTARY_EXIT'",
        "p_kind='DELINQUENCY_REVIEW'",
        "m.user_id=v_user",
        "p_tenant<>v_ctx_tenant",
        "OR v_old_actor IS DISTINCT FROM v_user",
        "UNIQUE (tenant_id,membership_id,request_kind,idempotency_key)",
        "REFERENCES public.cycles(id,tenant_id)",
        "REFERENCES public.memberships(id,tenant_id)",
    ):
        assert expected in s
    assert not re.search(r"(?i)GRANT\s+(?:INSERT|UPDATE|DELETE|ALL)\s+ON\s+public\.member_lifecycle_requests",s)
    for fragment in (
        "UPDATE public.memberships",
        "DELETE FROM public.contributions",
        "UPDATE public.cycle_closings",
        "INSERT INTO public.ledger_entries",
        "INSERT INTO public.ledger_transactions",
    ):
        assert fragment not in s


def test_local_termux_scripts_still_do_not_apply_028_without_authorization():
    script=(ROOT/"backend/scripts/aistudio_local_migration.sh").read_text(encoding="utf-8")
    assert "001-027" in script
    assert "001-028" not in script
    assert "028_member_lifecycle_sandbox_requests.sql" not in script
    assert "AI_STUDIO_APPROVED_SHA" in script


def test_ci_explicitly_applies_only_to_disposable_postgresql_suites():
    w=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text(encoding="utf-8")
    assert "028_member_lifecycle_sandbox_requests.sql" in w
    # A migração 028 deve continuar na sequência, sem exigir que seja a última.
    # Fixar 028 impedia testar 029/030 e quebrava a CI sem falha de segurança.
    matching=[line for line in w.splitlines() if "for i in $(seq 1 " in line]
    assert len(matching)==1
    last=int(matching[0].split("for i in $(seq 1 ",1)[1].split(")",1)[0])
    assert 28<=last<=100
    migrations=ROOT/"backend/migrations"
    for number in range(1,last+1):
        assert len(list(migrations.glob(f"{number:03d}_*.sql")))==1
    assert "PGDATABASE: frcaixinha_ci" in w
    assert "PostgreSQL 18 preflight" in w
    assert "PostgreSQL descartável" in w
