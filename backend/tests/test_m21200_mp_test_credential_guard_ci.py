"""M21200: only encrypted, locally scoped test credentials; never real payment."""
import importlib.util
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/aistudio_mp_credentials_local.py"

def load():
    spec=importlib.util.spec_from_file_location("mp_test_setup",SCRIPT)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_client_id_and_test_token_validation():
    mod=load()
    assert mod.valid_app_id("123456789")
    assert not mod.valid_app_id("123 ABC")
    assert not mod.valid_app_id("")
    assert mod.valid_test_token("APP_USR-"+"A"*36)
    for x in ["TOKEN", "APP_USR-", "APP_USR-a token", "TEST-1234", "APP_USR-"+"A"*2100]:
        assert not mod.valid_test_token(x)

def test_preflight_never_calls_provider_or_enables_money():
    s=SCRIPT.read_text()
    for key in ("age", "--passphrase","--decrypt",
     "AI_STUDIO_APPROVED_SHA", "ENCRYPTED_AND_RECOVERY_CHECKED",
     "REAL_PIX_COLLECTION_ACTIVE","REAL_PIX_PAYOUT_ACTIVE","getpass.getpass"):
        assert key in s
    for forbidden in ("api.mercadopago.com", "requests.post(", "httpx.post(",
       "INSERT INTO", "production_token", "REAL_PIX_COLLECTION_ACTIVE=YES"):
        assert forbidden not in s
    compiled=subprocess.run(["python","-m","py_compile",str(SCRIPT)],capture_output=True,text=True)
    assert compiled.returncode==0,compiled.stderr
