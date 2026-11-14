"""FR Finance M37323-M37330 — static OCI staging bootstrap plan, NEVER APPLY.

Reads only audited, versioned template files. No cloud SDK, external network,
filesystem writes, SQL, migrations, payment operations, secret collection or
service start. A valid blueprint is documentation, NOT deployment approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib

ROOT_RELATIVE="infra/oci/staging-reuse"
TEMPLATES=(
    "fr-finance-staging-api.service.template",
    "Caddyfile.template",
    "staging-runtime.env.example",
)
_CRITICAL_BLOCKERS=(
    "OCI_STAGING_RUNNING_VM_ABSENT",
    "OCI_STAGING_ACTIVE_VAULT_ABSENT",
    "OCI_HTTPS_443_INGRESS_NOT_PREPARED",
    "OCI_INSTANCE_PRINCIPAL_IAM_NOT_VERIFIED",
    "OCI_NSG_AND_OS_FIREWALL_NOT_VERIFIED",
    "OCI_PUBLIC_DNS_TLS_HTTPS_NOT_VERIFIED",
    "OCI_DATABASE_TLS_RLS_NOT_VERIFIED",
    "OCI_BACKUP_RESTORE_NOT_VERIFIED",
    "OCI_BACKEND_HEALTH_AND_AUTH_NOT_VERIFIED",
    "OCI_MARKETPLACE_WEBHOOK_AND_SETTLEMENT_NOT_VERIFIED",
    "OCI_PIX_AND_USER_ACTIVATION_NOT_AUTHORIZED",
)
REQUIRED={
    TEMPLATES[0]:(
        "ConditionPathExists=/etc/fr-finance/explicitly-reviewed-staging-deploy",
        "User=frfinance",
        "Group=frfinance",
        "WorkingDirectory=/opt/fr-finance/current/backend",
        "EnvironmentFile=/run/fr-finance/runtime.env",
        "ExecStart=/opt/fr-finance/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1",
        "NoNewPrivileges=true",
        "ProtectSystem=strict",
        "ProtectHome=true",
        "PrivateTmp=true",
        "UMask=0077",
        "StateDirectory=fr-finance",
    ),
    TEMPLATES[1]:(
        "{$FR_FINANCE_API_FQDN}",
        "handle /api/*",
        "reverse_proxy 127.0.0.1:8000",
        "respond 404",
        "Strict-Transport-Security",
    ),
    TEMPLATES[2]:(
        "ENVIRONMENT=homologation",
        "OCI_REGION=sa-saopaulo-1",
        "FR_FINANCE_PIX_REAL=0",
        "FR_FINANCE_REAL_USER_ACTIVATION=0",
        "FRC_MP_OCI_STAGING_ENABLED=0",
        "FRC_MP_ACCEPT_LIVE_NOTIFICATIONS=0",
        "FR_FINANCE_REAL_MAIL=0",
    ),
}
FORBIDDEN=(
    "--host 0.0.0.0",
    "--port 5432",
    "--port 5433",
    "reverse_proxy 0.0.0.0",
    "reverse_proxy localhost:5432",
    "ENVIRONMENT=production",
    "FRC_MP_ACCEPT_LIVE_NOTIFICATIONS=1",
    "FRC_MP_OCI_STAGING_ENABLED=1",
    "FR_FINANCE_PIX_REAL=1",
    "FR_FINANCE_REAL_USER_ACTIVATION=1",
    "FR_FINANCE_REAL_MAIL=1",
    "terraform apply",
    "oci compute instance launch",
    "oci kms management vault create",
    "0.0.0.0:5432",
    "0.0.0.0:5433",
    "http://",
)


class BootstrapPlanBlocked(ValueError):
    """Reason codes only. Never include file body or secrets in errors."""


@dataclass(frozen=True)
class BootstrapPlan:
    checked_templates: int
    content_sha256: str
    files_read_only: bool
    existing_vcn_reuse_only: bool
    backend_loopback_only: bool
    internet_https_requires_future_approval: bool
    blocked_gates: tuple[str, ...]
    cloud_mutations: bool = False
    sql_applied: bool = False
    deployment_authorized: bool = False
    paid_resource_authorized: bool = False
    production_auth_authorized: bool = False
    user_activation_authorized: bool = False
    real_pix_authorized: bool = False


def _read_template(root: Path, filename: str) -> str:
    location=root/ROOT_RELATIVE/filename
    if location.is_symlink() or not location.is_file():
        raise BootstrapPlanBlocked("BOOTSTRAP_TEMPLATE_MISSING_OR_SYMLINK")
    try:
        payload=location.read_bytes()
        if not 0<len(payload)<=20_000 or b"\x00" in payload:
            raise ValueError("invalid-size")
        value=payload.decode("utf-8")
    except (OSError,UnicodeError,ValueError):
        raise BootstrapPlanBlocked("BOOTSTRAP_TEMPLATE_INVALID") from None
    return value


def inspect_plan_only(root: Path) -> BootstrapPlan:
    if not isinstance(root, Path) or not root.is_dir():
        raise BootstrapPlanBlocked("BOOTSTRAP_REPOSITORY_INVALID")
    dig=hashlib.sha256()
    for name in TEMPLATES:
        body=_read_template(root,name)
        if any(token not in body for token in REQUIRED[name]):
            raise BootstrapPlanBlocked("BOOTSTRAP_SECURITY_REQUIREMENT_MISSING")
        if any(token in body for token in FORBIDDEN):
            raise BootstrapPlanBlocked("BOOTSTRAP_FORBIDDEN_OPERATION_OR_VALUE")
        # No URL, credentials, tokens or real hostnames are stored in templates.
        if name==TEMPLATES[1]:
            if body.count("{$FR_FINANCE_API_FQDN}")!=1:
                raise BootstrapPlanBlocked("BOOTSTRAP_HOST_PLACEHOLDER_INVALID")
            if body.count("reverse_proxy")!=1 or body.count("handle /api/*")!=1:
                raise BootstrapPlanBlocked("BOOTSTRAP_PROXY_SCOPE_INVALID")
        if name==TEMPLATES[2]:
            lines=[ln.strip() for ln in body.splitlines()
                   if ln.strip() and not ln.lstrip().startswith("#")]
            keys=[ln.split("=",1)[0] for ln in lines if "=" in ln]
            if (len(lines)!=len(REQUIRED[name]) or len(keys)!=len(lines)
                    or len(set(keys))!=len(keys)
                    or any(ln not in REQUIRED[name] for ln in lines)):
                raise BootstrapPlanBlocked("BOOTSTRAP_RUNTIME_FLAGS_NOT_DISABLED")
        dig.update(name.encode("utf-8")+b"\x00"+body.encode("utf-8")+b"\x00")
    return BootstrapPlan(
        checked_templates=len(TEMPLATES),
        content_sha256=dig.hexdigest(),
        files_read_only=True,
        existing_vcn_reuse_only=True,
        backend_loopback_only=True,
        internet_https_requires_future_approval=True,
        blocked_gates=_CRITICAL_BLOCKERS,
    )
