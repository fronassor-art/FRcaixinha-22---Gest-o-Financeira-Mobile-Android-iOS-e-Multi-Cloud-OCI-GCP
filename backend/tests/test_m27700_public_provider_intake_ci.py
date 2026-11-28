"""M27700: public provider input is syntactic and never production proof."""
from pathlib import Path
import pytest

from app.provider_intake_schema import (
    FIELDS, GATE_FIELDS, IntakeBlocked,
    validate_field, validate_manifest, new_manifest, intake_audit,
)


EXAMPLE = {
    "APP_URL":"https://app.frfinance.com.br",
    "OCI_REGION":"sa-saopaulo-1",
    "OCI_COMPARTMENT_OCID":"ocid1.compartment.oc1.."+"a"*32,
    "OCI_INSTANCE_OCID":"ocid1.instance.oc1.sa-saopaulo-1."+"b"*32,
    "OCI_VAULT_OCID":"ocid1.vault.oc1.sa-saopaulo-1."+"c"*32,
    "OCI_DATABASE_HOST":"db.frfinance.com.br",
    "SMTP_HOST":"smtp.frfinance.com.br",
    "SMTP_PORT":"587",
    "SMTP_USER":"sender@frfinance.com.br",
    "FR_FINANCE_EMAIL_FROM":"contato@frfinance.com.br",
    "MP_APPLICATION_ID":"1234567891234",
    "MP_OAUTH_REDIRECT_URI":"https://api.frfinance.com.br/api/v1/mp/oauth/callback",
    "MP_WEBHOOK_URL":"https://api.frfinance.com.br/api/v1/mp/webhooks",
}


def test_all_fields_are_public_and_schema_stable():
    assert len(FIELDS)==13
    assert len({f.key for f in FIELDS})==len(FIELDS)
    assert new_manifest()=={
        "schema_version":1,"project":"FR_FINANCE_AI_STUDIO","public_inputs":{}
    }
    report=intake_audit(new_manifest())
    assert report["status"]=="BLOCKED_EXTERNAL_EVIDENCE"
    assert all(not x["public_fields_complete"] for x in report["gates"])
    assert all(not x["enabled"] for x in report["gates"])
    for key in ("email_real_active","user_activation_active",
                "pix_inbound_active","pix_outbound_active",
                "provider_credentials_stored","writes_performed"):
        assert report[key] is False


@pytest.mark.parametrize("key,value",list(EXAMPLE.items()))
def test_valid_public_metadata_accepted(key,value):
    assert validate_field(key,value)==value


def test_complete_public_metadata_still_cannot_activate_any_provider():
    config=new_manifest()
    config["public_inputs"].update(EXAMPLE)
    result=intake_audit(config)
    assert not result["public_fields_absent"]
    assert all(gate["public_fields_complete"] for gate in result["gates"])
    assert all(gate["status"]=="PROVIDER_ATTESTATION_REQUIRED" for gate in result["gates"])
    assert all(not gate["operationally_verified"] and not gate["enabled"]
               for gate in result["gates"])
    assert result["status"]=="BLOCKED_EXTERNAL_EVIDENCE"
    assert set(GATE_FIELDS)=={g["gate"] for g in result["gates"]}
    assert "secret" not in str(result).lower() or "provider_credentials_stored" in result


@pytest.mark.parametrize("name",[
    "SMTP_PASSWORD","MP_CLIENT_SECRET","MP_ACCESS_TOKEN","MP_REFRESH_TOKEN",
    "MP_WEBHOOK_SECRET","AUTH_SECRET","DATABASE_URL","OCI_API_PRIVATE_KEY",
    "FR_FINANCE_PIX_REAL","FR_FINANCE_REAL_EMAIL_SEND","MP_PSP_TRANSFER_ENABLED",
    "VITE_MP_ACCESS_TOKEN",
])
def test_secret_and_activation_names_are_never_input_fields(name):
    with pytest.raises(IntakeBlocked):
        validate_field(name,"sensitive-value-not-to-be-stored")


@pytest.mark.parametrize("key,value",[
    ("APP_URL","http://app.frfinance.com.br"),
    ("APP_URL","https://127.0.0.1"),
    ("APP_URL","https://app.frfinance.com.br@127.0.0.1"),
    ("APP_URL","https://app.frfinance.com.br/path?token=abc"),
    ("OCI_REGION","not region"),
    ("OCI_DATABASE_HOST","127.0.0.1"),
    ("OCI_DATABASE_HOST","localhost"),
    ("OCI_DATABASE_HOST","internal.local"),
    ("SMTP_PORT","25"),
    ("SMTP_PORT","465"),
    ("SMTP_HOST","smtp.local"),
    ("SMTP_HOST","127.0.0.1"),
    ("SMTP_USER","secret token with spaces"),
    ("FR_FINANCE_EMAIL_FROM","name@example.com\r\nBcc:attacker@ex.com"),
    ("MP_APPLICATION_ID","APP_USR-SECRET"),
    ("MP_APPLICATION_ID","abc123"),
    ("MP_OAUTH_REDIRECT_URI","http://api.frfinance.com.br/oauth"),
    ("MP_OAUTH_REDIRECT_URI","https://api.frfinance.com.br/oauth?token=abc"),
    ("MP_WEBHOOK_URL","https://api.frfinance.com.br/webhook?secret=abc"),
    ("MP_WEBHOOK_URL","https://127.0.0.1:8080/webhook"),
    ("MP_WEBHOOK_URL","https://api.frfinance.com.br"),
])
def test_invalid_or_potentially_secret_inputs_fail_closed(key,value):
    with pytest.raises(IntakeBlocked):
        validate_field(key,value)


@pytest.mark.parametrize("invalid",[
    None,[],{},
    {"project":"FR_FINANCE_AI_STUDIO","schema_version":2,"public_inputs":{}},
    {"project":"FR_FINANCE_AI_STUDIO","schema_version":True,"public_inputs":{}},
    {"project":"SOME_OTHER_PROJECT","schema_version":1,"public_inputs":{}},
    {"project":"FR_FINANCE_AI_STUDIO","schema_version":1,"public_inputs":{"SMTP_PASSWORD":"abc"}},
])
def test_invalid_schema_and_unknown_values_rejected(invalid):
    with pytest.raises(IntakeBlocked):
        validate_manifest(invalid)


def test_no_network_or_bank_money_switches_in_intake():
    root=Path(__file__).resolve().parents[2]
    content=(root/"backend/app/provider_intake_schema.py").read_text()
    for forbidden in (
        "requests.", "httpx.", "smtplib", "oci.config", "asyncpg.connect(",
        "INSERT INTO ", "UPDATE public.", "account_activated=True",
        "pix_inbound_active\":True", "email_real_active\":True",
        "os.environ", "os.getenv",
    ):
        assert forbidden not in content
