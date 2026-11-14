"""AI Studio M3200: contract-based OCI backup/recovery evidence preflight.

This is a local validator for signed/verified operational observations. It
does NOT read OCI infrastructure, conduct restore, attest signatures, grant
Terraform apply, allow real money or replace an actual disaster recovery test.
Clauses consulted: 13.1-13.6, 9.9 of historic contract reference.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

CONTRACT = "AI_STUDIO_M3200_OCI_BACKUP_RECOVERY_PRECHECK_V1"
MAX_BACKUP_AGE = timedelta(hours=24)
MAX_WAL_AGE = timedelta(minutes=15)
MIN_RETENTION_DAYS = 35
MAX_RESTORE_AGE = timedelta(days=90)
MAX_RPO_MINUTES = 60
MAX_RTO_MINUTES = 480


@dataclass(frozen=True)
class OciOperationalEvidence:
    environment: str
    oci_server_deployed: bool
    database_exists: bool
    database_private_network: bool
    tls_verified: bool
    iam_least_privilege: bool
    vault_secret_isolation: bool
    backup_encrypted: bool
    backup_external_copy: bool
    last_full_backup_at: datetime | None
    wal_archiving_supported: bool
    wal_archiving_enabled: bool
    last_wal_archive_at: datetime | None
    retention_days: int
    last_disposable_restore_at: datetime | None
    measured_rpo_minutes: int
    measured_rto_minutes: int
    incident_alerting_enabled: bool
    reconciliation_after_restore_tested: bool
    owner_cost_reviewed: bool
    evidence_external_attestation_ref: str = ""


@dataclass(frozen=True)
class OciReadinessFinding:
    contract: str
    checks_total: int
    checks_passed: int
    failures: tuple[str, ...]
    eligible_for_manual_review: bool
    oci_provisioning_executed: bool = False
    terraform_apply_authorized: bool = False
    financial_activation_authorized: bool = False
    bank_reconciled: bool = False
    ledger_written: bool = False


def _is_recent(timestamp: datetime | None, now: datetime, max_age: timedelta) -> bool:
    if (type(timestamp) is not datetime or timestamp.tzinfo is None
            or timestamp.utcoffset() is None):
        return False
    age=now-timestamp.astimezone(timezone.utc)
    return timedelta(0) <= age <= max_age


def assess_oci_evidence(
    evidence: OciOperationalEvidence,
    *, now: datetime,
) -> OciReadinessFinding:
    """Review only. Every failure is a stable code, never secret/PII."""
    if type(evidence) is not OciOperationalEvidence:
        raise TypeError("OCI evidence object required")
    if type(now) is not datetime or now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("UTC-aware evaluation timestamp required")
    now=now.astimezone(timezone.utc)
    checks={
        "ENVIRONMENT_HOMOLOGACAO":evidence.environment=="HOMOLOGACAO",
        "OCI_DEPLOYED":evidence.oci_server_deployed is True,
        "POSTGRESQL_PROVISIONED":evidence.database_exists is True,
        "DB_PRIVATE_NETWORK":evidence.database_private_network is True,
        "TLS_VERIFIED":evidence.tls_verified is True,
        "IAM_LEAST_PRIVILEGE":evidence.iam_least_privilege is True,
        "VAULT_TENANT_ISOLATION":evidence.vault_secret_isolation is True,
        "DAILY_BACKUP_ENCRYPTED":(
            evidence.backup_encrypted is True
            and _is_recent(evidence.last_full_backup_at,now,MAX_BACKUP_AGE)
        ),
        "BACKUP_COPY_OUTSIDE_PRIMARY":evidence.backup_external_copy is True,
        "WAL_ARCHIVE_15_MINUTES":(
            evidence.wal_archiving_supported is True
            and evidence.wal_archiving_enabled is True
            and _is_recent(evidence.last_wal_archive_at,now,MAX_WAL_AGE)
        ),
        "RETENTION_35_DAYS":(
            type(evidence.retention_days) is int
            and evidence.retention_days>=MIN_RETENTION_DAYS
        ),
        "RESTORE_90_DAYS":_is_recent(
            evidence.last_disposable_restore_at,now,MAX_RESTORE_AGE
        ),
        "RPO_60_MINUTES":(
            type(evidence.measured_rpo_minutes) is int
            and 0 <= evidence.measured_rpo_minutes <= MAX_RPO_MINUTES
        ),
        "RTO_480_MINUTES":(
            type(evidence.measured_rto_minutes) is int
            and 0 <= evidence.measured_rto_minutes <= MAX_RTO_MINUTES
        ),
        "INCIDENT_ALERTS":evidence.incident_alerting_enabled is True,
        "POST_RESTORE_RECONCILIATION":(
            evidence.reconciliation_after_restore_tested is True
        ),
        "OWNER_COST_REVIEW":evidence.owner_cost_reviewed is True,
        "EXTERNAL_ATTESTATION":(
            type(evidence.evidence_external_attestation_ref) is str
            and 8 <= len(evidence.evidence_external_attestation_ref) <= 128
            and evidence.evidence_external_attestation_ref.isascii()
            and evidence.evidence_external_attestation_ref.replace("-","").replace("_","").isalnum()
        ),
    }
    failed=tuple(k for k,passed in checks.items() if not passed)
    return OciReadinessFinding(
        contract=CONTRACT,checks_total=len(checks),
        checks_passed=len(checks)-len(failed),
        failures=failed,
        eligible_for_manual_review=not failed,
    )
