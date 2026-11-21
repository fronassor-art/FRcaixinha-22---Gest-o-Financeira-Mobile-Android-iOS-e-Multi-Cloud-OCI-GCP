"""FR Finance M39920 — preflight for *candidate* double-entry journals, no I/O.

This module cannot post a journal, approve an expense, settle a provider
payment, grant remuneration, change a cycle or read/write either PostgreSQL.
A passing preflight validates SHAPE only. Evidence, ownership, policy, consent
and provider reconciliation must be independently attested later.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import re
from uuid import UUID

from .exclusive_cashbox_provenance import (
    PLATFORM_MASTER, TENANT_ADMIN_OWN, TENANT_COLLECTIVE,
    classify_cashbox_source,
)

_SCOPE_PREFIX = {
    PLATFORM_MASTER: "PM_",
    TENANT_ADMIN_OWN: "TA_",
    TENANT_COLLECTIVE: "TC_",
}
_REF = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{5,119}$")
_CODE = re.compile(r"^[A-Z0-9_]{4,40}$")
_MAX_CENTS = 999_999_999_999
_MAX_LINES = 100


@dataclass(frozen=True)
class CandidateLine:
    scope: str
    tenant_id: UUID | None
    account_code: str
    side: str
    amount_cents: int


@dataclass(frozen=True)
class JournalCandidate:
    scope: str
    tenant_id: UUID | None
    event_type: str
    evidence_reference: str
    lines: tuple[CandidateLine, ...]
    fingerprint: str
    state: str = "STRUCTURAL_PREVIEW_NO_POSTING"
    evidence_attested: bool = False
    policy_attested: bool = False
    provider_reconciled: bool = False
    journal_posted: bool = False
    payment_enabled: bool = False
    withdrawal_enabled: bool = False


def review_journal_candidate(
    *, event_type: str, scope: str, tenant_id: UUID | None,
    evidence_reference: str, lines: tuple[CandidateLine, ...],
) -> JournalCandidate:
    """Enforce scope + double entry before any future persistence design.

    Fingerprint is a deterministic *candidate identity*, not a database-backed
    idempotency guarantee. It deliberately contains no person, token or amount
    in a user-visible output. This module has no posting or release function.
    """
    classify_cashbox_source(event_type, scope, tenant_id)
    if type(evidence_reference) is not str or not _REF.fullmatch(evidence_reference):
        raise ValueError("Identificador de evidência inválido")
    if type(lines) is not tuple or not 2 <= len(lines) <= _MAX_LINES:
        raise ValueError("Partidas contábeis incompletas ou excessivas")

    dr = cr = 0
    used_accounts: set[tuple[str, str]] = set()
    manifest = []
    for line in lines:
        if type(line) is not CandidateLine:
            raise ValueError("Linha contábil inválida")
        if line.scope != scope or line.tenant_id != tenant_id:
            raise ValueError("Linha de caixa ou tenant diferente")
        if type(line.account_code) is not str or not _CODE.fullmatch(line.account_code):
            raise ValueError("Conta contábil inválida")
        if not line.account_code.startswith(_SCOPE_PREFIX[scope]):
            raise ValueError("Conta de domínio patrimonial diferente")
        if type(line.side) is not str or line.side not in ("DR", "CR"):
            raise ValueError("Partida contábil não reconhecida")
        if type(line.amount_cents) is not int or not 1 <= line.amount_cents <= _MAX_CENTS:
            raise ValueError("Valor em centavos inválido")
        if (line.account_code, line.side) in used_accounts:
            raise ValueError("Partida repetida para a mesma conta")
        used_accounts.add((line.account_code, line.side))
        if line.side == "DR":
            dr += line.amount_cents
        else:
            cr += line.amount_cents
        manifest.append((line.account_code, line.side, line.amount_cents))

    if not dr or dr != cr or (
        len({code for code, _, _ in manifest}) < 2
    ):
        raise ValueError("Lançamento desbalanceado ou sem contrapartida independente")

    # Canonical ordering removes ambiguity from a caller's line order.
    material = {
        "version": "M39920_CANDIDATE_V1",
        "event_type": event_type,
        "scope": scope,
        "tenant_id": str(tenant_id) if tenant_id is not None else None,
        "evidence_reference": evidence_reference,
        "lines": sorted(manifest),
    }
    digest = sha256(json.dumps(material, sort_keys=True,
                               separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()
    return JournalCandidate(
        scope=scope, tenant_id=tenant_id,
        event_type=event_type, evidence_reference=evidence_reference,
        lines=lines, fingerprint=digest,
    )
