"""M27900/M28000 — operator tasks cannot be promoted to live grants."""
from pathlib import Path

from app.operator_release_worklist import (
    OFF_FLAGS, PROVIDER_TASKS, SENSITIVE_ITEMS, release_worklist,
)
from app.provider_intake_schema import FIELDS, GATE_FIELDS, new_manifest


def test_blank_operator_worklist_assigns_public_and_external_tasks():
    report=release_worklist(new_manifest())
    assert report["project"]=="FR_FINANCE_AI_STUDIO"
    assert report["mode"]=="OPERATOR_WORKLIST_NO_ACTIVATION"
    assert report["overall_status"]=="EXTERNAL_ATTESTATION_AND_SECURITY_APPROVAL_REQUIRED"
    assert report["secrets_collected"] is False
    assert report["enables_any_action"] is False
    assert report["public_fields_complete"] is False
    assert report["live_state"]==OFF_FLAGS
    assert len(report["stages"])==len(GATE_FIELDS)
    for gate in report["stages"]:
        assert gate["status"]=="PUBLIC_FIELDS_MISSING"
        assert gate["public_fields_missing"]
        assert gate["provider_test_approved"] is False
        assert gate["live_provider_authorized"] is False
        assert all(item["state"]=="PENDING_EXTERNAL_EVIDENCE" for item in gate["actions"])
        assert {t["responsible"] for t in gate["actions"]} <= {"OPERATOR","DEVELOPER"}


def test_vendors_require_untrusted_external_authorization():
    assert set(GATE_FIELDS)==set(PROVIDER_TASKS)
    for topic in ("OCI_HOSTING","OCI_VAULT_IAM","MAIL_PROVIDER","USER_ACTIVATION",
                  "MP_CONNECT","PIX_INBOUND","PIX_OUTBOUND"):
        assert topic in PROVIDER_TASKS
        assert len(PROVIDER_TASKS[topic])>=2
    assert any("Payouts" in action for _,action in PROVIDER_TASKS["PIX_OUTBOUND"])
    assert any("PKCE" in action for _,action in PROVIDER_TASKS["MP_CONNECT"])
    assert any("SPF" in action for _,action in PROVIDER_TASKS["MAIL_PROVIDER"])
    assert any("MFA" in action for _,action in PROVIDER_TASKS["USER_ACTIVATION"])
    assert any("RLS" in action for _,action in PROVIDER_TASKS["OCI_HOSTING"])


def test_even_fake_complete_manifest_never_activates_mail_account_or_money():
    manifest=new_manifest()
    # Use the type-specific inputs validated in the previous security suite.
    manifest["public_inputs"]={
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
    report=release_worklist(manifest)
    assert report["public_fields_complete"] is True
    assert len(report["stages"])==len(GATE_FIELDS)
    assert all(item["status"]=="PROVIDER_ATTESTATION_REQUIRED" for item in report["stages"])
    assert all(item["public_fields_missing"]==[] for item in report["stages"])
    assert all(v is False for v in report["live_state"].values())
    assert report["enables_any_action"] is False
    for value in manifest["public_inputs"].values():
        assert value not in str(report)
    assert set(SENSITIVE_ITEMS)==set(report["required_secret_names_only"])
    assert "MP_SELLER_ACCESS_TOKEN" in report["required_secret_names_only"]


def test_no_network_database_or_secret_source_in_worklist():
    root=Path(__file__).resolve().parents[2]
    source=(root/"backend/app/operator_release_worklist.py").read_text()
    for bad in (
        "os.getenv", "os.environ", "smtplib", "oci.config",
        "requests.", "httpx.", "psycopg.connect", "asyncpg.connect",
        "UPDATE public.", "INSERT INTO ", "live_state=True",
        "money_movement_enabled=True",
    ):
        assert bad not in source
    assert len(FIELDS)>=13
