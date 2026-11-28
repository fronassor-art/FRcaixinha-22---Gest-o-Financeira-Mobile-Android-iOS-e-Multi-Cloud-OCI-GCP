"""M38804–M38879: one existing FR Finance schema, safe notifications & Pix."""
from __future__ import annotations

from pathlib import Path
import ast
import json

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "backend/app/routers"
CYCLE = SOURCE / "cycle_contribution_price.py"
NOTIF = SOURCE / "notifications.py"
PIX = SOURCE / "pix_automation.py"
CLOSINGS = SOURCE / "closings.py"
M043 = ROOT / "backend/local_migrations/043_cycle_contribution_contract_minimum.sql"
M044 = ROOT / "backend/local_migrations/044_cycle_opening_audit.sql"
IDENTITY = ROOT / "backend/config/frfinance_project_identity.json"
HEALTH = ROOT / "backend/app/main.py"


def text(path):
    return path.read_text(encoding="utf-8")


def test_sources_parse_without_running_db_or_app():
    for source in (CYCLE, NOTIF, PIX, CLOSINGS, HEALTH):
        ast.parse(text(source), filename=source.name)


def test_one_original_project_manifest_and_no_provision_permission():
    data = json.loads(text(IDENTITY))
    p = data["active_project"]["postgresql"]
    assert (p["database"],p["port"],p["owner"]) == (
        "frcaixinha_aistudio_dev", 5433, "frc_ai_owner")
    assert p["pgdata"].endswith("/frcaixinha_aistudio_pg18")
    assert data["active_project"]["termux_worktree"] == "fr-finance"
    assert data["never_start_server_from_project_identity"] is True
    assert data["never_apply_migrations_during_preflight"] is True
    assert data["production_authorized"] is False


@pytest.mark.parametrize("constraint", [
    "M043_POLICY_FLOOR", "M043_QUOTA_FLOOR", "M043_NO_DEFAULTS",
    "M043_WRAPPER_FLOOR", "M043_LEGACY_RESTRICTED",
    "M044_AUDIT_RLS", "M044_IMMUTABLE_TRIGGERS",
    "M044_CREATE_FLOOR", "M044_ROLE_BOUNDARY", "M044_UNIQUE_REPLAY",
])
def test_043_044_compatible_observed_does_not_claim_migration_was_run(constraint):
    report = text(ROOT / "backend/scripts/aistudio_m38701_local_043_044_catalog_readonly.py")
    assert constraint in report
    assert "NOT_ATTESTED" in report
    assert "READ ONLY" in report


@pytest.mark.parametrize("schema", [M043, M044])
def test_do_not_reapply_observed_migration_as_new_project(schema):
    sql = text(schema)
    assert "frcaixinha_aistudio_dev" in sql
    assert "frc_ai_owner" in sql
    assert "frcaixinha_2_2_dev" not in sql
    assert "CREATE DATABASE" not in sql.upper()
    assert "DROP DATABASE" not in sql.upper()


@pytest.mark.parametrize("amount", [
    "15000", "1000000", "strict=True", "existing_contributions_repriced",
])
def test_cycle_quota_route_has_original_150_minimum_and_no_reprice(amount):
    src = text(CYCLE)
    assert amount in src
    assert src.count("ge=15000") >= 2
    assert '"existing_contributions_repriced":False' in src
    assert '"real_payments_enabled":False' in src


def test_044_admin_selected_amount_without_default_100():
    sql = text(M044)
    assert "p_amount_cents NOT BETWEEN 15000 AND 1000000" in sql
    assert "p_amount_cents::numeric/100" in sql
    assert "UNIQUE(tenant_id,idempotency_key)" in sql
    assert "DEFAULT 100" not in sql


def test_legacy_15_85_reference_is_not_live_payment_execution():
    src = text(CLOSINGS)
    assert "15% taxa administrativa / 85% pool dos membros" in src
    assert "FR Finance" in src[:160]
    assert "status_code=503" in src
    assert "Fechamento indisponível" in src


@pytest.mark.parametrize("marker", [
    'db.hostname == "127.0.0.1"',
    "db.port == 5433",
    'db.path == "/frcaixinha_aistudio_dev"',
    'db.username == "frc_ai_app"',
    'db.query == ""',
    'db.fragment == ""',
    'os.getenv("FRCAIXINHA_TERMUX_LOCAL_API") == "1"',
    'os.getenv("AI_STUDIO_IN_APP_NOTIFICATIONS") == "YES"',
    'os.getenv("ENVIRONMENT","development") != "production"',
    "len(secret.encode(\"utf-8\")) >= 32",
])
def test_notifications_gate_only_original_single_database(marker):
    assert marker in text(NOTIF)


@pytest.mark.parametrize("marker", [
    '"email_delivery_active":False',
    '"push_delivery_active":False',
    '"whatsapp_delivery_active":False',
    '"schedule_approved":False',
    '"bank_reconciled":False',
])
def test_notification_capabilities_do_not_claim_real_external_delivery(marker):
    assert marker in text(NOTIF)


@pytest.mark.parametrize("marker", [
    '"pix_collection_enabled": False',
    '"pix_payout_enabled": False',
    '"real_payments_enabled": False',
    '"bank_reconciled": False',
    'or getattr(service, "verified_provisioning", False) is not True',
    'or getattr(service, "bank_settlement_authorized", False) is not True',
    'or getattr(service, "provider_account_bound", False) is not True',
])
def test_pix_is_not_enabled_by_offline_catalog_compatibility(marker):
    assert marker in text(PIX)


def test_api_health_is_existing_app_and_ready_not_production():
    src = text(HEALTH)
    assert '@app.get("/api/health")' in src
    assert '"app": "FR Finance"' in src
    assert '@app.get("/api/health/ready")' in src
    assert '"scope": "LOCAL_HOMOLOGATION_ONLY"' in src
    assert "asyncpg.connect" in src


def test_static_compatibility_is_not_live_migration_proof():
    src = text(ROOT / "backend/scripts/aistudio_m38701_local_043_044_catalog_readonly.py")
    assert "MIGRATION_PROVENANCE=NOT_ATTESTED" in src or (
        "MIGRATION_PROVENANCE" in src and "NOT_ATTESTED" in src)
