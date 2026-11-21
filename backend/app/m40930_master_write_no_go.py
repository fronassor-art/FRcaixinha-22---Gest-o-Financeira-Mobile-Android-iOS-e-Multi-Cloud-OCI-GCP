"""M40930: containment fence for real Master SQL mutations.

The M40923-M40929 signature, issuer and guardian implementations are
**disposable-CI proofs only**, not installed in production FastAPI. No
environment variable, UID check, bearer, feature flag or certificate alone
constitutes an approved independent SQL authorization.

This dependency is intentionally fail-closed in ALL environments. Unit tests
using synthetic connections can override it in the FastAPI test application;
the application itself exposes no runtime override. Do not lift until the
original Master routes use independently approved, audited SQL boundaries.
"""
from fastapi import HTTPException, status


def require_unreleased_master_write() -> None:
    """Deny SQL-changing Master endpoints before session/database acquisition."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Gravacoes Master indisponiveis ate homologacao de custodia independente.",
    )
