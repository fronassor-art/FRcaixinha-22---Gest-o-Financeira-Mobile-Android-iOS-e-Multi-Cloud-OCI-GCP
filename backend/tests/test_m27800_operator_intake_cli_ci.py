"""M27800: CLI only writes private, nonsecret provider metadata in HOME."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys


ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/aistudio_provider_intake.py"


def command(home, *args):
    env=os.environ.copy()
    env["HOME"]=str(home)
    env["PYTHONPATH"]=str(ROOT/"backend")
    return subprocess.run(
        [sys.executable,str(SCRIPT),*args],
        cwd=ROOT,env=env,text=True,capture_output=True,
        timeout=15,check=False,
    )


def test_private_home_manifest_and_redacted_operator_checklist(tmp_path):
    local=tmp_path/"operator"
    local.mkdir(mode=0o700)
    config=local/".config/frfinance-aistudio/provider-public-inputs.json"
    step=command(local,"init")
    assert step.returncode==0,step.stderr
    assert config.is_file()
    assert stat.S_IMODE(config.stat().st_mode)==0o600
    assert stat.S_IMODE(config.parent.stat().st_mode)==0o700
    assert command(local,"init").returncode==2
    listing=command(local,"fields")
    assert listing.returncode==0
    assert "SMTP_PASSWORD" not in listing.stdout
    assert "MP_CLIENT_SECRET" not in listing.stdout
    assert "APP_URL" in listing.stdout
    assert "MP_WEBHOOK_URL" in listing.stdout
    new=command(local,"set","APP_URL","https://app.frfinance.com.br")
    assert new.returncode==0
    assert "frfinance.com.br" not in new.stdout
    audit=command(local,"audit")
    assert audit.returncode==0,audit.stderr
    assert "FR_FINANCE_PUBLIC_INTAKE_AUDIT=PASS" in audit.stdout
    assert "FR_FINANCE_REAL_MAIL=OFF" in audit.stdout
    assert "FR_FINANCE_PIX_INBOUND=OFF" in audit.stdout
    assert "FR_FINANCE_REAL_USER_ACTIVATION=OFF" in audit.stdout
    assert "GATE_MAIL_PROVIDER=PUBLIC_FIELDS_MISSING" in audit.stdout
    assert "https://app.frfinance.com.br" not in audit.stdout
    assert "SMTP_PASSWORD" not in audit.stdout
    data=json.loads(config.read_text())
    assert data["public_inputs"]=={"APP_URL":"https://app.frfinance.com.br"}
    removed=command(local,"unset","APP_URL")
    assert removed.returncode==0
    assert json.loads(config.read_text())["public_inputs"]=={}


def test_unknown_secret_key_rejected_without_writing_its_value(tmp_path):
    root=tmp_path/"home"
    root.mkdir()
    assert command(root,"init").returncode==0
    config=root/".config/frfinance-aistudio/provider-public-inputs.json"
    before=config.read_bytes()
    token="REALLY_SENSITIVE_SIMULATED_VALUE"
    request=command(root,"set","MP_ACCESS_TOKEN",token)
    assert request.returncode==2
    assert token not in (request.stdout+request.stderr)
    assert config.read_bytes()==before
    assert command(root,"set","FR_FINANCE_PIX_REAL","true").returncode==2
    assert command(root,"set","SMTP_HOST","127.0.0.1").returncode==2
    assert config.read_bytes()==before


def test_world_readable_metadata_and_symlink_are_blocked(tmp_path):
    root=tmp_path/"home"
    root.mkdir()
    assert command(root,"init").returncode==0
    config=root/".config/frfinance-aistudio/provider-public-inputs.json"
    config.chmod(0o644)
    assert command(root,"audit").returncode==2
    config.chmod(0o600)
    config.unlink()
    target=tmp_path/"victim"
    target.write_text("UNRELATED_FILE")
    config.symlink_to(target)
    result=command(root,"set","APP_URL","https://app.frfinance.com.br")
    assert result.returncode==2
    assert target.read_text()=="UNRELATED_FILE"


def test_duplicate_json_fields_and_synthetic_secrets_blocked(tmp_path):
    root=tmp_path/"home"
    root.mkdir()
    assert command(root,"init").returncode==0
    config=root/".config/frfinance-aistudio/provider-public-inputs.json"
    config.write_text(
        '{"schema_version":1,"project":"FR_FINANCE_AI_STUDIO",'
        '"public_inputs":{"APP_URL":"https://example.com.br",'
        '"APP_URL":"https://another.com.br"}}'
    )
    config.chmod(0o600)
    assert command(root,"audit").returncode==2
    assert command(root,"set","SMTP_HOST","smtp.frfinance.com.br").returncode==2


def test_never_calls_network_or_any_database_service():
    s=SCRIPT.read_text()
    for dangerous in (
        "requests.post(", "urllib.request", "smtplib.SMTP(",
        "asyncpg.connect(", "psycopg.connect(", "oci.config.",
        "MP_ACCESS_TOKEN=", "SMTP_PASSWORD=", "FR_FINANCE_REAL_PIX=1",
    ):
        assert dangerous not in s
    assert "json.dumps(validate_manifest(data)" in s
    assert "os.O_EXCL" in s
