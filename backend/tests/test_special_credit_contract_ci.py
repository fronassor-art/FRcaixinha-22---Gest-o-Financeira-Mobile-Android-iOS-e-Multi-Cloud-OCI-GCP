"""M39014 — Crédito Especial/Extraordinário, zero external delivery.

Only pure logic; does not contact a database, financial provider or channel.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from backend.app.special_credit_contract import (
    SpecialCreditDenied, amount_brl, validate_exception,
    request_is_permitted, channel_permissions, public_push_preview,
    external_dispatch_allowed,
)
from backend.app.special_credit_channels import (
    brevo_email_envelope, brevo_sms_marketing_envelope,
    whatsapp_template_envelope, push_fcm_envelope, provider_dispatch,
)

NOW = datetime(2026,11,11,12,tzinfo=timezone.utc)
TOMORROW = NOW+timedelta(days=1)


@pytest.mark.parametrize("invalid", [0,-1,"NaN","Infinity",float("nan"),1.5,False,None,"0.009"])
def test_amount_rejects_non_exact_or_invalid(invalid):
    with pytest.raises(SpecialCreditDenied):
        amount_brl(invalid)


def test_approved_amount_is_exact_brl():
    assert amount_brl("5000.00") == Decimal("5000.00")


def test_exception_rejects_cross_tenant():
    with pytest.raises(SpecialCreditDenied):
        validate_exception(tenant_id="box1",member_tenant_id="box2",
            member_status="ATIVA",cycle_status="ABERTO",
            amount="5000.00",expires_at=TOMORROW,
            reason="Avaliação documentada do risco.",now=NOW)


def test_expired_or_no_longer_active():
    params=dict(grant_status="ACTIVE",valid_until=TOMORROW,
       requested="500.00",granted_limit="5000.00",member_active=True,cycle_open=True,now=NOW)
    assert request_is_permitted(**params)
    assert not request_is_permitted(**{**params,"now":TOMORROW})
    assert not request_is_permitted(**{**params,"grant_status":"REVOKED"})
    assert not request_is_permitted(**{**params,"member_active":False})
    assert not request_is_permitted(**{**params,"cycle_open":False})
    assert not request_is_permitted(**{**params,"requested":"5000.01"})


def test_marketing_is_default_denied():
    assert channel_permissions([]) == {
      "PUSH":False,"EMAIL":False,"WHATSAPP":False,"SMS":False}
    # Consent alone is NOT a provider/identity verification.
    assert not any(channel_permissions(["PUSH","EMAIL"]).values())
    assert channel_permissions(["PUSH"],verified=["PUSH"])["PUSH"]


def test_locked_screen_excludes_amount_and_loan():
    msg=public_push_preview()
    assert "5000" not in str(msg)
    assert "empréstimo" not in str(msg).lower()


def test_external_is_never_enabled_from_ci_only():
    params=dict(feature_enabled=True,production=False,
      authorization_real=True,provider_verified=True,channel_opt_in=True)
    assert not external_dispatch_allowed(**params)
    assert not external_dispatch_allowed(**{**params,"production":True,"channel_opt_in":False})


def test_push_fcm_envelope_not_sent():
    envelope=push_fcm_envelope(project_id="fr-finance-prod",
                               device_token="abc:def456ghi789jkl012mno")
    assert envelope.url.startswith("https://fcm.googleapis.com/")
    assert envelope.real_send_enabled is False
    assert envelope.body["message"]["data"]["destination"]=="minhas-oportunidades"


def test_brevo_email_marketing_requires_unsubscribe():
    msg=brevo_email_envelope(
        verified_sender="contato@frfinance.com.br",
        recipient="member@example.com",
        unsubscribe_url="https://frfinance.com.br/optout/test")
    assert msg.channel=="EMAIL" and not msg.real_send_enabled
    with pytest.raises(SpecialCreditDenied):
        brevo_email_envelope(verified_sender="contato@frfinance.com.br",
            recipient="member@example.com",unsubscribe_url="http://unsafe.test")


def test_sms_is_marketing_not_transactional():
    envelope=brevo_sms_marketing_envelope(
        sender="FRFinance",e164_digits="5591999999999",
        content="Nova oportunidade no aplicativo FR Finance.")
    assert envelope.body["type"]=="marketing"
    assert envelope.real_send_enabled is False
    with pytest.raises(SpecialCreditDenied):
        brevo_sms_marketing_envelope(sender="FRFinance",
            e164_digits="5591999999999",content="Seu crédito foi liberado!")


def test_whatsapp_must_use_preapproved_template_name():
    msg=whatsapp_template_envelope(phone_number_id="12345678901",
       e164_digits="5591999999999",approved_template="fr_credito_especial")
    assert msg.body["type"]=="template"
    assert not msg.real_send_enabled
    with pytest.raises(SpecialCreditDenied):
        whatsapp_template_envelope(phone_number_id="12345678901",
           e164_digits="5591999999999",approved_template="../freeform")


def test_no_network_dispatch_function():
    with pytest.raises(SpecialCreditDenied):
        provider_dispatch()


def test_master_contracts_have_new_annex_without_clobbering_history():
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    contract=(root/"docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md").read_text(encoding="utf-8")
    notebook=(root/"docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md").read_text(encoding="utf-8")
    annex=(root/"docs/FR_FINANCE_CREDITO_ESPECIAL_EXTRAORDINARIO_M39010.md").read_text(encoding="utf-8")
    assert "CTM-CRED-EX-01" in contract and "CTM-CRED-EX-06" in contract
    assert "CM-CRED-EX-01" in notebook and "CM-EX-12" in notebook
    assert "Cláusula 4.2" not in contract or "Origem histórica" in contract
    for channel in ("push", "e-mail", "WhatsApp", "SMS"):
        assert channel.lower() in annex.lower()
    assert "NÃO AUTORIZADOS" in annex
    assert "FRcaixinha 2.2" in annex
