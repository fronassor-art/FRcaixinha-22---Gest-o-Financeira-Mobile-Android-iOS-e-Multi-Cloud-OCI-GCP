"""FR Finance AI Studio: read-only, non-punitive delinquency review signals."""
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class RegisteredRiskSignals:
    registered_ninety_day_review_candidate: bool
    registered_three_competence_review_candidate: bool
    requires_independent_review: bool
    contractual_effect_applied: bool = False
    profit_eligible: None = None
    real_payment_authorized: bool = False


def registered_review_signals(*, oldest_days: int,
                              three_competence_trigger: date | None,
                              as_of: date) -> RegisteredRiskSignals:
    if (type(oldest_days) is not int or not 0 <= oldest_days <= 36500
            or type(as_of) is not date
            or (three_competence_trigger is not None
                and (type(three_competence_trigger) is not date
                     or three_competence_trigger > as_of))):
        raise ValueError("M37987_INVALID_REGISTERED_RISK_FACTS")
    by_days = oldest_days >= 90
    by_months = three_competence_trigger is not None
    return RegisteredRiskSignals(
        registered_ninety_day_review_candidate=by_days,
        registered_three_competence_review_candidate=by_months,
        requires_independent_review=by_days or by_months,
    )
