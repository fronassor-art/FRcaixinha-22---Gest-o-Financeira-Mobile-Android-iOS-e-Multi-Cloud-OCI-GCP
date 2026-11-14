"""Matriz de INTENÇÃO de governança. Não implementa grant, RLS ou permissão.

NÃO usar o resultado deste módulo como autorização. A aplicação deve
continuar validando sessão e contexto, e o PostgreSQL aplica RLS.
"""
from types import MappingProxyType

ROLES = ("MASTER", "TENANT_ADMIN", "TENANT_MEMBER", "ANONYMOUS")
RESOURCES = (
    "PLATFORM_TENANT_REGISTRY",
    "PLATFORM_ADMIN_REFERENCES",
    "ADMIN_ONBOARDING_PREFLIGHT",
    "ADMIN_WORKFLOW_SIMULATOR",
    "TENANT_FINANCIAL_DATA",
    "MEMBER_PRIVATE_DATA",
    "INVITATION_TOKEN_STORAGE",
    "INVITATION_ISSUANCE",
    "MEMBERSHIP_ROLE_CHANGE",
    "DIRECT_AUDIT_MUTATION",
)
ACCESS = ("DENIED", "METADATA_ONLY", "SIMULATION_ONLY",
          "OWN_TENANT_ONLY", "OWN_RECORD_ONLY")

# Os três acessos delimitados dependem SEMPRE das verificações RBAC+RLS;
# jamais representam uma autorização concedida por esta matriz.
MATRIX = MappingProxyType({
    "PLATFORM_TENANT_REGISTRY": ("METADATA_ONLY", "DENIED", "DENIED", "DENIED"),
    "PLATFORM_ADMIN_REFERENCES": ("METADATA_ONLY", "DENIED", "DENIED", "DENIED"),
    "ADMIN_ONBOARDING_PREFLIGHT": ("SIMULATION_ONLY", "DENIED", "DENIED", "DENIED"),
    "ADMIN_WORKFLOW_SIMULATOR": ("SIMULATION_ONLY", "DENIED", "DENIED", "DENIED"),
    "TENANT_FINANCIAL_DATA": ("DENIED", "OWN_TENANT_ONLY", "OWN_RECORD_ONLY", "DENIED"),
    "MEMBER_PRIVATE_DATA": ("DENIED", "OWN_TENANT_ONLY", "OWN_RECORD_ONLY", "DENIED"),
    "INVITATION_TOKEN_STORAGE": ("DENIED", "DENIED", "DENIED", "DENIED"),
    "INVITATION_ISSUANCE": ("DENIED", "DENIED", "DENIED", "DENIED"),
    "MEMBERSHIP_ROLE_CHANGE": ("DENIED", "DENIED", "DENIED", "DENIED"),
    "DIRECT_AUDIT_MUTATION": ("DENIED", "DENIED", "DENIED", "DENIED"),
})


def permission_matrix_contract() -> dict:
    return {
        "scope": "MASTER_ONBOARDING_PERMISSION_MATRIX",
        "source": "DECLARED_POLICY_NOT_RUNTIME_AUTHORITY",
        "mode": "DOCUMENTATION_AND_CI_ONLY",
        "grants_changed": False,
        "operations_enabled": False,
        "database_migration_required": False,
        "roles": list(ROLES),
        "resources": list(RESOURCES),
        "permissions": {
            name: dict(zip(ROLES, row)) for name, row in MATRIX.items()
        },
        "enforcement": "FASTAPI_RBAC_PLUS_POSTGRESQL_RLS",
        "sensitive_actions": "BLOCKED_PENDING_APPROVAL",
    }
