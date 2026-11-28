"""M40923 offline security regressions, isolated signature parser and runner."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from hashlib import sha256
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/tests/m40923_offdb_master_sql_issuer_disposable.py"
GATE=ROOT/"backend/tests/m40923_offdb_master_action_gate.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40923-offdb-master-command-pg18-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40923_OFFDB_MASTER_COMMAND_NO_GO.md"
SRC=SCRIPT.read_text(encoding="utf-8")
sys.path.insert(0,str(GATE.parent))
from m40923_offdb_master_action_gate import (
    EphemeralApprovalGate, body_digest, sign, canonical,
)

def test_ci_runner_fails_closed_without_github_disposable_flags():
    p=subprocess.run([sys.executable,"-B",str(SCRIPT)],
        env={"PATH":os.environ.get("PATH","")},text=True,capture_output=True,
        timeout=15)
    assert p.returncode==2
    assert "M40923_STATUS=BLOCKED_RuntimeError" in p.stdout
    assert "M40923_ORIGINAL_TERMUX_PG_5433=NOT_ACCESSED" in p.stdout

def setup_signer():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private=Ed25519PrivateKey.generate()
    actor,tenant,nonce=map(lambda _:str(uuid4()),range(3))
    digest=sha256(b"synthetic-session").hexdigest()
    command={
        "version":1,"method":"POST",
        "path":"/master/saas-promotions/transition",
        "actor_id":actor,"tenant_id":tenant,
        "session_digest":digest,"action":"PUBLISH",
        "campaign_id":str(uuid4()),"expected_revision":1,
        "body_digest":body_digest({"reason":"isolated-test"}),
        "nonce":nonce,"expires_at":100010,
    }
    registry=EphemeralApprovalGate({
        (actor,tenant,digest):private.public_key()
    })
    return private,registry,command

def test_valid_signature_once_then_replay_denied():
    private,gate,cmd=setup_signer()
    signature=sign(private,cmd)
    assert gate.authorize(cmd,signature,now=100000)
    assert not gate.authorize(cmd,signature,now=100000)

@pytest.mark.parametrize("patch",[
    {"action":"CANCEL"},
    {"method":"GET"},
    {"path":"/master/other"},
    {"expected_revision":2},
    {"body_digest":"a"*64},
    {"tenant_id":str(uuid4())},
    {"actor_id":str(uuid4())},
    {"session_digest":"f"*64},
    {"nonce":str(uuid4())},
    {"expires_at":100100},
    {"expires_at":100000},
    {"campaign_id":None},
    {"version":2},
])
def test_changed_or_invalid_command_fails_signature_or_context(patch):
    private,gate,cmd=setup_signer()
    assert not gate.authorize({**cmd,**patch},sign(private,cmd),now=100000)

def test_unknown_field_and_noncanonical_signature_denied():
    private,gate,cmd=setup_signer()
    with pytest.raises(ValueError):
        canonical({**cmd,"identity":"extra"})
    assert not gate.authorize(cmd,sign(private,cmd)+"=",now=100000)

def test_wrong_key_and_missing_registry_denied():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    private,gate,cmd=setup_signer()
    other=Ed25519PrivateKey.generate()
    assert not gate.authorize(cmd,sign(other,cmd),now=100000)
    assert not EphemeralApprovalGate({}).authorize(cmd,sign(private,cmd),now=100000)

@pytest.mark.parametrize("marker",[
    "CI_M40923_DISPOSABLE",
    "CREATE ROLE m40923_issuer_login LOGIN NOINHERIT NOBYPASSRLS",
    "M40923_STOLEN_SIGNER_SQL_LOGIN_NO_MASTER_WRITE=PASS",
    "M40923_OFFDB_ED25519_COMMAND_CONTEXT=PASS",
    "M40923_STOLEN_APP_SQL_PLUS_MASTER_BEARER=NO_GO_BYPASS_CONFIRMED",
    "M40923_MASTER_REVOCATION=ENFORCED",
    "M40923_DB_OWNER_OR_APP_SQL_COMPROMISE=NOT_REMEDIATED_NO_GO",
])
def test_compromised_issuer_and_bypass_regression_is_explicit(marker):
    assert marker in SRC

@pytest.mark.parametrize("forbidden",[
    "pg_ctl","pg_dump","pg_restore","subprocess.Popen",
    "os.system(","127.0.0.1:5433","backend/migrations/114",
    "ALTER ROLE frc_ai_owner",
])
def test_original_database_never_targeted(forbidden):
    assert forbidden not in SRC

def test_ci_contract_and_no_go_document():
    y=WORKFLOW.read_text()
    doc=DOC.read_text()
    for needle in ("postgres:18","55433:5432",
        "CI_M40923_DISPOSABLE: '1'","CI_M40922_DISPOSABLE: '1'",
        "PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'",
        "ATIVACAO_REAL: 'OFF'","contents: read",
        "cryptography==45.0.7"):
        assert needle in y
    for needle in ("M40570","M40730","M40922","NO-GO",
        "MIGRATIONS=NONE","PRODUCTION=BLOCKED"):
        assert needle in doc
