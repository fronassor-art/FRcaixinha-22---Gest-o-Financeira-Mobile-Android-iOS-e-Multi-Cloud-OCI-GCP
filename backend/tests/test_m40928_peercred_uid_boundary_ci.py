"""M40928 Linux UID + SO_PEERCRED CI policy. No local DB connections."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
WORKER=ROOT/"backend/tests/m40928_guardian_peercred_worker_disposable.py"
ORCHESTRATOR=ROOT/"backend/tests/m40928_peercred_uid_boundary_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40928-peercred-uid-boundary-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40928_PEERCRED_UID_BOUNDARY_NO_GO.md"
W=WORKER.read_text(encoding="utf-8")
S=ORCHESTRATOR.read_text(encoding="utf-8")

@pytest.mark.parametrize("script", [WORKER,ORCHESTRATOR])
def test_scripts_refuse_termux_or_non_ci_use(script):
    result=subprocess.run(
        [sys.executable,"-B",str(script)],
        env={"PATH":os.environ.get("PATH","")},
        text=True,capture_output=True,timeout=15,
    )
    assert result.returncode==2
    assert "M40928_" in result.stdout
    assert "ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in result.stdout

@pytest.mark.parametrize("marker",[
    "CI_M40928_GUARDIAN_ONLY",
    "CI_M40928_GUARDIAN_DSN",
    "CI_M40928_PUBLIC_REGISTRY",
    "CI_M40928_AUTHORIZED_UID",
    "CI_M40928_ISSUER_DSN",
    "CI_M40928_APP_DSN",
    "CI_PROMOTIONS_DATABASE_URL",
    "GITHUB_ACTIONS",
    "FRCAIXINHA_CI_ISOLATED",
    "socket.SO_PEERCRED",
    "struct.unpack(\"3i\",cred)",
    "peer_uid!=int(",
    "M40928_PEERCRED_UNAUTHORIZED_UID=DENIED",
    "M40928_UID_SEPARATION_REQUIRED",
    "M40928_CONFIG_OWNER_MODE_DENIED",
    "os.O_NOFOLLOW",
    "stat.S_IMODE(state.st_mode)!=0o600",
    "M40928_LINUX_PEERCRED_REQUIRED",
    "M40928_GUARDIAN_PUBLIC_KEYS_ONLY=PASS",
    "M40928_GUARDIAN_HAS_NO_ROOT_ISSUER_APP_DSN=PASS",
    "os.chmod(path,0o666)",
    "m40926.seals",
])
def test_worker_enforces_identity_and_tight_config(marker):
    assert marker in W

@pytest.mark.parametrize("marker",[
    "CI_M40928_DISPOSABLE",
    "from m40926_dual_custody_master_disposable import require_disposable",
    "CI_M40928_GUARDIAN_UID",
    "gateway_uid=os.geteuid()",
    "gateway_uid!=guardian_uid",
    "os.chmod(config_path,0o600)",
    "sudo","frf_m40928_guardian",
    '"/usr/bin/env","-i"',
    "M40928_CONFIG_GUARDIAN_OWNER_MODE_0600=PASS",
    "M40928_DIFFERENT_OS_UID=PASS",
    "M40928_UNAUTHORIZED_UID_DENIED_BY_SO_PEERCRED=PASS",
    '"sudo","-n","-u","nobody"',
    "M40928_GUARDIAN_SEPARATE_OS_PROCESS=PASS",
    "M40928_GATEWAY_NO_GUARDIAN_DSN=PASS_FIXTURE",
    "M40928_STOLEN_APP_ISSUER_MASTER_WITHOUT_SIGNED_SEAL=DENIED",
    "M40928_GUARDIAN_PROCESS_NONCE_ONE_OF_SIX=PASS",
    "M40928_REVOKED_MASTER=DENIED",
    "M40928_ASGI_SIGNED_DRAFT_PUBLISH_CANCEL=PASS",
    "M40928_GUARDIAN_UNAVAILABLE=FAIL_CLOSED_503",
    "M40928_STOLEN_ALL_THREE_SQL_LOGINS=NO_GO_BYPASS",
    "M40928_SAME_GATEWAY_UID_SOCKET_ACCESS=NOT_REMEDIATED_NO_GO",
])
def test_gateway_uid_probe_and_adversarial_proofs(marker):
    assert marker in S

@pytest.mark.parametrize("forbidden",[
    "127.0.0.1:5433","pg_ctl","pg_dump","pg_restore",
    "ALTER ROLE frc_ai_owner","backend/migrations/114",
    "PIX_REAL=ON","PAGAMENTOS_REAIS=ON","ATIVACAO_REAL=ON",
])
def test_scripts_never_target_original_database(forbidden):
    assert forbidden not in W and forbidden not in S

def test_guardian_dsn_never_enters_child_cli_or_env():
    block=S.split("proc=subprocess.Popen(",1)[1].split("\n        )",1)[0]
    assert "config_path" in block
    assert "guardian_dsn" not in block
    assert "issuer_dsn" not in block
    assert "app_dsn" not in block
    assert "CI_PROMOTIONS_DATABASE_URL" not in block
    assert "CI_M40928_PUBLIC_REGISTRY" not in block
    assert "PYTHONDONTWRITEBYTECODE=1" in block

def test_ci_and_documented_no_go():
    yaml=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for marker in [
        "postgres:18","55433:5432",
        "CI_M40928_DISPOSABLE: '1'",
        "CI_M40927_DISPOSABLE: '1'",
        "CI_M40926_DISPOSABLE: '1'",
        "sudo -n useradd",
        "CI_M40928_GUARDIAN_UID",
        "fastapi==0.115.12",
        "httpx==0.28.1",
        "cryptography==45.0.7",
        "PIX_REAL: 'OFF'",
        "PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'",
        "contents: read",
    ]:
        assert marker in yaml
    for marker in [
        "M40927","M40928","M40570","M40730",
        "SO_PEERCRED","mesmo UID","NO-GO","FastAPI",
        "Vault","MIGRATIONS=NONE","PRODUCTION=BLOCKED",
    ]:
        assert marker in doc
