"""M37445 tests only the explicitly isolated PG18 CI SQL test contract."""
from pathlib import Path
import re
import pytest
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/sql/m37445_cycle_opening_e2e_disposable_ci.sql"
WORKFLOW=ROOT/".github/workflows/validacao-atualizacao.yml"
def test_ci_only_postgres18_and_required_rollback():
    s=SCRIPT.read_text()
    assert s.startswith("-- FR Finance M37445")
    assert re.search(r"(?m)^BEGIN;$",s) and s.rstrip().endswith("ROLLBACK;")
    assert "COMMIT;" not in s
    for guard in ("current_database()<>'frcaixinha_ci'",
      "inet_server_port()<>5432","session_user<>'postgres'",
      "current_setting('frfinance.m37445_disposable_ci',true)<>'1'",
      "current_setting('server_version_num')::int NOT BETWEEN 180000 AND 189999"):
      assert guard in s
    for bad in ("CREATE DATABASE","DROP DATABASE","TRUNCATE ",
                "DELETE FROM public.users","DELETE FROM public.tenants"):
      assert bad not in s
def test_actual_function_called_and_three_administrator_prices():
    s=SCRIPT.read_text()
    assert "public.cycle_open_create(" in s
    assert "ARRAY[15000,20000,32500]" in s
    assert "cents[i]::numeric/100" in s
    assert "M37445 EXPLICIT_CYCLE_OPEN_FAILED" in s
    assert "M37445 INCORRECT_POLICY_AMOUNT" in s
    assert "M37445 IDEMPOTENT_REPLAY_FAILED" in s
    assert "M37445 CONFLICT_ACCEPTED" in s
    assert "M37445 PARALLEL_OPEN_ACCEPTED" in s
def test_security_and_no_automatic_financial_debt():
    s=SCRIPT.read_text()
    for mark in ("M37445 R100_ACCEPTED","M37445 R149_99_ACCEPTED",
      "M37445 CROSS_TENANT_ACCEPTED","M37445 MEMBER_OPEN_ACCEPTED",
      "M37445 INVALID_TOKEN_ACCEPTED",
      "M37445 AUDIT_UPDATE_ACCEPTED","M37445 AUDIT_DELETE_ACCEPTED",
      "count(*) FROM public.contributions",
      "count(*) FROM public.quotas",
      "count(*) FROM public.pix_payment_intents",
      "count(*) FROM public.ledger_transactions",
      "count(*) FROM public.ledger_entries",
      "count(*) FROM public.loans"):
        assert mark in s
def test_workflow_runs_only_in_disposable_postgres18_and_rolls_back():
    w=WORKFLOW.read_text()
    assert "M37445 — abertura autenticada de tres valores em PG18 descartavel" in w
    assert "PGDATABASE: frcaixinha_ci" in w
    assert "FRCAIXINHA_CI_ISOLATED: '1'" in w
    assert "frfinance.m37445_disposable_ci=1" in w
    assert "backend/tests/sql/m37445_cycle_opening_e2e_disposable_ci.sql" in w
    assert "M37445_POST_TRANSACTION_BASELINE=PASS" in w
    assert "ROLLBACK;" in SCRIPT.read_text()
    assert "M37445 — verificacao estatica" in w
