"""M28300: operator can see secret aliases, never values or live privileges."""
import os
from pathlib import Path
import subprocess
import sys

from app.provider_secret_inventory import (
    REQUIREMENTS, AUTHORIZATION_GATES, secret_names_and_access_plan,
)


def test_secret_names_are_purpose_scoped_and_operationally_blocked():
    report=secret_names_and_access_plan()
    assert report["project"]=="FR_FINANCE_AI_STUDIO"
    assert report["mode"]=="READ_ONLY_NO_CREDS_OR_DEPLOYMENT"
    assert report["secrets_collected"] is False
    assert report["secrets_exist_in_vault_verified"] is False
    assert report["credentials_present_in_chat"] is False
    assert report["secret_values"] is None
    assert len(REQUIREMENTS)>=12
    aliases=[row["alias"] for row in report["secret_requirements"]]
    assert len(aliases)==len(set(aliases))
    assert "MP_CLIENT_SECRET" in aliases
    assert "MP_WEBHOOK_SECRET" in aliases
    assert "MP_SELLER_REFRESH_TOKEN" in aliases
    assert "SMTP_PASSWORD" in aliases
    assert "ENVELOPE_AES_KEY" in aliases
    assert "RECIPIENT_INDEX_HMAC_KEY" in aliases
    assert "PG_APP_PASSWORD" in aliases
    assert "PG_AUTH_PASSWORD" in aliases
    assert "PG_VERIFIER_PASSWORD" in aliases
    assert all(row["state"]=="NOT_ATTESTED" for row in report["secret_requirements"])
    assert all(row["storage"].startswith("OCI_VAULT") for row in report["secret_requirements"])
    assert all(not gate["approved"] and not gate["evidence_recorded"]
               for gate in report["approval_gates"])
    assert len(AUTHORIZATION_GATES)==len(report["approval_gates"])
    assert report["send_email"] is False
    assert report["activate_user"] is False
    assert report["pix_collection"] is False
    assert report["pix_payout"] is False


def test_cryptographic_secrets_cannot_be_reused_between_roles():
    by_name={item.alias:item for item in REQUIREMENTS}
    assert by_name["ENVELOPE_AES_KEY"].owner != by_name["RECIPIENT_INDEX_HMAC_KEY"].owner
    assert by_name["ENVELOPE_AES_KEY"].isolation=="TENANT_BOUND"
    assert by_name["RECIPIENT_INDEX_HMAC_KEY"].isolation=="TENANT_BOUND"
    assert by_name["MP_CLIENT_SECRET"].owner != by_name["MP_WEBHOOK_SECRET"].owner
    assert by_name["PG_APP_PASSWORD"].owner != by_name["PG_AUTH_PASSWORD"].owner
    assert by_name["PG_AUTH_PASSWORD"].owner != by_name["PG_VERIFIER_PASSWORD"].owner


def test_cli_can_print_secret_aliases_without_opening_private_file(tmp_path):
    root=Path(__file__).resolve().parents[2]
    env=os.environ.copy()
    env["HOME"]=str(tmp_path)
    env["PYTHONPATH"]=str(root/"backend")
    result=subprocess.run(
        [sys.executable,str(root/"backend/scripts/aistudio_provider_intake.py"),
         "secrets-plan"],
        env=env,cwd=root,text=True,capture_output=True,timeout=15,check=False,
    )
    assert result.returncode==0,result.stderr
    assert "FR_FINANCE_SECRETS_STATUS=NOT_ATTESTED" in result.stdout
    assert "FR_FINANCE_LIVE_SERVICES=OFF" in result.stdout
    assert "SMTP_PASSWORD | OCI_VAULT" in result.stdout
    assert "MP_CLIENT_SECRET | OCI_VAULT" in result.stdout
    assert "PG_VERIFIER_PASSWORD | OCI_VAULT" in result.stdout
    assert not (tmp_path/".config/frfinance-aistudio/provider-public-inputs.json").exists()


def test_no_network_or_credential_material_in_inventory():
    root=Path(__file__).resolve().parents[2]
    s=(root/"backend/app/provider_secret_inventory.py").read_text()
    for prohibited in (
        "get_secret_bundle(", "os.environ", "os.getenv", "SMTP(", "smtplib",
        "httpx.", "requests.", "asyncpg.connect", "psycopg.connect",
        "INSERT INTO", "UPDATE public.", "private_key=", "api_key=",
    ):
        assert prohibited not in s
