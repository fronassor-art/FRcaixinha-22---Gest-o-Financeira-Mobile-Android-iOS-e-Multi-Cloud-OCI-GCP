"""M28100 — public input priority doesn't enable or expose integrations."""
import pytest

from app.provider_setup_sequence import PHASES, OPS_PROOFS, prioritized_public_steps
from app.provider_intake_schema import FIELD_BY_KEY, new_manifest


def test_blank_input_returns_actionable_first_fields_not_fake_resources():
    report=prioritized_public_steps(new_manifest())
    assert report["project"]=="FR_FINANCE_AI_STUDIO"
    assert report["next_public_field"]=="OCI_REGION"
    assert report["remaining_public_count"]==13
    assert len(report["stages"])==4
    assert len(OPS_PROOFS)==8
    assert all(not p["operationally_verified"] for p in report["stages"])
    assert all(not p["verified"] for p in report["external_proofs"])
    assert report["all_external_gates_blocked"] is True
    assert report["credentials_required_in_chat"] is False
    assert report["real_email_enabled"] is False
    assert report["real_users_enabled"] is False
    assert report["real_pix_enabled"] is False
    names=[task["field"] for phase in report["stages"] for task in phase["missing"]]
    assert names==[name for _,fields in PHASES for name,_ in fields]
    assert set(names)==set(FIELD_BY_KEY)
    assert len(names)==13


def test_partial_public_inputs_skip_completed_without_changing_external_proofs():
    config=new_manifest()
    config["public_inputs"]["OCI_REGION"]="sa-saopaulo-1"
    config["public_inputs"]["MP_APPLICATION_ID"]="1234567"
    report=prioritized_public_steps(config)
    assert report["remaining_public_count"]==11
    assert report["next_public_field"]=="APP_URL"
    assert report["stages"][0]["status"]=="PUBLIC_FIELDS_COMPLETE_NOT_VERIFIED"
    assert all(not proof["verified"] for proof in report["external_proofs"])


def test_full_public_input_contract_does_not_mark_integration_live():
    config=new_manifest()
    config["public_inputs"]={
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
    result=prioritized_public_steps(config)
    assert result["next_public_field"] is None
    assert result["remaining_public_count"]==0
    assert all(stage["status"]=="PUBLIC_FIELDS_COMPLETE_NOT_VERIFIED" for stage in result["stages"])
    assert all(not gate["verified"] for gate in result["external_proofs"])
    assert result["all_external_gates_blocked"]
    assert result["real_pix_enabled"] is False
    assert result["real_email_enabled"] is False
    assert result["real_users_enabled"] is False
    for value in config["public_inputs"].values():
        assert value not in str(result)


def test_operator_cli_priority_is_readonly_even_on_empty_manifest(tmp_path):
    import subprocess
    import sys
    import os
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    env=os.environ.copy()
    env.update({"HOME":str(tmp_path),"PYTHONPATH":str(root/"backend")})
    cmd=[sys.executable,str(root/"backend/scripts/aistudio_provider_intake.py")]
    init=subprocess.run([*cmd,"init"],env=env,capture_output=True,text=True,check=False)
    assert init.returncode==0, init.stderr
    nxt=subprocess.run([*cmd,"next"],env=env,capture_output=True,text=True,check=False)
    assert nxt.returncode==0,nxt.stderr
    assert "NEXT_PUBLIC_FIELD=OCI_REGION" in nxt.stdout
    assert "FR_FINANCE_LIVE_SERVICES=OFF" in nxt.stdout
    assert "OCI_REGION" in nxt.stdout
    assert "MP_APPLICATION_ID" in nxt.stdout
    assert "SMTP_PASSWORD" not in nxt.stdout
    assert "MP_CLIENT_SECRET" not in nxt.stdout


@pytest.mark.parametrize("tamper",[
    {"project":"OTHER","schema_version":1,"public_inputs":{}},
    {"project":"FR_FINANCE_AI_STUDIO","schema_version":1,"public_inputs":{"SMTP_PASSWORD":"sensitive"}},
])
def test_unknown_projects_and_sensitive_fields_rejected(tamper):
    from app.provider_intake_schema import IntakeBlocked
    with pytest.raises(IntakeBlocked):
        prioritized_public_steps(tamper)
