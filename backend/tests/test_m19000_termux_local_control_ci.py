"""M19000 Termux service must never start without authorized SHA."""
from pathlib import Path
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]

def test_termux_api_control_default_denied():
 path=ROOT/"scripts/aistudio_termux_api_control.py"
 p=subprocess.run([sys.executable,str(path),"status"],capture_output=True,text=True,timeout=10)
 assert p.returncode==2 and "BLOQUEADO" in p.stderr
 s=path.read_text()
 for key in ("AI_STUDIO_APPROVED_SHA","api.env","local_inbox_schema_verified",
             "real_payments_enabled","start_new_session=True","is_owned_uvicorn",
             "FRCAIXINHA_TEST_AUTH","127.0.0.1"):
  assert key in s,key
 assert "shell=True" not in s

def test_notification_env_upgrade_default_denied_and_secrets_private():
 path=ROOT/"scripts/aistudio_notifications_api_env_upgrade.py"
 p=subprocess.run([sys.executable,str(path)],capture_output=True,text=True,timeout=10)
 assert p.returncode==2 and "BLOQUEADO" in p.stderr
 s=path.read_text()
 for key in ("IN_APP_CURSOR_HMAC_KEY","AI_STUDIO_IN_APP_NOTIFICATIONS",
             "tempfile.NamedTemporaryFile","os.replace","0o600",
             "AI_STUDIO_APPROVED_SHA","secrets.token_urlsafe(48)"):
  assert key in s,key
