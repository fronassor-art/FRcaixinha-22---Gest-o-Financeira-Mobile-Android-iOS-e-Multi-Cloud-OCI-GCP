"""FR Finance: bind existing invitation/password flows to the existing FastAPI.

This is a secure adapter boundary, NOT a second API or a delivery worker.
Until a reviewed, durable same-database backend worker is injected by the
deployment, requests remain 503. Never send SMTP from an HTTP request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable
from uuid import UUID

from fastapi import HTTPException, Request


@dataclass(frozen=True, slots=True)
class AccessDeliveryReceipt:
    """Only an actual committed original-PostgreSQL transaction may return this."""
    event_id: UUID
    persisted: bool = False
    durable_outbox_queued: bool = False
    email_sent: bool = False
    recipient_verified: bool = False
    user_activated: bool = False


@dataclass(frozen=True, slots=True)
class AccessDeliveryBinding:
    """Installed only after a deployment-specific review of existing workers.

    The caller supplying the binding must independently prove these properties.
    Flags here are local configuration assertions, NOT proof from a provider.
    """
    invite: Callable[..., Awaitable[AccessDeliveryReceipt]]
    reset: Callable[..., Awaitable[AccessDeliveryReceipt]]
    verify_invitation_email: Callable[..., Awaitable[bool]] | None = None
    complete_password_reset: Callable[..., Awaitable[bool]] | None = None
    original_db_verified: bool = False
    segregated_worker_verified: bool = False
    durable_outbox_verified: bool = False
    scoped_audit_verified: bool = False
    smtp_credential_protected: bool = False
    external_delivery_authorized: bool = False


def require_access_delivery(request: Request) -> AccessDeliveryBinding:
    runtime = getattr(request.app.state, "access_delivery_runtime", None)
    if not isinstance(runtime, AccessDeliveryBinding) or not all((
        runtime.original_db_verified is True,
        runtime.segregated_worker_verified is True,
        runtime.durable_outbox_verified is True,
        runtime.scoped_audit_verified is True,
        runtime.smtp_credential_protected is True,
        runtime.external_delivery_authorized is True,
    )):
        raise HTTPException(
            status_code=503,
            detail="Entrega de convites e recuperação por e-mail ainda não implementada na API operacional.",
        )
    return runtime


def verified_enqueue(receipt: object) -> None:
    """Never mistake a synthetic receipt or SMTP acceptance for a queued event."""
    if (type(receipt) is not AccessDeliveryReceipt
            or type(receipt.event_id) is not UUID
            or receipt.event_id.int == 0
            or receipt.persisted is not True
            or receipt.durable_outbox_queued is not True
            or receipt.email_sent is not False
            or receipt.recipient_verified is not False
            or receipt.user_activated is not False):
        raise HTTPException(
            status_code=503,
            detail="Entrega não confirmada no armazenamento transacional original.",
        )


def invitation_accepted_response(receipt: AccessDeliveryReceipt) -> dict[str, object]:
    verified_enqueue(receipt)
    return {
        "status": "QUEUED_FOR_DELIVERY",
        "event_id": str(receipt.event_id),
        "email_sent": False,
        "recipient_verified": False,
        "activation_authorized": False,
        "user_created": False,
    }


def password_recovery_accepted_response(receipt: AccessDeliveryReceipt) -> dict[str, object]:
    verified_enqueue(receipt)
    # Never reveal whether an account exists or a token was created.
    return {
        "status": "REQUEST_ACCEPTED_IF_ELIGIBLE",
        "message": "Se o endereço estiver cadastrado, enviaremos as instruções de recuperação.",
        "user_exists": None,
        "email_sent": False,
        "account_activated": False,
    }
