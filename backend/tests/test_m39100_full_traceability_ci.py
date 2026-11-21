"""M39100: 330-point contract manifest + 2310-stage no-go regression tests.

No network, server, SQL, clouds or user secrets; synthetic mutations only.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from app.m39100_full_traceability import (
 ROOT, CHECKPOINT, HISTORICAL, CADERNO, CONTRATO,
 GATE_SOURCE, PROVIDER_SOURCE, FAMILY_COUNTS, STAGES,
 TraceabilityDrift, check, source, workplan,
)


@pytest.fixture(scope="module")
def manifest():
 return json.loads(source(ROOT,CHECKPOINT))


@pytest.fixture(scope="module")
def audited():
 return check()


def test_full_contract_and_annexes_are_reconciled(audited):
 assert audited["source_integrity"]=="PASS"
 assert audited["items_checked"]==330
 assert audited["documentary_requirements"]==106
 assert audited["historical_clauses_review_pending"]==147
 assert audited["live_gates_total"]==20
 assert audited["provider_gates_total"]==7
 assert audited["AT_scenarios_total"]==50
 assert audited["macro_tasks_planned"]==2310


def test_all_330_ids_are_unique_and_no_one_has_production_signoff(manifest):
 xs=manifest["items"]
 assert len({x["check_id"] for x in xs})==330
 assert len({(x["family"],x["requirement_id"]) for x in xs})==330
 assert all(x["production_verified"] is False for x in xs)
 assert all(x["acceptance_state"]=="PENDING_INDEPENDENT_EVIDENCE" for x in xs)
 assert all(x["source_path"] and x["title"] and x["required_proof"] for x in xs)
 for i,x in enumerate(xs,1):
  assert x["check_id"]==f"CP26-{i:04d}"


def test_explicit_330_families_and_no_undocumented_annexes(manifest):
 from collections import Counter
 assert Counter(x["family"] for x in manifest["items"])==FAMILY_COUNTS
 assert sum(manifest["counts"][k] for k in (
  "CM_original","CM_annex","CTM_original","CTM_annex"))==106
 assert manifest["counts"]["original_matrix"]==281
 assert manifest["counts"]["expanded_total"]==330


def test_147_historical_clauses_not_automatically_binding(manifest):
 clauses=[x for x in manifest["items"] if x["family"]=="HISTORICAL_LEGACY_CLAUSE"]
 assert len(clauses)==147
 assert {x["requirement_id"] for x in clauses
         if x["historical_baseline"]=="DIVERGENTE"}=={
  "HIST-1.6","HIST-1.8","HIST-4.1","HIST-5.3","HIST-8.2"
 }
 assert manifest["baseline_counts"]=={
  "PARCIAL":58,"BLOQUEADO":50,"DIVERGENTE":5,"NÃO VERIFICADO":34
 }


def test_macro_has_all_2310_unique_numbered_stages(manifest):
 tasks=workplan(content=manifest)
 assert len(tasks)==330*7
 assert len({t["task_id"] for t in tasks})==2310
 assert set(t["check_id"] for t in tasks)=={
  x["check_id"] for x in manifest["items"]}
 assert all(t["production_authorized"] is False
            and t["status"]=="PENDING_EVIDENCE" for t in tasks)
 assert tasks[0]["depends_on"]==[]
 assert tasks[1]["depends_on"]==[tasks[0]["task_id"]]
 assert tasks[6]["depends_on"]==[tasks[5]["task_id"]]
 assert tasks[7]["depends_on"]==[]
 assert tasks[-1]["requirement_id"]=="AT-50"


@pytest.mark.parametrize("index",list(range(330)))
def test_every_requirement_has_seven_explicit_stages(manifest,index):
 item=manifest["items"][index]
 stages=STAGES
 assert len(stages)==7
 assert all(suffix.startswith(f"{i:02d}_") for i,(suffix,_) in
            enumerate(stages,1))
 assert item["check_id"]==f"CP26-{index+1:04d}"
 assert item["production_verified"] is False


@pytest.mark.parametrize("tamper,code",[
 (lambda m:m.update(release_decision="PRODUCTION_AUTHORIZED"),
  "CHECKPOINT_IDENTITY"),
 (lambda m:m["counts"].update(expanded_total=329),"CHECKPOINT_COUNTS"),
 (lambda m:m["evidence_status"].update(live_release_gates_verified=1),
  "GATE_PROMOTION"),
 (lambda m:m["items"][0].update(check_id="CP26-9999"),
  "CHECK_IDS_DRIFT"),
 (lambda m:m["items"][0].update(requirement_id="CM-TAMPER"),
  "CURRENT_DOC_TEXT_DRIFT"),
 (lambda m:m["items"][0].update(title="Texto alterado sem aprovação"),
  "CURRENT_DOC_TEXT_DRIFT"),
 (lambda m:m["items"][0].update(production_verified=True),
  "UNSUPPORTED_APPROVAL"),
 (lambda m:m["items"][0].update(acceptance_state="PASS"),
  "UNSUPPORTED_APPROVAL"),
 (lambda m:m["items"][0].update(required_proof=""),
  "UNSUPPORTED_APPROVAL"),
 (lambda m:m["items"][-1].update(requirement_id="AT-99"),
  "AT_SCENARIO_DRIFT"),
 (lambda m:m["items"].pop(),"CHECKPOINT_FORMAT_PLACEHOLDER"),
])
def test_tampering_cannot_silently_promote_readiness(manifest,tamper,code):
 data=deepcopy(manifest)
 tamper(data)
 if code=="CHECKPOINT_FORMAT_PLACEHOLDER":code="ITEM_TOTAL_DRIFT"
 with pytest.raises(TraceabilityDrift,match="M39100_"+code):
  check(content=data)


def test_sources_are_sha_locked_and_new_annexes_cannot_go_unnoticed(tmp_path,manifest):
 paths=set(manifest["source_blob_sha"])|{CHECKPOINT}
 for path in paths:
  target=tmp_path/path
  target.parent.mkdir(parents=True,exist_ok=True)
  target.write_bytes(source(ROOT,path))
 assert check(root=tmp_path)["items_checked"]==330
 target=tmp_path/CADERNO
 target.write_text(target.read_text()+"\n- Novo requisito sem checkpoint.\n")
 with pytest.raises(TraceabilityDrift,match="M39100_SOURCE_BLOB_DRIFT"):
  check(root=tmp_path)


def test_source_path_injection_is_rejected_without_leaks(manifest):
 data=deepcopy(manifest)
 data["items"][0]["evidence_candidates"]="../../etc/passwd"
 with pytest.raises(TraceabilityDrift,match="M39100_EVIDENCE_PATH_UNSAFE"):
  check(content=data)


def test_no_external_or_financial_side_effects(audited):
 assert audited["production_release"]=="BLOCKED"
 assert audited["production_verified"] is False
 for key in ("database_queries","database_writes","migrations",
             "cloud_mutations"):
  assert audited[key]==0
 for key in ("real_pix","real_payments","real_activation"):
  assert audited[key] is False
 assert audited["live_gates_independently_verified"]==0
 assert audited["provider_gates_independently_verified"]==0
 assert audited["AT_scenarios_e2e_verified"]==0


def test_cli_summary_is_reproducible_and_does_not_contain_secrets():
 script=ROOT/"backend/scripts/frfinance_m39100_super_macropacote_readonly.py"
 p=subprocess.run([sys.executable,"-B",str(script),"summary"],
  text=True,capture_output=True,cwd=ROOT,check=True)
 assert "M39100_REQUIREMENTS=330_330_TRACED" in p.stdout
 assert "M39100_TASK_STAGES=2310_PLANNED" in p.stdout
 assert "M39100_PRODUCTION_RELEASE=BLOCKED" in p.stdout
 assert "M39100_POSTGRESQL_ACCESS=NONE" in p.stdout
 assert "M39100_MIGRATIONS=NONE" in p.stdout
 assert not any(x in p.stdout+p.stderr for x in (
  "ocid1.","sk_test_","sk_live_","Bearer eyJ","postgresql://"))
 j=subprocess.run([sys.executable,"-B",str(script),"json"],
  text=True,capture_output=True,cwd=ROOT,check=True)
 assert json.loads(j.stdout)["production_verified"] is False
