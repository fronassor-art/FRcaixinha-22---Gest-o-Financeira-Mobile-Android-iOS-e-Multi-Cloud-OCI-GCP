"""M40927 static, fail-closed and process-boundary contract tests."""
from pathlib import Path
import os
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]
MAIN=ROOT/"backend/tests/m40927_isolated_guardian_process_disposable.py"
WORKER=ROOT/"backend/tests/m40927_guardian_worker_disposable.py"
YML=ROOT/".github/workflows/frfinance-m40927-isolated-guardian-process-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40927_ISOLATED_GUARDIAN_PROCESS_NO_GO.md"
SRC=MAIN.read_text(encoding="utf-8")
CHILD=WORKER.read_text(encoding="utf-8")

@pytest.mark.parametrize("script", [MAIN,WORKER])
def test_disposable_scripts_reject_local_termux(script):
    result=subprocess.run(
        [sys.executable,"-B",str(script)],text=True,capture_output=True,
        env={"PATH":os.environ.get("PATH","")},timeout=15,
    )
    assert result.returncode==2
    assert "STATUS=BLOCKED_RuntimeError" in result.stdout
    assert "ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in result.stdout

@pytest.mark.parametrize("needle", [
    "CI_M40927_DISPOSABLE",
    "from m40926_dual_custody_master_disposable import require_disposable",
    "subprocess.Popen(",
    "env=child_env",
    "CI_M40927_GUARDIAN_DSN",
    "CI_M40927_PUBLIC_REGISTRY",
    "M40927_GUARDIAN_SEPARATE_OS_PROCESS=PASS",
    "M40927_GATEWAY_NO_GUARDIAN_DSN=PASS_FIXTURE",
    "M40927_GUARDIAN_NO_APP_ISSUER_ROOT_DSN=PASS_FIXTURE",
    "guardian_call(",
    "m40924.gated_draft(",
    "m40924.gated_transition(",
    "M40927_ASGI_SIGNED_DRAFT_PUBLISH_CANCEL=PASS",
    "M40927_INVALID_SIGNATURE_SCOPE_REPLAY_MEMBER=DENIED",
    "M40927_STOLEN_APP_ISSUER_MASTER_WITHOUT_SIGNED_SEAL=DENIED",
    "M40927_GUARDIAN_PROCESS_NONCE_ONE_OF_SIX=PASS",
    "M40927_REVOKED_MASTER=DENIED",
    "M40927_STOLEN_ALL_THREE_SQL_LOGINS=NO_GO_BYPASS",
    "M40927_GUARDIAN_UNAVAILABLE=FAIL_CLOSED_503",
    "M40927_ORCHESTRATOR_ROOT_FIXTURE=NOT_PRODUCTION_ISOLATION",
])
def test_orchestrator_boundaries_and_negative_cases(needle):
    assert needle in SRC

@pytest.mark.parametrize("needle", [
    "GITHUB_ACTIONS",
    "FRCAIXINHA_CI_ISOLATED",
    "CI_M40927_GUARDIAN_ONLY",
    "CI_PROMOTIONS_DATABASE_URL",
    "CI_M40927_APP_DSN",
    "CI_M40927_ISSUER_DSN",
    "CI_M40927_PRIVATE_KEY",
    "M40927_GUARDIAN_DATABASE_IDENTITY_DENIED",
    "m40926_guardian_login",
    "m40923_offdb_master_action_gate import",
    "EphemeralApprovalGate",
    "parse_arguments",
    "body_digest(body)",
    "verification.authorize(",
    "m40924.draft_digest(",
    "m40924.transition_digest(",
    "m40926.seals",
    "client.shutdown(socket.SHUT_WR)" if False else "server.bind(path)",
    "os.chmod(path,0o600)",
    "M40927_GUARDIAN_WORKER_UNIX_SOCKET=READY",
    "M40927_GUARDIAN_HAS_NO_ROOT_ISSUER_APP_DSN=PASS",
    "M40927_GUARDIAN_PUBLIC_KEYS_ONLY=PASS",
])
def test_child_has_only_guardian_database_and_public_keys(needle):
    assert needle in CHILD

@pytest.mark.parametrize("forbidden", [
    "pg_ctl","pg_dump","pg_restore","127.0.0.1:5433",
    "ALTER ROLE frc_ai_owner","backend/migrations/114",
    "ATIVACAO_REAL=ON","PAGAMENTOS_REAIS=ON","PIX_REAL=ON",
])
def test_both_scripts_never_touch_original_database(forbidden):
    assert forbidden not in SRC and forbidden not in CHILD

def test_app_factory_signature_cannot_receive_guardian_sql_login():
    header=SRC.split("def app_factory(",1)[1].split("):",1)[0]
    assert "issuer_dsn" in header and "app_dsn" in header
    assert "guardian_socket_path" in header
    assert "guardian_dsn" not in header
    assert "public_registry" not in header

def test_ci_and_no_go_controls_documented():
    yaml=YML.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    for needle in (
        "postgres:18","55433:5432",
        "CI_M40927_DISPOSABLE: '1'",
        "CI_M40926_DISPOSABLE: '1'",
        "CI_M40925_DISPOSABLE: '1'",
        "CI_M40924_DISPOSABLE: '1'",
        "CI_M40923_DISPOSABLE: '1'",
        "fastapi==0.115.12","httpx==0.28.1",
        "cryptography==45.0.7",
        "PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'","contents: read",
    ):
        assert needle in yaml
    for needle in (
        "M40926","M40927","NO-GO","Ed25519","FastAPI",
        "M40570","M40730","socket Unix","mesmo UID",
        "Vault","MIGRATIONS=NONE","PRODUCTION=BLOCKED",
    ):
        assert needle in doc
