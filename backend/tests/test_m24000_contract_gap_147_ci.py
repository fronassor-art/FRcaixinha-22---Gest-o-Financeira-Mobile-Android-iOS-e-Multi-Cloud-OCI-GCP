"""M24000: read-only 147-clause audit cannot grant production privileges."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/aistudio_contract_gap_audit.py"
DOC=ROOT/"docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json"


def test_147_registry_and_84_backlog_proofs():
    data=json.loads(DOC.read_text(encoding="utf-8"))
    cs=data["clauses"]
    assert len(cs)==147
    assert len({c["id"] for c in cs})==147
    counts={}
    for c in cs:
        counts[c["baseline_status"]]=counts.get(c["baseline_status"],0)+1
        assert c["production_verified"] is False
        assert c["review_state"]=="AWAITING_CLAUSE_EVIDENCE"
        assert c["required_evidence"] and c["next_action"]
    assert counts=={"PARCIAL":58,"BLOQUEADO":50,
                    "NÃO VERIFICADO":34,"DIVERGENTE":5}
    assert data["production_release_authorized"] is False
    assert data["kind"]=="HISTORICAL_BASELINE_NOT_CURRENT_COMPLIANCE"


def test_34_unverified_have_individual_executable_review_actions():
    data=json.loads(DOC.read_text())
    unknown=[x for x in data["clauses"]
             if x["baseline_status"]=="NÃO VERIFICADO"]
    assert len(unknown)==34
    assert all(x["next_action"]!="Revisão individual e evidência ainda necessárias."
               for x in unknown)
    assert len({x["next_action"] for x in unknown})==34
    assert all(x["required_evidence"] for x in unknown)


def test_readonly_cli_validates_against_original_147_checkpoint():
    q=subprocess.run([sys.executable,str(SCRIPT),"--json"],
                     capture_output=True,text=True,timeout=15)
    assert q.returncode==0,(q.stdout,q.stderr)
    d=json.loads(q.stdout)
    assert d["total_clauses"]==147
    assert d["historical_counts"]["BLOQUEADO"]==50
    assert d["historical_counts"]["NÃO VERIFICADO"]==34
    assert d["priority_clauses"]==84
    assert d["clauses_promoted_by_this_audit"]==0
    assert d["current_production_clearance"]=="NOT_ASSESSED_OR_AUTHORIZED"


def test_priority_list_covers_all_84_without_credentials_or_database():
    q=subprocess.run([sys.executable,str(SCRIPT),"--priority"],
                     capture_output=True,text=True,timeout=15)
    assert q.returncode==0,(q.stdout,q.stderr)
    assert q.stdout.count("\tBLOQUEADO\t")==50
    assert q.stdout.count("\tNÃO VERIFICADO\t")==34
    assert "M24000_PRODUCTION_RELEASE=DENIED_PENDING_EVIDENCE" in q.stdout
    s=SCRIPT.read_text()
    assert "psycopg" not in s and "subprocess.run" not in s
    assert "oci" not in s.lower() and "requests" not in s
