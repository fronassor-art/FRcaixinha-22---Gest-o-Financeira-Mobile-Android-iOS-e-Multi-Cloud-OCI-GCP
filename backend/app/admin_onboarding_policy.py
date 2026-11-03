"""Blueprint somente leitura de convite administrativo, SEM efeitos colaterais.

FRcaixinha AI Studio Mobile: nunca emite token, senha, e-mail, memberships
ou aprovacoes. A API de producao deve implementar persistencia transacional
e controles juridicos/tecnicos adicionais antes de liberar qualquer acao.
"""

from typing import Literal

FLOW_STATES = (
    "REQUESTED", "EMAIL_VERIFIED", "MASTER_REVIEW", "APPROVED",
    "INVITE_PREPARED", "DELIVERED", "ACCEPTED", "ACTIVE",
)
TERMINAL_STATES = ("REJECTED", "REVOKED", "EXPIRED")
# Gates tecnicos que ainda NAO foram implementados ou validados para uso real.
REQUIRED_GATES = (
    "MASTER_MFA", "DUAL_CONTROL", "EMAIL_OWNERSHIP",
    "INVITE_SINGLE_USE", "EXPIRATION_AND_REVOCATION",
    "TRANSACTIONAL_AUDIT", "IDENTITY_MEMBERSHIP_RECHECK",
    "DELIVERY_PROVIDER_VERIFIED", "LEGAL_APPROVAL",
)


def readiness_manifest() -> dict:
    """Contrato minimo transparente: nenhum gate operacional foi liberado."""
    return {
        "scope": "MASTER_ADMIN_ONBOARDING_PREPARATION",
        "mode": "READ_ONLY_PREFLIGHT",
        "operations_enabled": False,
        "real_invites_enabled": False,
        "real_account_changes_enabled": False,
        "workflow_states": list(FLOW_STATES + TERMINAL_STATES),
        "gates": {name: "BLOCKED" for name in REQUIRED_GATES},
        "next_action": "REQUIRES_SEPARATE_SCHEMA_RLS_AND_SECURITY_APPROVAL",
    }


def preflight_assessment(
    *, tenant_id: str, tenant_name: str,
    tenant_status: Literal["ATIVO", "SUSPENSO", "RASCUNHO_INATIVO", "ENCERRADO"] | str,
    is_owner_box: bool, candidate_id: str | None, actor_id: str,
) -> dict:
    """Avalia referencias tecnicas sem consultar pessoa, convite ou dados financeiros."""
    tenant_active = tenant_status == "ATIVO"
    candidate_identified = candidate_id is not None
    self_approval_blocked = candidate_id is not None and (
        candidate_id.lower() == actor_id.lower()
    )
    reasons = [f"GATE_{name}_BLOCKED" for name in REQUIRED_GATES]
    if not tenant_active:
        reasons.append("TENANT_NOT_ACTIVE")
    if not candidate_identified:
        reasons.append("CANDIDATE_NOT_PROVIDED")
    if self_approval_blocked:
        reasons.append("SELF_APPROVAL_PROHIBITED")
    return {
        "source": "POSTGRESQL_RLS",
        "scope": "MASTER_ADMIN_ONBOARDING_PREFLIGHT",
        "result": "BLOCKED_PREPARATION_ONLY",
        "tenant": {
            "id": tenant_id,
            "display_name": tenant_name,
            "status": tenant_status,
            "is_owner_box": is_owner_box,
        },
        "target_role": "TENANT_ADMIN",
        "candidate_reference_present": candidate_identified,
        "candidate_identity_verified": False,
        "tenant_active": tenant_active,
        "self_approval_blocked": self_approval_blocked,
        "blocking_reasons": reasons,
        "writes_performed": False,
        "invitation_created": False,
        "approval_granted": False,
        "real_account_changed": False,
    }


def preview_workflow_transition(
    *, current: str, proposed: str, actor_role: str,
    candidate_is_actor: bool, email_verified: bool, tenant_active: bool,
    approval_independent: bool, token_valid: bool,
) -> dict:
    """Simulador puro para testes adversariais, NUNCA executa transicoes reais."""
    allowed_edges = dict(zip(FLOW_STATES, FLOW_STATES[1:]))
    reasons = []
    if current not in FLOW_STATES:
        reasons.append("UNKNOWN_CURRENT_STATE")
    if proposed not in FLOW_STATES + TERMINAL_STATES:
        reasons.append("UNKNOWN_PROPOSED_STATE")
    if current in allowed_edges and proposed != allowed_edges[current]:
        reasons.append("INVALID_STATE_TRANSITION")
    if actor_role != "MASTER":
        reasons.append("MASTER_REQUIRED")
    if candidate_is_actor:
        reasons.append("SELF_APPROVAL_PROHIBITED")
    if not email_verified:
        reasons.append("EMAIL_NOT_VERIFIED")
    if not tenant_active:
        reasons.append("TENANT_NOT_ACTIVE")
    if not approval_independent:
        reasons.append("DUAL_CONTROL_REQUIRED")
    if not token_valid:
        reasons.append("TOKEN_EXPIRED_OR_UNVERIFIED")
    # Mesmo sem pendencias hipoteticas, operacao continua bloqueada por gate real.
    return {
        "transition_executed": False,
        "allowed_for_real_execution": False,
        "simulator_only": True,
        "reasons": reasons + ["RUNTIME_OPERATIONS_DISABLED"],
    }
