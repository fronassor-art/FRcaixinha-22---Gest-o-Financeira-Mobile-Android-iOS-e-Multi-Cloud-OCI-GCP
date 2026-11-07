"""M27400 — no delivery authorization from fake/mismatched postcommit proof."""
from dataclasses import replace
from uuid import uuid4, UUID

import pytest

from app.email_challenge_material import PreparedCiEmailChallenge
from app.committed_challenge_handoff import (
    ChallengeHandoffBlocked, SyntheticChallengeReadback,
    PostCommitChallengeDecision, check_committed_challenge,
)

NOW=1794000000


def fixture():
    prepared=PreparedCiEmailChallenge(
        event_id=uuid4(),tenant_id=uuid4(),document_id=uuid4(),
        challenge_digest="a"*64,ttl_seconds=600,
        expires_at=NOW+600,raw_token_for_trusted_worker="S"*64,
    )
    readback=SyntheticChallengeReadback(
        tenant_id=prepared.tenant_id,event_id=prepared.event_id,
        document_id=prepared.document_id,outbox_id=uuid4(),
        challenge_digest=prepared.challenge_digest,
        issued_at=NOW,expires_at=NOW+600,
        failed_attempts=0,consumed=False,
        challenge_status="CI_CHALLENGE_NOT_DELIVERED",
        outbox_status="HELD_CI_NOT_SENT",
        terminal_quarantine=False,source="DISPOSABLE_POSTGRESQL_CI_READBACK",
    )
    return prepared,readback


def test_valid_synthetic_readback_is_not_permission_to_send():
    p,r=fixture()
    result=check_committed_challenge(prepared=p,readback=r,now=NOW+2)
    assert result==PostCommitChallengeDecision()
    assert result.can_send_network is False
    assert result.provider_delivery_confirmed is False
    assert result.recipient_verified is False
    assert result.contract_accepted is False
    assert result.account_activated is False
    assert p.raw_token_for_trusted_worker not in repr(r)
    assert p.raw_token_for_trusted_worker not in repr(result)
    assert p.challenge_digest not in repr(r)
    assert p.challenge_digest not in repr(result)


@pytest.mark.parametrize("field,value", [
    ("tenant_id",uuid4()),
    ("event_id",uuid4()),
    ("document_id",uuid4()),
    ("outbox_id",UUID(int=0)),
    ("challenge_digest","b"*64),
    ("challenge_digest","not a digest"),
    ("issued_at",NOW-31),
    ("issued_at",NOW+1),
    ("expires_at",NOW+601),
    ("expires_at",NOW+59),
    ("failed_attempts",1),
    ("failed_attempts",3),
    ("consumed",True),
    ("challenge_status","CI_TOKEN_CONSUMED_NOT_PROOF"),
    ("challenge_status","SENT"),
    ("outbox_status","DELIVERED"),
    ("terminal_quarantine",True),
    ("source","PUBLIC_HTTP_REQUEST"),
    ("source","FAKE"),
])
def test_challenge_readback_rejects_all_untrusted_or_inconsistent_states(field,value):
    p,r=fixture()
    with pytest.raises(ChallengeHandoffBlocked):
        check_committed_challenge(
            prepared=p,readback=replace(r,**{field:value}),now=NOW+2,
        )


@pytest.mark.parametrize("field,value", [
    ("event_id",uuid4()),
    ("tenant_id",uuid4()),
    ("document_id",uuid4()),
    ("ttl_seconds",900),
    ("expires_at",NOW+100),
    ("challenge_digest","c"*64),
    ("can_send_network",True),
    ("recipient_verified",True),
    ("contract_accepted",True),
    ("account_activated",True),
])
def test_prepared_token_scope_cannot_be_mutated_to_pass_readback(field,value):
    p,r=fixture()
    with pytest.raises(ChallengeHandoffBlocked):
        check_committed_challenge(
            prepared=replace(p,**{field:value}),readback=r,now=NOW+2,
        )


@pytest.mark.parametrize("now", [
    NOW-1,NOW+31,NOW+600,NOW+10000,None,True,
])
def test_stale_future_or_invalid_clock_never_approves_readback(now):
    p,r=fixture()
    with pytest.raises(ChallengeHandoffBlocked):
        check_committed_challenge(prepared=p,readback=r,now=now)


def test_fake_object_dict_cannot_replace_internal_postcommit_snapshot():
    p,r=fixture()
    with pytest.raises(ChallengeHandoffBlocked):
        check_committed_challenge(prepared=p,readback=vars(r),now=NOW+2)
    with pytest.raises(ChallengeHandoffBlocked):
        check_committed_challenge(prepared=vars(p),readback=r,now=NOW+2)


def test_issuer_handoff_has_no_database_or_network_or_public_route():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    source=(root/"backend/app/committed_challenge_handoff.py").read_text()
    for bad in (
        "smtplib", "requests.", "httpx.", "INSERT INTO",
        "UPDATE public.", "oci.config", "os.environ",
        "can_send_network: bool = True", "SMTP(",
    ):
        assert bad not in source
    assert "hmac.compare_digest" in source
    for name in ("invitations.py","auth.py","master.py"):
        route=(root/"backend/app/routers"/name).read_text()
        assert "check_committed_challenge" not in route
