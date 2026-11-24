"""M40939 source-only release gate and missing/corrupt/cyclic task tests."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import subprocess
import sys
import os

import pytest

from scripts.frfinance_m40939_release_gate import (
    GateInvalid, MANIFEST, ROOT, validate, expected_production_gate_ids,
)

RUNNER=ROOT/"backend/scripts/frfinance_m40939_release_gate.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40939-supermacropacote-gates-ci.yml"
DOC=ROOT/"docs/FR_FINANCE_M40939_SUPERMACRO_CADERNO_EXECUCAO_NO_GO.md"


def manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_all_twenty_canonical_launch_gates_are_blocked():
    obj=manifest()
    report=validate(obj)
    assert report["M40939_PRODUCTION_GATES"]==20
    assert len(expected_production_gate_ids())==20
    assert report["M40939_DECISION"]=="NO_GO"
    assert report["M40939_MIGRATION"]=="NOT_AUTHORIZED"
    assert report["M40939_PRODUCTION"]=="BLOCKED"
    assert report["M40939_BLOCKED_OR_CI_PENDING"]>=30


@pytest.mark.parametrize("mutate",[
    lambda a: a.update({"release_decision":"GO"}),
    lambda a: a.update({"production_enabled":True}),
    lambda a: a.update({"pix_real":"ON"}),
    lambda a: a.update({"original_database_migrations_authorized":True}),
    lambda a: a["production_gates"][0].update({"production_verified":True}),
    lambda a: a["production_gates"].pop(),
    lambda a: a["tasks"][0].update({"status":"READY"}),
    lambda a: a["tasks"][0].update({"depends_on":["UNKNOWN_DEPENDENCY"]}),
    lambda a: a["tasks"][0].update({"depends_on":["M40730_INDEPENDENT_ISSUER"]}),
    lambda a: a["tasks"][1].update({"status":"DONE_SOURCE_ONLY"}),
    lambda a: a["tasks"].append(copy.deepcopy(a["tasks"][0])),
])
def test_mutated_or_false_approval_cannot_pass_validation(mutate):
    obj=copy.deepcopy(manifest())
    mutate(obj)
    with pytest.raises((GateInvalid,KeyError,ValueError)):
        validate(obj)


def test_release_mode_is_always_denied_and_audit_is_safe():
    env={"PATH":os.getenv("PATH",""),"ENVIRONMENT":"production",
         "PIX_REAL":"ON","PAGAMENTOS_REAIS":"ON","ATIVACAO_REAL":"ON",
         "FR_FINANCE_SQL_TRUST_APPROVED":"true"}
    a=subprocess.run([sys.executable,"-B",str(RUNNER)],
                     capture_output=True,text=True,timeout=10,env=env)
    b=subprocess.run([sys.executable,"-B",str(RUNNER),
                      "--mode","approve-production"],
                     capture_output=True,text=True,timeout=10,env=env)
    assert a.returncode==0,a.stdout+a.stderr
    assert "M40939_DECISION=NO_GO" in a.stdout
    assert b.returncode==2
    assert "M40939_APPROVAL=DENIED_EXTERNAL_ATTESTATION_REQUIRED" in b.stdout


def test_no_database_network_service_or_git_side_effects():
    code=RUNNER.read_text(encoding="utf-8")
    for unsafe in ("import psycopg","import asyncpg","import requests",
                   "subprocess.run", "os.system", "git fetch", "git merge",
                   "pg_ctl", "CREATE DATABASE", "ALTER ROLE", "SET ROLE"):
        assert unsafe not in code
    assert "M40939_ORIGINAL_DB" in code
    assert "M40939_TERMUX_SYNC" in code
    assert "M40939_MIGRATION" in code


def test_ci_and_manual_synchronization_policy_not_bypassed():
    yaml=WORKFLOW.read_text(encoding="utf-8")
    doc=DOC.read_text(encoding="utf-8")
    assert "test_m40939_supermacropacote_gates_ci.py" in yaml
    assert "contents: read" in yaml
    for token in ("M40600","M40840","M40930","SQL",
                  "Termux","NO-GO","PIX_REAL=OFF"):
        assert token in doc
