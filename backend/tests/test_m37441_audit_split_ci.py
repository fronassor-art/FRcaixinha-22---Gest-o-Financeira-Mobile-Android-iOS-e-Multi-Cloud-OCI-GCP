"""M37441: reject unsafe extra audit events; preserve original PG18."""
from pathlib import Path
import pytest
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"backend/scripts"))
import aistudio_dev_price_fixture_reset_guarded as guard

def test_total_is_five_pre_and_six_post_with_three_scoped():
    assert guard.BASELINE[12]==5
    assert guard.AFTER[8]==6
    assert guard.EXPECTED_AUDIT_SPLIT==(3,2,0)
    guard.require_baseline(guard.BASELINE)
    guard.verify_audit_split((3,2,0))

@pytest.mark.parametrize("input",[
 (5,0,0),(3,2,1),(2,3,0),(4,1,0),(3,2,-1),
 (3,2),(3,2,"0"),None,
])
def test_unexpected_split_fails_closed(input,capsys):
    with pytest.raises(guard.Blocked):
        guard.verify_audit_split(input)
    assert "M37439_STATUS=DEV_RESET_PASS" not in capsys.readouterr().out

def test_report_aggregates_only_and_keeps_true_block(capsys):
    with pytest.raises(guard.Blocked,match="AUDIT_SCOPE_CHANGED_MUST_REVIEW"):
        guard.verify_audit_split((5,0,0))
    x=capsys.readouterr().out
    assert "M37441_AFFECTED_TENANT_EVENTS_EXPECTED=3" in x
    assert "M37441_AFFECTED_TENANT_EVENTS_OBSERVED=5" in x
    assert "M37441_DB_WRITES=NONE" in x

def test_ci_rehearsal_includes_two_unrelated_global_events():
    seed=(ROOT/"backend/tests/sql/m37438_seed_disposable_ci.sql").read_text()
    check=(ROOT/"backend/tests/sql/m37438_assert_disposable_ci.sql").read_text()
    sql=(ROOT/"backend/scripts/aistudio_dev_price_fixture_reset_candidate.sql").read_text()
    assert "'CI_UNRELATED_GLOBAL_EVENT'" in seed
    assert "NULL,'CI_UNRELATED_GLOBAL_EVENT'" in seed
    assert "WHERE tenant_id IS NULL)<>2" in check
    assert "WHERE tenant_id IS NOT NULL)<>4" in check
    assert "SELECT count(*) FROM public.audit_events)<>5" in sql
    assert "external audit event references legacy cycle" in sql
    assert "a.tenant_id IS DISTINCT FROM v_tenant" in sql

def test_no_change_to_db_or_apply_secrets():
    code=(ROOT/"backend/scripts/aistudio_dev_price_fixture_reset_guarded.py").read_text()
    assert "default_transaction_read_only=on" in code
    assert "FR_FINANCE_M37439_ENABLE_APPLY" in code
    assert "AUTORIZO_EXCECAO_AUDITORIA_DEV" in code
    assert "M37441_OTHER_SCOPE_AUDIT_EVENTS=2" in code
