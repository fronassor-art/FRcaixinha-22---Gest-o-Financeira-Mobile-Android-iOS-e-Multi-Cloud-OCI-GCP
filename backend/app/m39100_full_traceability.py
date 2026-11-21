"""M39100: offline FR Finance 330-item contractual and operational auditor.

Offline-only, no credentials, DB, network, subprocess, files written,
payments, or production authorization. Builds 2,310 explicit pending steps.
"""
from __future__ import annotations
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CHECKPOINT="docs/FR_FINANCE_CP20261114_CHECKLIST_INTEGRAL_330.json"
HISTORICAL="docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json"
CADERNO="docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md"
CONTRATO="docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md"
GATE_SOURCE="backend/app/launch_readiness.py"
PROVIDER_SOURCE="backend/app/operator_release_worklist.py"
DIVERGENT_LEGACY={"1.6","1.8","4.1","5.3","8.2"}
FAMILY_COUNTS={
 "CURRENT_ORIGINAL_REQUIREMENT":57,
 "CURRENT_ANNEX_REQUIREMENT":49,
 "HISTORICAL_LEGACY_CLAUSE":147,
 "LIVE_RELEASE_GATE":20,
 "EXTERNAL_PROVIDER_GATE":7,
 "ACCEPTANCE_SCENARIO":50,
}
STAGES=(
 ("01_SCOPE","Decidir aplicabilidade e redação aprovada"),
 ("02_CODE","Implementar requisito ou registrar exclusão justificada"),
 ("03_UNIT","Testar casos positivos, negativos e regressões"),
 ("04_SECURITY","Testar autorização, RLS, concorrência, LGPD e isolamento"),
 ("05_E2E","Homologar fluxo integrado em staging com evidência"),
 ("06_EXTERNAL","Coletar pareceres e provas de provedores, quando aplicáveis"),
 ("07_SIGNOFF","Validar prova e aceite humano independente para liberação"),
)


class TraceabilityDrift(ValueError):
 """Never reveal secrets, source or personal data in diagnostics."""


def require(test, code):
 if not test:
  raise TraceabilityDrift("M39100_"+code)


def source(root, name):
 require(type(name) is str and bool(name) and not name.startswith("/")
         and chr(92) not in name and ".." not in Path(name).parts,
         "SOURCE_PATH_INVALID")
 path=root/name
 require(path.is_file() and not path.is_symlink(),"SOURCE_UNAVAILABLE")
 return path.read_bytes()


def git_sha(data):
 return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()


def literal_assignment(root, path, name):
 tree=ast.parse(source(root,path).decode("utf-8"),filename=path)
 for node in tree.body:
  if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name)
    and t.id==name for t in node.targets):
   try: return ast.literal_eval(node.value)
   except (ValueError,SyntaxError,TypeError,MemoryError) as e:
    raise TraceabilityDrift("M39100_SOURCE_LITERAL_UNSAFE") from e
 raise TraceabilityDrift("M39100_SOURCE_REQUIREMENTS_MISSING")


def doc_items(root,path,prefix,original_sections):
 lines=source(root,path).decode("utf-8").splitlines()
 section=None; sections=[]; first=0; annex=0; items=[]
 for line_no,line in enumerate(lines,1):
  if line.startswith("## "):
   section=line[3:].strip()
   sections.append(section)
  if not line.startswith("- "):continue
  require(section is not None,"DOC_BULLET_OUTSIDE_SECTION")
  if len(sections)<=original_sections:
   first+=1
   req_id=f"{prefix}-{first:02d}"
   family="CURRENT_ORIGINAL_REQUIREMENT"
  else:
   annex+=1
   req_id=f"{prefix}-ANX-{len(sections)}-{annex:02d}"
   family="CURRENT_ANNEX_REQUIREMENT"
  items.append(dict(family=family,requirement_id=req_id,
   section=section,source_path=path,source_line=line_no,
   title=" ".join(line[2:].split())))
 require(len(sections)==original_sections+3,"DOC_SECTIONS_DRIFT")
 require((first,annex)==((29,25) if prefix=="CM" else (28,24)),
         "DOC_ITEMS_DRIFT")
 return items


def check(root=ROOT,content=None):
 root=Path(root)
 if content is None:content=json.loads(source(root,CHECKPOINT))
 require(type(content) is dict,"CHECKPOINT_FORMAT")
 require(content.get("schema")=="FR_FINANCE_CP20261114_CHECKLIST_330_V1"
  and content.get("product")=="FR_FINANCE_AI_STUDIO_ONLY"
  and content.get("release_decision")=="NO_GO_PRODUCTION_NOT_AUTHORIZED",
  "CHECKPOINT_IDENTITY")
 counts=content.get("counts")
 require(type(counts) is dict and all(counts.get(k)==v for k,v in {
  **FAMILY_COUNTS,"CM_original":29,"CM_annex":25,
  "CTM_original":28,"CTM_annex":24,
  "original_matrix":281,"annex_additions":49,"expanded_total":330
 }.items()),"CHECKPOINT_COUNTS")
 expected_status={
  "live_release_gates_verified":0,"live_release_gates_total":20,
  "external_provider_gates_verified":0,"external_provider_gates_total":7,
  "AT_scenarios_e2e_verified":0,"AT_scenarios_total":50,
 }
 require(content.get("evidence_status")==expected_status,"GATE_PROMOTION")
 expected_hash=content.get("source_blob_sha")
 require(type(expected_hash) is dict and set(expected_hash)=={
  CADERNO,CONTRATO,HISTORICAL,GATE_SOURCE,
  "backend/app/release_evidence_matrix.py",PROVIDER_SOURCE
 },"SOURCE_SET_DRIFT")
 for path,expect in expected_hash.items():
  require(type(expect) is str and git_sha(source(root,path))==expect,
          "SOURCE_BLOB_DRIFT")
 items=content.get("items")
 require(type(items) is list and len(items)==330
  and all(type(x) is dict for x in items),"ITEM_TOTAL_DRIFT")
 require([x.get("check_id") for x in items]==[
  f"CP26-{i:04d}" for i in range(1,331)],"CHECK_IDS_DRIFT")
 require(len({(x.get("family"),x.get("requirement_id")) for x in items})
         ==330,"SOURCE_IDS_DUPLICATED")
 require(Counter(x["family"] for x in items)==FAMILY_COUNTS,
         "FAMILY_COUNTS_DRIFT")
 observed=[x for x in items if x["family"] in (
  "CURRENT_ORIGINAL_REQUIREMENT","CURRENT_ANNEX_REQUIREMENT")]
 docs=doc_items(root,CADERNO,"CM",6)+doc_items(root,CONTRATO,"CTM",7)
 require(len(observed)==len(docs)==106,"CURRENT_DOC_ITEMS_DRIFT")
 for x,d in zip(observed,docs):
  require(all(x.get(k)==d[k] for k in (
   "family","requirement_id","section","source_path","source_line","title")),
   "CURRENT_DOC_TEXT_DRIFT")
 historic=json.loads(source(root,HISTORICAL))["clauses"]
 historical=[x for x in items if x["family"]=="HISTORICAL_LEGACY_CLAUSE"]
 require(len(historic)==len(historical)==147,"HISTORICAL_COUNT")
 require(all(x["requirement_id"]=="HIST-"+c["id"]
  and x["title"]==c["name"]
  and x["historical_baseline"]==c["baseline_status"]
  and x["source_path"]==HISTORICAL for x,c in zip(historical,historic)),
  "HISTORICAL_DRIFT")
 require({x["requirement_id"].removeprefix("HIST-") for x in historical
  if x["historical_baseline"]=="DIVERGENTE"}==DIVERGENT_LEGACY,
  "DIVERGENCE_DRIFT")
 gate_ids=[x[0] for x in literal_assignment(root,GATE_SOURCE,"REQUIREMENTS")]
 release=[x for x in items if x["family"]=="LIVE_RELEASE_GATE"]
 require(len(gate_ids)==20 and [x["requirement_id"] for x in release]==gate_ids,
         "LIVE_GATES_DRIFT")
 provider=list(literal_assignment(root,PROVIDER_SOURCE,"PROVIDER_TASKS"))
 providers=[x for x in items if x["family"]=="EXTERNAL_PROVIDER_GATE"]
 require(len(provider)==7
  and [x["requirement_id"] for x in providers]==provider,"PROVIDER_GATES_DRIFT")
 acceptance=[x for x in items if x["family"]=="ACCEPTANCE_SCENARIO"]
 require([x["requirement_id"] for x in acceptance]==[
  f"AT-{i:02d}" for i in range(1,51)],"AT_SCENARIO_DRIFT")
 for x in items:
  require(x.get("production_verified") is False
   and x.get("acceptance_state")=="PENDING_INDEPENDENT_EVIDENCE"
   and isinstance(x.get("required_proof"),str)
   and x["required_proof"].strip(),"UNSUPPORTED_APPROVAL")
 candidate_found=0;candidate_unproven=0
 for item in items:
  for token in str(item.get("evidence_candidates") or "").split(";"):
   name=token.strip().strip(chr(96))
   if not name:continue
   require(not name.startswith("/") and chr(92) not in name
           and ".." not in Path(name).parts,"EVIDENCE_PATH_UNSAFE")
   file=root/name
   if file.is_file() and not file.is_symlink():
    candidate_found+=1
   else:
    candidate_unproven+=1
 return {
  "project":"FR_FINANCE_AI_STUDIO_ONLY",
  "package":"M39100_M39429",
  "source_integrity":"PASS",
  "production_release":"BLOCKED",
  "production_verified":False,
  "documentary_requirements":106,
  "historical_clauses_review_pending":147,
  "live_gates_independently_verified":0,
  "live_gates_total":20,
  "provider_gates_independently_verified":0,
  "provider_gates_total":7,
  "AT_scenarios_e2e_verified":0,
  "AT_scenarios_total":50,
  "items_checked":330,
  "candidate_source_paths_present":candidate_found,
  "candidate_source_paths_missing_or_generic":candidate_unproven,
  "macro_tasks_planned":330*len(STAGES),
  "macro_tasks_closed_by_code":0,
  "database_queries":0,
  "database_writes":0,
  "migrations":0,
  "cloud_mutations":0,
  "real_pix":False,
  "real_payments":False,
  "real_activation":False,
 }


def workplan(root=ROOT,content=None):
 check(root,content)
 if content is None:content=json.loads(source(Path(root),CHECKPOINT))
 result=[]
 for index,item in enumerate(content["items"],1):
  for step,(suffix,action) in enumerate(STAGES):
   result.append({
    "task_id":f"M39100-{index:03d}-{suffix}",
    "check_id":item["check_id"],
    "requirement_id":item["requirement_id"],
    "family":item["family"],
    "action":action,
    "depends_on":[] if step==0 else [
     f"M39100-{index:03d}-{STAGES[step-1][0]}"],
    "responsible_role":(
     "LEGAL_PRODUCT" if step==0 else "ENGINEERING"
     if step in (1,2) else "SECURITY" if step==3 else
     "QA_STAGING" if step==4 else "PROVIDER_LEGAL" if step==5
     else "INDEPENDENT_RELEASE_REVIEWER"),
    "status":"PENDING_EVIDENCE",
    "proof_required":item["required_proof"],
    "production_authorized":False,
   })
 require(len(result)==2310 and
  len({x["task_id"] for x in result})==2310,"MACRO_TASK_DRIFT")
 return result
