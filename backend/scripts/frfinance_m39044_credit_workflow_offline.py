#!/usr/bin/env python3
"""FR Finance M39044 — fluxo administrador/membro OFFLINE e 100% sintético.

Executa o roteador FastAPI REAL contra o fake RLS já versionado em M39033.
Não abre porta, não conecta ao PostgreSQL ORIGINAL, não cria membros,
empréstimos, pagamentos, campanhas reais, notificações ou Pix.
Termux: python -B -m backend.scripts.frfinance_m39044_credit_workflow_offline
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

from backend.app.routers import special_credit as routes
from backend.tests.test_m39033_special_credit_route_flow_ci import (
    SyntheticRlsDb, make_client, TENANT, OTHER_TENANT,
    ADMIN, MEMBER_USER, MEMBERSHIP, GRANT, CAMPAIGN, RECIPIENT, PATH,
)

OTHER_MEMBER = UUID("33333333-3333-4333-8333-333333333333")
SANDBOX_DSN = "postgresql://frc_ai_app@127.0.0.1:5433/frcaixinha_aistudio_dev"


def _require(response, code: int, label: str):
    if response.status_code != code:
        raise AssertionError(f"{label}: expected HTTP {code}, got {response.status_code}")
    return response.json()


def run_scenario() -> None:
    # Allow local execution only from the single canonical Termux checkout.
    # GitHub CI runs in a disposable runner, with NO connection to Termux PG18.
    if os.getenv("GITHUB_ACTIONS") != "true":
        original = Path("/data/data/com.termux/files/home/fr-finance")
        if Path.cwd().resolve() != original or not (original / ".git").is_dir():
            raise RuntimeError("M39044_ONLY_ORIGINAL_TERMUX_DIRECTORY")
        if os.getenv("HOME") != "/data/data/com.termux/files/home":
            raise RuntimeError("M39044_TERMUX_NATIVE_REQUIRED")

    env = {
        "ENVIRONMENT": "development",
        "FRCAIXINHA_TEST_AUTH": "1",
        "FR_FINANCE_SPECIAL_CREDIT_SANDBOX": "YES",
        "FR_FINANCE_PIX_REAL": "OFF",
    }
    print("=== FR FINANCE M39044 — CREDITO ESPECIAL API OFFLINE ===")
    print("M39044_DATABASE=IN_MEMORY_FAKE_ONLY")
    print("M39044_SOCKETS=NONE")
    with patch.dict(os.environ, env), patch.object(
        routes, "settings", SimpleNamespace(DATABASE_URL=SANDBOX_DSN)
    ):
        state = SyntheticRlsDb()
        with (
            make_client(state, "TENANT_ADMIN", ADMIN) as admin,
            make_client(state, "TENANT_MEMBER", MEMBER_USER) as member,
            make_client(state, "TENANT_MEMBER", OTHER_MEMBER) as intruder,
            make_client(state, "TENANT_MEMBER", MEMBER_USER, OTHER_TENANT) as wrong_tenant,
        ):
            expiration_grant = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
            expiration_campaign = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
            grant = {
                "member_ids": [str(MEMBERSHIP)],
                "ceiling_brl": "5000.00",
                "expires_at": expiration_grant,
                "reason": "Justificativa de risco estritamente simulada M39044.",
                "request_id": "00000000-0000-4000-8000-000000000044",
            }
            _require(member.post(PATH + "/grants", json=grant), 403, "member_cannot_grant")
            _require(wrong_tenant.get(PATH + "/opportunities"), 403, "wrong_tenant")
            assert state.statements == [], "Acesso proibido consultou a conexão sintética"
            print("M39044_RBAC_AND_TENANT=PASS")

            created = _require(admin.post(PATH + "/grants", json=grant), 200, "admin_grant")
            assert created["grants"][0]["grant_id"] == str(GRANT)
            assert created["real_credit_enabled"] is False
            replay = _require(admin.post(PATH + "/grants", json=grant), 200, "grant_replay")
            assert replay["grants"][0]["grant_id"] == str(GRANT)
            altered = {**grant, "ceiling_brl": "6000.00"}
            _require(admin.post(PATH + "/grants", json=altered), 409, "grant_conflicting_id")
            assert sum(e[4] == "GRANT_CREATED" for e in state.audit) == 1
            print("M39044_GRANT_IDEMPOTENCY=PASS")

            campaign = {
                "grant_ids": [str(GRANT)],
                "title": "Simulacao privada M39044",
                "body": "Convite para conhecer uma oportunidade demonstrativa sem credito real.",
                "expires_at": expiration_campaign,
                "request_id": "00000000-0000-4000-8000-000000000045",
            }
            created_campaign = _require(
                admin.post(PATH + "/campaigns", json=campaign), 200, "campaign_draft"
            )
            assert created_campaign["id"] == str(CAMPAIGN)
            assert created_campaign["status"] == "DRAFT"
            repeat = _require(admin.post(PATH + "/campaigns", json=campaign), 200, "campaign_replay")
            assert repeat["created"] is False
            altered_campaign = {**campaign, "body": "Outra mensagem demonstrativa com mesmo request_id."}
            _require(admin.post(PATH + "/campaigns", json=altered_campaign),
                     409, "campaign_conflicting_id")
            print("M39044_CAMPAIGN_DRAFT_AND_IDEMPOTENCY=PASS")

            # Opt-in is a local preference; the outbox is ONLY a blocked record,
            # never transport through FCM, Brevo, WhatsApp, SMS or internet.
            pref = _require(member.post(PATH + "/preferences",
                         json={"channel": "PUSH", "opted_in": True}), 200, "push_optin")
            assert pref == {"channel": "PUSH", "opted_in": True, "external_dispatch": False}
            publish = _require(admin.post(PATH + f"/campaigns/{CAMPAIGN}/publish"),
                               200, "publish_in_app")
            assert publish == {"status": "PUBLISHED", "in_app": True, "external_dispatch": False}
            assert state.outbox == [{"channel": "PUSH", "state": "BLOCKED_EXTERNAL"}]
            _require(admin.post(PATH + f"/campaigns/{CAMPAIGN}/publish"),
                     200, "publish_replay")
            assert len(state.outbox) == 1, "Republicação duplicou outbox"
            print("M39044_IN_APP_PUBLISH_ONLY=PASS")
            print("M39044_OUTBOX_BLOCKED_EXTERNAL=PASS")

            visible = _require(member.get(PATH + "/opportunities"), 200, "member_list")
            assert len(visible) == 1
            assert visible[0]["recipient_id"] == str(RECIPIENT)
            assert visible[0]["ceiling_brl"] == "5000.00"
            assert _require(intruder.get(PATH + "/opportunities"), 200, "other_member_list") == []
            _require(intruder.post(PATH + f"/opportunities/{RECIPIENT}/reply",
                                 json={"status": "INTERESTED"}), 409, "other_member_reply")
            assert state.recipient["response_status"] == "PENDING"
            response = _require(member.post(PATH + f"/opportunities/{RECIPIENT}/reply",
                                json={"status": "INTERESTED"}), 200, "member_reply")
            assert response == {"status": "INTERESTED", "loan_created": False}
            _require(member.post(PATH + f"/opportunities/{RECIPIENT}/reply",
                                 json={"status": "DECLINED"}), 409, "double_reply")
            print("M39044_MEMBER_ISOLATION_AND_SINGLE_REPLY=PASS")

            optout = _require(member.post(PATH + "/preferences",
                           json={"channel": "PUSH", "opted_in": False}), 200, "push_optout")
            assert optout["opted_in"] is False and optout["external_dispatch"] is False
            prefs = _require(member.get(PATH + "/preferences"), 200, "prefs")
            assert prefs["preferences"]["PUSH"] is False
            assert prefs["external_dispatch"] is False
            assert all(item["state"] == "BLOCKED_EXTERNAL" for item in state.outbox)
            print("M39044_MEMBER_OPT_OUT=PASS")

            assert sum(e[4] == "CAMPAIGN_PUBLISHED_IN_APP" for e in state.audit) == 1
            assert sum(e[4] == "OPPORTUNITY_INTERESTED" for e in state.audit) == 1
            for sql in state.statements:
                low = sql.lower()
                assert "public.loans" not in low and "pix" not in low
            # Feature turned OFF immediately: admin cannot mutate despite session.
            os.environ["FR_FINANCE_SPECIAL_CREDIT_SANDBOX"] = "NO"
            _require(admin.post(PATH + "/grants", json=grant), 503, "sandbox_off")
            print("M39044_SANDBOX_OFF_DENIES_WRITES=PASS")

    print("M39044_POSTGRESQL_ORIGINAL=NOT_CONNECTED")
    print("M39044_DATABASE_WRITES=NONE")
    print("M39044_EXTERNAL_DELIVERY=OFF")
    print("M39044_PIX_REAL=OFF")
    print("M39044_STATUS=PASS")


if __name__ == "__main__":
    run_scenario()
