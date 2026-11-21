"""M37987-M38000: 90 civil days must never be inferred as 3 competences."""
from datetime import date, timedelta
import pytest
from app.member_risk_review_signals import registered_review_signals


@pytest.mark.parametrize("days", range(0, 131))
def test_calendar_days_independent_of_monthly_competence(days):
    day=date(2027,1,10)+timedelta(days=days)
    result=registered_review_signals(oldest_days=days,
        three_competence_trigger=None,as_of=day)
    assert result.registered_ninety_day_review_candidate is (days>=90)
    assert result.registered_three_competence_review_candidate is False
    assert result.requires_independent_review is (days>=90)
    assert result.profit_eligible is None
    assert not result.contractual_effect_applied
    assert not result.real_payment_authorized


@pytest.mark.parametrize("days",range(1,90))
def test_three_competence_is_not_90_days(days):
    result=registered_review_signals(oldest_days=days,
        three_competence_trigger=date(2027,3,11),
        as_of=date(2027,3,11)+timedelta(days=days-1))
    assert result.registered_three_competence_review_candidate
    assert not result.registered_ninety_day_review_candidate
    assert result.requires_independent_review


@pytest.mark.parametrize("bad",[True,False,None,90.0,-1,36501,"90"])
def test_invalid_day_counts_rejected(bad):
    with pytest.raises(ValueError,match="M37987_INVALID_REGISTERED_RISK_FACTS"):
        registered_review_signals(oldest_days=bad,
            three_competence_trigger=None,as_of=date(2027,4,11))


@pytest.mark.parametrize("bad",[date(2027,4,12),"2027-03-11",False,1])
def test_invalid_trigger_rejected(bad):
    with pytest.raises(ValueError):
        registered_review_signals(oldest_days=91,
            three_competence_trigger=bad,as_of=date(2027,4,11))


def test_both_review_signals_do_not_authorize_sanctions():
    r=registered_review_signals(oldest_days=91,
       three_competence_trigger=date(2027,3,11),as_of=date(2027,4,11))
    assert r.requires_independent_review
    assert r.profit_eligible is None
    assert not r.contractual_effect_applied and not r.real_payment_authorized


def test_api_requires_review_fields_and_readonly_routes():
    from pathlib import Path
    from app.models import MemberCycleRiskPreviewResponse
    for name in ("registered_ninety_day_review_candidate",
                 "registered_three_competence_review_candidate",
                 "requires_independent_review"):
        assert MemberCycleRiskPreviewResponse.model_fields[name].is_required()
    source=(Path(__file__).resolve().parents[1]/
            "app/routers/member_cycle_previews.py").read_text()
    assert "registered_review_signals(" in source
    assert "Depends(get_current_session)" in source
    assert "Depends(get_rls_db_connection)" in source
    assert "@router.post(" not in source
    assert "@router.delete(" not in source
    assert "@router.put(" not in source
