#!/usr/bin/env python3
"""FR Finance M39100 — source-locked 330-item CP and 2,310-step offline plan.

Modes: audit (default), json, plan, summary. Standard library only.
No GitHub credentials, database, network, cloud, secrets or file writes.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"backend"))
from app.m39100_full_traceability import TraceabilityDrift,check,workplan


def main(argv=None):
 args=list(sys.argv[1:] if argv is None else argv)
 mode=args[0] if args else "audit"
 if len(args)>1 or mode not in ("audit","summary","json","plan"):
  print("M39100_USAGE=audit|summary|json|plan",file=sys.stderr)
  return 2
 try:
  result=check()
  if mode=="plan":
   print(json.dumps({
    "package":"M39100_M39429",
    "production_release":"BLOCKED",
    "stages_per_requirement":7,
    "tasks":workplan(),
   },ensure_ascii=False,sort_keys=True))
  elif mode=="json":
   print(json.dumps(result,ensure_ascii=False,sort_keys=True))
  else:
   print("=== FR FINANCE M39100–M39429 | SUPER MACROPACOTE ===")
   print("M39100_SOURCES=INTEGRITY_PASS")
   print("M39100_REQUIREMENTS=330_330_TRACED")
   print("M39100_CURRENT_DOC_REQUIREMENTS=106")
   print("M39100_HISTORICAL_CLAUSES=147_REVIEW_PENDING")
   print("M39100_TASK_STAGES=2310_PLANNED")
   print("M39100_LIVE_GATES=0_OF_20_INDEPENDENTLY_ATTESTED")
   print("M39100_PROVIDER_GATES=0_OF_7_INDEPENDENTLY_ATTESTED")
   print("M39100_AT_SCENARIOS=0_OF_50_E2E_ATTESTED")
   print("M39100_EVIDENCE_CANDIDATES_FOUND="+str(
    result["candidate_source_paths_present"]))
   print("M39100_EVIDENCE_CANDIDATES_NOT_PROVEN="+str(
    result["candidate_source_paths_missing_or_generic"]))
   print("M39100_PRODUCTION_RELEASE=BLOCKED")
   print("M39100_POSTGRESQL_ACCESS=NONE")
   print("M39100_MIGRATIONS=NONE")
   print("M39100_OCI_MUTATIONS=NONE")
   print("M39100_PIX_REAL=OFF")
   print("M39100_PAYMENTS_REAL=OFF")
   print("M39100_ACTIVATION_REAL=OFF")
  return 0
 except (TraceabilityDrift,ValueError,FileNotFoundError,KeyError,
         UnicodeDecodeError,TypeError) as error:
  code=str(error)
  if not code.startswith("M39100_"):code="M39100_UNEXPECTED_AUDIT_FAILURE"
  print(code,file=sys.stderr)
  print("M39100_PRODUCTION_RELEASE=BLOCKED",file=sys.stderr)
  return 2


if __name__=="__main__":
 raise SystemExit(main())
