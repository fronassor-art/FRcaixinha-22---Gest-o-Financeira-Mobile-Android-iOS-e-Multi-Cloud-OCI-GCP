from datetime import datetime, timezone, timedelta

import pytest

from app.annual_consent import ActiveMember, ConsentEvent, assess_annual_consent


def event(member, kind, when, year=2027, version='termo-v1'):
    return ConsentEvent('tenant-a', year, 'admin', member, version, kind, when)


def assess(members, events, when):
    return assess_annual_consent(
        tenant_id='tenant-a', cycle_year=2027, admin_user_id='admin',
        members=members, events=events, terms_version='termo-v1', at=when)


def test_unanimity_zero_members_new_member_revocation_and_expiry():
    now = datetime(2027, 6, 1, 12, tzinfo=timezone.utc)
    admin = ActiveMember('admin-link', 'admin')
    one = ActiveMember('member-1', 'user-1')
    two = ActiveMember('member-2', 'user-2')
    assert assess([admin], [], now).reason == 'SEM_OUTROS_MEMBROS'
    assert assess([ActiveMember('member-1', 'user-1')], [], now).reason == 'ADMIN_NAO_MEMBRO_ATIVO'
    signed = [event('member-1', 'SIGNED', now - timedelta(days=1))]
    assert assess([admin, one], signed, now).authorized
    assert not assess([admin, one, two], signed, now).authorized
    signed.append(event('member-2', 'SIGNED', now - timedelta(hours=1)))
    assert assess([admin, one, two], signed, now).authorized
    signed.append(event('member-1', 'REVOKED', now))
    result = assess([admin, one, two], signed, now)
    assert not result.authorized and result.missing_membership_ids == ('member-1',)
    assert assess([admin, one, two], signed, datetime(2028, 1, 10, tzinfo=timezone.utc)).reason == 'FORA_DO_CICLO'


def test_wrong_tenant_version_future_event_and_naive_time_are_rejected():
    now = datetime(2027, 6, 1, tzinfo=timezone.utc)
    member = ActiveMember('m', 'user')
    wrong = [event('m', 'SIGNED', now + timedelta(days=1)),
             event('m', 'SIGNED', now, version='old'),
             ConsentEvent('tenant-b', 2027, 'admin', 'm', 'termo-v1', 'SIGNED', now)]
    assert not assess([member], wrong, now).authorized
    with pytest.raises(ValueError):
        assess([member], [], datetime(2027, 6, 1))


@pytest.mark.asyncio
async def test_legacy_vote_cannot_claim_annual_authorization():
    from fastapi import HTTPException
    from app.dependencies import AuthenticatedSession
    from app.models import AdminConsentVotePayload
    from app.routers.consents import get_admin_self_loan_consent_status, vote_admin_self_loan_consent
    session = AuthenticatedSession('user', 'TENANT_MEMBER', 'tenant-a',
                                   'synthetic@example.invalid', 'Sintético', False)
    status = await get_admin_self_loan_consent_status('tenant-a', None, session)
    assert status.is_unanimous is False
    assert status.status == 'BLOQUEADO_ASSINATURA_ANUAL_INDISPONIVEL'
    with pytest.raises(HTTPException) as error:
        await vote_admin_self_loan_consent(
            'tenant-a', AdminConsentVotePayload(decision='FAVORAVEL'), 'loan', session)
    assert error.value.status_code == 503
