"""Motor puro de verificação da autorização anual, sem efeito financeiro.

A coleta de assinaturas e a persistência ainda não estão ligadas a este motor.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ActiveMember:
    membership_id: str
    user_id: str


@dataclass(frozen=True)
class ConsentEvent:
    tenant_id: str
    cycle_year: int
    beneficiary_admin_user_id: str
    voter_membership_id: str
    terms_version: str
    kind: str  # SIGNED ou REVOKED
    occurred_at: datetime


@dataclass(frozen=True)
class AnnualConsentAssessment:
    authorized: bool
    required_count: int
    signed_count: int
    missing_membership_ids: tuple[str, ...]
    reason: str


def assess_annual_consent(*, tenant_id: str, cycle_year: int, admin_user_id: str,
                          members: Iterable[ActiveMember], events: Iterable[ConsentEvent],
                          terms_version: str, at: datetime) -> AnnualConsentAssessment:
    """Exige assinatura vigente de cada outro membro ativo; revogação prevalece."""
    if at.tzinfo is None or not terms_version:
        raise ValueError('Data com fuso e versão dos termos são obrigatórias.')
    local_day = at.astimezone(ZoneInfo('America/Belem')).date()
    if local_day.year != cycle_year:
        return AnnualConsentAssessment(False, 0, 0, (), 'FORA_DO_CICLO')
    active_members = tuple(members)
    if (any(not m.membership_id or not m.user_id for m in active_members) or
            len({m.membership_id for m in active_members}) != len(active_members)):
        return AnnualConsentAssessment(False, 0, 0, (), 'VINCULOS_INVALIDOS')
    if not any(m.user_id == admin_user_id for m in active_members):
        return AnnualConsentAssessment(False, 0, 0, (), 'ADMIN_NAO_MEMBRO_ATIVO')
    required = {m.membership_id for m in active_members if m.user_id != admin_user_id}
    if not required:
        return AnnualConsentAssessment(False, 0, 0, (), 'SEM_OUTROS_MEMBROS')
    latest: dict[str, ConsentEvent] = {}
    for event in events:
        if (event.tenant_id != tenant_id or event.cycle_year != cycle_year
                or event.beneficiary_admin_user_id != admin_user_id
                or event.terms_version != terms_version
                or event.voter_membership_id not in required
                or event.occurred_at.tzinfo is None or event.occurred_at > at):
            continue
        previous = latest.get(event.voter_membership_id)
        if (previous is None or event.occurred_at > previous.occurred_at or
                (event.occurred_at == previous.occurred_at and
                 previous.kind == 'SIGNED' and event.kind != 'SIGNED')):
            # Mesmo instante: revogação ou estado desconhecido prevalece,
            # independentemente da ordem dos eventos.
            latest[event.voter_membership_id] = event
    signed = {member_id for member_id, event in latest.items() if event.kind == 'SIGNED'}
    missing = tuple(sorted(required - signed))
    return AnnualConsentAssessment(
        not missing, len(required), len(signed), missing,
        'UNANIME_VIGENTE' if not missing else 'ANUENCIA_PENDENTE_OU_REVOGADA')
