"""Contrato e simulação de governança Master — SEM persistência ou privilégios.

O fingerprint é somente diagnóstico de um cenário hipotético, NÃO é evento
assinado, trilha persistente, recibo, autenticação, prova de envio ou convite.
"""
import hashlib
import json
import uuid

from .admin_onboarding_policy import FLOW_STATES, TERMINAL_STATES, REQUIRED_GATES

STATES = FLOW_STATES + TERMINAL_STATES
EDGES: dict[str, tuple[str, ...]] = {
    "REQUESTED": ("EMAIL_VERIFIED", "REJECTED", "REVOKED", "EXPIRED"),
    "EMAIL_VERIFIED": ("MASTER_REVIEW", "REJECTED", "REVOKED", "EXPIRED"),
    "MASTER_REVIEW": ("APPROVED", "REJECTED", "REVOKED", "EXPIRED"),
    "APPROVED": ("INVITE_PREPARED", "REVOKED", "EXPIRED"),
    "INVITE_PREPARED": ("DELIVERED", "REVOKED", "EXPIRED"),
    "DELIVERED": ("ACCEPTED", "REVOKED", "EXPIRED"),
    "ACCEPTED": ("ACTIVE", "REVOKED"),
    "ACTIVE": (),
    "REJECTED": (),
    "REVOKED": (),
    "EXPIRED": (),
}
AUDIT_FIELDS = (
    "request_id", "tenant_id", "transition", "actor_id",
    "independent_approver_id", "expected_revision", "observed_revision",
    "decision", "idempotency_key_hash", "previous_event_hash",
    "event_hash", "occurred_at",
)
TRANSACTION_GUARDS = (
    "REQUIRE_MASTER_AND_MFA",
    "TENANT_RLS_AND_STATUS_RECHECK",
    "SINGLE_USE_EMAIL_PROOF",
    "INDEPENDENT_APPROVER",
    "EXPECTED_REVISION_COMPARE_AND_SWAP",
    "UNIQUE_IDEMPOTENCY_KEY",
    "EXPIRATION_AND_REVOCATION",
    "AUDIT_APPEND_SAME_TRANSACTION",
    "NO_PRIVILEGE_ESCALATION",
)


def workflow_contract() -> dict:
    return {
        "scope": "MASTER_ONBOARDING_WORKFLOW_CONTRACT",
        "mode": "SPECIFICATION_AND_SIMULATION_ONLY",
        "operations_enabled": False,
        "audit_persisted": False,
        "states": list(STATES),
        "edges": {key: list(destinations) for key, destinations in EDGES.items()},
        "required_gates": list(REQUIRED_GATES),
        "transaction_guards": list(TRANSACTION_GUARDS),
        "proposed_audit_fields": list(AUDIT_FIELDS),
        "max_previous_keys": 32,
        "next_action": "SECURITY_AND_SCHEMA_APPROVAL_REQUIRED",
    }


def preview_transition(
    *, current: str, proposed: str, actor_role: str,
    candidate_is_actor: bool, email_verified: bool, tenant_active: bool,
    independent_approval: bool, token_valid: bool,
    expected_revision: int, observed_revision: int,
    idempotency_key: uuid.UUID, previously_used_keys: list[uuid.UUID],
) -> dict:
    """Deterministic, side-effect-free transition evaluation. ALL paths deny."""
    reasons: list[str] = []
    graph_valid = proposed in EDGES.get(current, ())
    replay_detected = idempotency_key in previously_used_keys
    revision_conflict = expected_revision != observed_revision
    if current in TERMINAL_STATES or current == "ACTIVE":
        reasons.append("FINAL_STATE_IMMUTABLE")
    if not graph_valid:
        reasons.append("INVALID_STATE_TRANSITION")
    if actor_role != "MASTER":
        reasons.append("MASTER_ROLE_REQUIRED")
    if candidate_is_actor:
        reasons.append("SELF_APPROVAL_PROHIBITED")
    if not email_verified:
        reasons.append("EMAIL_NOT_VERIFIED")
    if not tenant_active:
        reasons.append("TENANT_INACTIVE")
    if not independent_approval:
        reasons.append("INDEPENDENT_APPROVAL_REQUIRED")
    if not token_valid:
        reasons.append("TOKEN_EXPIRED_OR_INVALID")
    if revision_conflict:
        reasons.append("REVISION_CONFLICT")
    if replay_detected:
        reasons.append("IDEMPOTENCY_REPLAY")
    # Mesmo que o cenário hipotético passe, NUNCA considerar liberação real.
    reasons.append("RUNTIME_OPERATIONS_DISABLED")
    hypothetical = {
        "schema": 1, "current": current, "proposed": proposed,
        "role": actor_role, "candidate_is_actor": candidate_is_actor,
        "email_verified": email_verified, "tenant_active": tenant_active,
        "independent_approval": independent_approval,
        "token_valid": token_valid, "expected_revision": expected_revision,
        "observed_revision": observed_revision,
        "idempotency_key": str(idempotency_key),
        "previously_used_keys": sorted(str(x) for x in previously_used_keys),
    }
    fingerprint = hashlib.sha256(
        json.dumps(hypothetical, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "scope": "MASTER_ONBOARDING_TRANSITION_PREVIEW",
        "mode": "MEMORY_ONLY_NOT_AUDIT",
        "result": "EXECUTION_DENIED",
        "current_state": current,
        "proposed_state": proposed,
        "graph_valid": graph_valid,
        "revision_conflict": revision_conflict,
        "idempotency_replay_detected": replay_detected,
        "scenario_fingerprint": fingerprint,
        "fingerprint_is_audit_proof": False,
        "reasons": reasons,
        "state_unchanged": True,
        "projected_next_state": None,
        "writes_performed": False,
        "audit_persisted": False,
        "invitation_created": False,
        "account_changed": False,
        "allowed_for_real_execution": False,
    }
