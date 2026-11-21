"""M3200: exact OCI disaster-recovery thresholds, fail-closed review only."""
from dataclasses import replace
from datetime import datetime,timedelta,timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.oci_recovery_policy import (
    OciOperationalEvidence, assess_oci_evidence,
    CONTRACT, MAX_BACKUP_AGE, MAX_WAL_AGE, MAX_RESTORE_AGE,
)

NOW=datetime(2026,11,4,20,0,tzinfo=timezone.utc)


def good():
    return OciOperationalEvidence(
        environment="HOMOLOGACAO",
        oci_server_deployed=True,
        database_exists=True,
        database_private_network=True,
        tls_verified=True,
        iam_least_privilege=True,
        vault_secret_isolation=True,
        backup_encrypted=True,
        backup_external_copy=True,
        last_full_backup_at=NOW-timedelta(hours=2),
        wal_archiving_supported=True,
        wal_archiving_enabled=True,
        last_wal_archive_at=NOW-timedelta(minutes=3),
        retention_days=35,
        last_disposable_restore_at=NOW-timedelta(days=7),
        measured_rpo_minutes=60,
        measured_rto_minutes=480,
        incident_alerting_enabled=True,
        reconciliation_after_restore_tested=True,
        owner_cost_reviewed=True,
        evidence_external_attestation_ref="CI-EXTERNAL-PROOF-ONLY",
    )


def test_full_evidence_passes_manual_review_not_activation():
    r=assess_oci_evidence(good(),now=NOW)
    assert r.eligible_for_manual_review
    assert r.checks_total==18
    assert r.checks_passed==18
    assert not r.failures
    assert r.oci_provisioning_executed is False
    assert r.terraform_apply_authorized is False
    assert r.financial_activation_authorized is False
    assert r.bank_reconciled is False
    assert r.ledger_written is False


@pytest.mark.parametrize("change,expected",[
    ({"environment":"PRODUCAO"},"ENVIRONMENT_HOMOLOGACAO"),
    ({"oci_server_deployed":False},"OCI_DEPLOYED"),
    ({"database_exists":False},"POSTGRESQL_PROVISIONED"),
    ({"database_private_network":False},"DB_PRIVATE_NETWORK"),
    ({"tls_verified":False},"TLS_VERIFIED"),
    ({"iam_least_privilege":False},"IAM_LEAST_PRIVILEGE"),
    ({"vault_secret_isolation":False},"VAULT_TENANT_ISOLATION"),
    ({"backup_encrypted":False},"DAILY_BACKUP_ENCRYPTED"),
    ({"backup_external_copy":False},"BACKUP_COPY_OUTSIDE_PRIMARY"),
    ({"wal_archiving_supported":False},"WAL_ARCHIVE_15_MINUTES"),
    ({"wal_archiving_enabled":False},"WAL_ARCHIVE_15_MINUTES"),
    ({"retention_days":34},"RETENTION_35_DAYS"),
    ({"retention_days":True},"RETENTION_35_DAYS"),
    ({"measured_rpo_minutes":61},"RPO_60_MINUTES"),
    ({"measured_rpo_minutes":-1},"RPO_60_MINUTES"),
    ({"measured_rto_minutes":481},"RTO_480_MINUTES"),
    ({"measured_rto_minutes":True},"RTO_480_MINUTES"),
    ({"incident_alerting_enabled":False},"INCIDENT_ALERTS"),
    ({"reconciliation_after_restore_tested":False},"POST_RESTORE_RECONCILIATION"),
    ({"owner_cost_reviewed":False},"OWNER_COST_REVIEW"),
    ({"evidence_external_attestation_ref":""},"EXTERNAL_ATTESTATION"),
    ({"evidence_external_attestation_ref":"../../../secret"},"EXTERNAL_ATTESTATION"),
])
def test_missing_compliance_rejected(change,expected):
    r=assess_oci_evidence(replace(good(),**change),now=NOW)
    assert expected in r.failures
    assert not r.eligible_for_manual_review
    assert not r.financial_activation_authorized


@pytest.mark.parametrize("key,age,expected",[
    ("last_full_backup_at",timedelta(hours=24,seconds=1),"DAILY_BACKUP_ENCRYPTED"),
    ("last_wal_archive_at",timedelta(minutes=15,seconds=1),"WAL_ARCHIVE_15_MINUTES"),
    ("last_disposable_restore_at",timedelta(days=90,seconds=1),"RESTORE_90_DAYS"),
    ("last_full_backup_at",timedelta(days=-1),"DAILY_BACKUP_ENCRYPTED"),
    ("last_wal_archive_at",timedelta(days=-1),"WAL_ARCHIVE_15_MINUTES"),
    ("last_disposable_restore_at",timedelta(days=-1),"RESTORE_90_DAYS"),
])
def test_ages_strict(key,age,expected):
    r=assess_oci_evidence(replace(good(),**{key:NOW-age}),now=NOW)
    assert expected in r.failures
    assert not r.eligible_for_manual_review


def test_boundaries_are_inclusive():
    d=replace(good(),
        last_full_backup_at=NOW-MAX_BACKUP_AGE,
        last_wal_archive_at=NOW-MAX_WAL_AGE,
        last_disposable_restore_at=NOW-MAX_RESTORE_AGE,
    )
    r=assess_oci_evidence(d,now=NOW)
    assert r.eligible_for_manual_review


def test_no_evidence_cannot_fake_oci_deployment():
    d=replace(good(),
        oci_server_deployed=False,
        last_full_backup_at=None,
        last_wal_archive_at=None,
        last_disposable_restore_at=None,
    )
    r=assess_oci_evidence(d,now=NOW)
    assert "OCI_DEPLOYED" in r.failures
    assert "DAILY_BACKUP_ENCRYPTED" in r.failures
    assert "WAL_ARCHIVE_15_MINUTES" in r.failures
    assert "RESTORE_90_DAYS" in r.failures


def test_health_is_inert_no_real_oci_or_database():
    with TestClient(app) as c:
        d=c.get("/api/health/features/m3200").json()
    assert d["contract"]==CONTRACT
    assert d["workstream"]=="AI_STUDIO"
    assert d["backup_recovery_policy_in_code"] is True
    assert d["oci_staging_deployed"] is False
    assert d["financial_closing_authorized"] is False
    assert d["real_payments_enabled"] is False
