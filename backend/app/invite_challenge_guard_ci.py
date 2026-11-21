"""Pure offline guard for simulated email challenge issuance, M38050."""
from datetime import datetime, timedelta

MAX_CHALLENGES = 3
MIN_INTERVAL = timedelta(seconds=60)

class ChallengeGuardError(ValueError):
    pass

def check_challenge_budget(*, issued_count: int, last_created_at: datetime | None,
                           now: datetime) -> None:
    if (type(issued_count) is not int or issued_count < 0
            or type(now) is not datetime or now.tzinfo is None
            or now.utcoffset() is None
            or (last_created_at is None) != (issued_count == 0)):
        raise ChallengeGuardError("INVALID_CHALLENGE_STATE")
    if last_created_at is not None and (
            type(last_created_at) is not datetime
            or last_created_at.tzinfo is None
            or last_created_at.utcoffset() is None
            or last_created_at > now):
        raise ChallengeGuardError("INVALID_CHALLENGE_STATE")
    if issued_count >= MAX_CHALLENGES:
        raise ChallengeGuardError("CHALLENGE_LIMIT_EXHAUSTED")
    if last_created_at is not None and now - last_created_at < MIN_INTERVAL:
        raise ChallengeGuardError("CHALLENGE_COOLDOWN")
