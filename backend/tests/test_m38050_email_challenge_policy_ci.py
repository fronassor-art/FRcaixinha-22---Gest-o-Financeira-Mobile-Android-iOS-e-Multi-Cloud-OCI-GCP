"""M38050: offline, fail-closed email challenge budget contract."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from app.invite_challenge_guard_ci import (
    check_challenge_budget, ChallengeGuardError,
)
NOW = datetime(2026,11,11,3,0,tzinfo=timezone.utc)

@pytest.mark.parametrize("count",[0,1,2])
def test_valid_challenge_issue_with_interval(count):
    last=None if count==0 else NOW-timedelta(seconds=60)
    check_challenge_budget(issued_count=count,last_created_at=last,now=NOW)

@pytest.mark.parametrize("seconds",[0,1,30,59])
def test_reissue_within_cooldown_is_blocked(seconds):
    with pytest.raises(ChallengeGuardError,match="CHALLENGE_COOLDOWN"):
        check_challenge_budget(
            issued_count=1,last_created_at=NOW-timedelta(seconds=seconds),now=NOW)

@pytest.mark.parametrize("count",[3,4,100])
def test_total_challenge_quota_includes_revoked(count):
    with pytest.raises(ChallengeGuardError,match="CHALLENGE_LIMIT_EXHAUSTED"):
        check_challenge_budget(
            issued_count=count,last_created_at=NOW-timedelta(days=1),now=NOW)

@pytest.mark.parametrize("count,last,now",[
    (-1,None,NOW),(True,NOW-timedelta(minutes=2),NOW),
    (0,NOW-timedelta(minutes=2),NOW),(1,None,NOW),
    (1,NOW+timedelta(seconds=1),NOW),
    (1,NOW.replace(tzinfo=None),NOW),
    (1,NOW-timedelta(minutes=2),NOW.replace(tzinfo=None)),
    (2,"bad-date",NOW),(2,NOW,"bad-date"),(0,None,None),
])
def test_unknown_history_denied(count,last,now):
    with pytest.raises(ChallengeGuardError):
        check_challenge_budget(issued_count=count,last_created_at=last,now=now)

def test_guard_precedes_revocation_under_invitation_lock():
    root=Path(__file__).resolve().parents[2]
    module=(root/"backend/app/invite_registration_ci.py").read_text()
    segment=module.split("def prepare_invite_email_verification_ci(",1)[1].split(
        "def register_new_invited_identity_ci(",1)[0]
    assert "_ci_only(conn)" in segment
    assert segment.index("FOR UPDATE") < segment.index("SELECT count(*)::int,max(created_at)")
    assert segment.index("check_challenge_budget(") < segment.index(
        "UPDATE public.invite_email_verification SET revoked_at=now()")
    assert segment.index("UPDATE public.invite_email_verification SET revoked_at=now()") < segment.index(
        "INSERT INTO public.invite_email_verification")

def test_public_invites_stay_disabled():
    root=Path(__file__).resolve().parents[2]
    router=(root/"backend/app/routers/invitations.py").read_text()
    assert "prepare_invite_email_verification_ci" not in router
    assert "register_new_invited_identity_ci" not in router
    assert "Convites ainda não implementados" in router
