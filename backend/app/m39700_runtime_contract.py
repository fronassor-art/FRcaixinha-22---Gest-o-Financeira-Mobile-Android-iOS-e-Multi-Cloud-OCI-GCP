"""FR Finance M39700 — public, non-secret running API contract.

This contract distinguishes *loaded process code* from a Git worktree
updated while uvicorn continued running. It is NOT build-SHA, database,
reconciliation, legal, provider, or production attestation.
"""
from __future__ import annotations

CONTRACT = "FR_FINANCE_M39700_RUNTIME_V1"
EXPECTED_GET = frozenset({
    "/api/v1/tenants/{tenant_id}/special-credit/capabilities",
    "/api/v1/tenants/{tenant_id}/special-credit/members",
    "/api/v1/tenants/{tenant_id}/special-credit/campaigns",
    "/api/v1/tenants/{tenant_id}/special-credit/cycle-readiness",
    "/api/v1/master/exclusive-cashbox",
    "/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox",
})


def checkpoint_payload() -> dict:
    """Version marker is sourced from loaded Python, never an env/URL/token."""
    return {
        "product": "FR Finance",
        "workstream": "AI_STUDIO",
        "contract": CONTRACT,
        "runtime_contract_loaded": True,
        "repository_head_verified": False,
        "database_catalog_attested": False,
        "bank_reconciled": False,
        "real_pix_enabled": False,
        "real_payments_enabled": False,
        "production_authorized": False,
    }


def classify_health(document: object) -> str:
    if (type(document) is dict
            and document.get("app") == "FR Finance"
            and document.get("status") == "ONLINE"):
        return "FR_FINANCE_ONLINE"
    return "WRONG_APP_OR_HEALTH"


def classify_checkpoint(document: object) -> str:
    if type(document) is not dict:
        return "RUNTIME_CONTRACT_INVALID"
    required = checkpoint_payload()
    if document.keys() != required.keys():
        return "RUNTIME_CONTRACT_INVALID"
    if any(type(document[key]) is not type(value)
           or document[key] != value for key, value in required.items()):
        return "RUNTIME_CONTRACT_INVALID"
    return "M39700_RUNNING_CODE_LOADED"


def classify_routes(document: object) -> tuple[str, tuple[str, ...]]:
    if type(document) is not dict or type(document.get("paths")) is not dict:
        return "OPENAPI_INVALID", ()
    paths = document["paths"]
    valid = {
        path for path, methods in paths.items()
        if type(path) is str and type(methods) is dict
        and type(methods.get("get")) is dict
    }
    missing = tuple(sorted(EXPECTED_GET - valid))
    return ("GET_ROUTES_PRESENT" if not missing else "GET_ROUTES_MISSING",
            missing)


def classify_readiness(status: int, document: object) -> str:
    """503 is not proof that PG18 is down; auth/config can also block."""
    if (status == 200 and type(document) is dict
            and document.get("status") == "READY_FOR_TEST_AUTH"
            and document.get("scope") == "LOCAL_HOMOLOGATION_ONLY"):
        return "LOCAL_TEST_AUTH_READY"
    if status == 503:
        return "BLOCKED_READINESS_503_AUTH_OR_PG18_REVIEW"
    return "BLOCKED_READINESS_NOT_ATTESTED"
