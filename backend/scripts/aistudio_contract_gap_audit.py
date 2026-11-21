#!/usr/bin/env python3
"""FR Finance AI Studio M24000: inspect historical 147-clause backlog safely.

Reads two versioned repository documents only. No cloud APIs, DB, credentials,
network or code mutation. A baseline classification is NOT a current finding.
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
BASELINE=ROOT/"docs/CHECKPOINT_CONTRATO_2026-11-01.md"
REGISTER=ROOT/"docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json"
EXPECTED={"PARCIAL":58,"BLOQUEADO":50,"NÃO VERIFICADO":34,"DIVERGENTE":5}
ID=re.compile(r"^\d+(?:\.\d+)?(?:[-][A-Z0-9.]+)?$")


def baseline_rows():
    source=BASELINE.read_text(encoding="utf-8")
    part=source.split("## Matriz das 147 cláusulas\n",1)[1].split(
        "\n## Contagem e histórico",1)[0]
    result=[]
    for line in part.splitlines():
        if not line.startswith("|"):
            continue
        cols=[x.strip() for x in line.split("|")[1:-1]]
        if len(cols)!=6 or not ID.fullmatch(cols[0]):
            continue
        clause,name,status,source_hint,prior_test_hint,remaining=cols
        result.append((clause,name,status,source_hint,prior_test_hint,remaining))
    return result


def inspect():
    baseline=baseline_rows()
    manifest=json.loads(REGISTER.read_text(encoding="utf-8"))
    clauses=manifest["clauses"]
    assert manifest["schema"]=="FR_FINANCE_AI_STUDIO_CONTRACT_BACKLOG_M24000_V1"
    assert manifest["source_product"]=="FR_FINANCE_AI_STUDIO_ONLY"
    assert manifest["kind"]=="HISTORICAL_BASELINE_NOT_CURRENT_COMPLIANCE"
    assert manifest["production_release_authorized"] is False
    assert len(baseline)==len(clauses)==147
    ids=[row[0] for row in baseline]
    assert len(set(ids))==147
    status=Counter(row[2] for row in baseline)
    assert dict(status)==EXPECTED
    assert manifest["counts"]==EXPECTED
    assert len({c["id"] for c in clauses})==147
    for record,expected in zip(clauses,baseline):
        keys=("id","name","baseline_status","source_hint",
              "prior_test_hint","remaining_evidence")
        assert tuple(record[k] for k in keys)==expected,record["id"]
        assert record["review_state"]=="AWAITING_CLAUSE_EVIDENCE",record["id"]
        assert record["production_verified"] is False,record["id"]
        assert record["workstream"] and record["required_evidence"]
        if record["baseline_status"] in ("BLOQUEADO","NÃO VERIFICADO"):
            assert record["next_action"] and len(record["next_action"])>=18
    summary={
        "schema":"FR_FINANCE_AI_STUDIO_M24000_GAP_AUDIT_V1",
        "basis":"HISTORICAL_2026-11-01",
        "current_production_clearance":"NOT_ASSESSED_OR_AUTHORIZED",
        "total_clauses":len(clauses),
        "historical_counts":dict(status),
        "priority_clauses":sum(c["baseline_status"] in
                                ("BLOQUEADO","NÃO VERIFICADO")
                                for c in clauses),
        "clauses_promoted_by_this_audit":0,
        "workstreams":dict(sorted(Counter(c["workstream"] for c in clauses).items())),
    }
    assert summary["priority_clauses"]==84
    return summary,clauses


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json",action="store_true",help="Print summary only as JSON")
    ap.add_argument("--priority",action="store_true",
                    help="List 84 blocked or unverified historical clauses")
    args=ap.parse_args()
    summary,clauses=inspect()
    if args.json:
        print(json.dumps(summary,ensure_ascii=False,sort_keys=True))
    else:
        print("M24000_CONTRACT_147=PASS")
        print("M24000_HISTORICAL_BLOCKED=50")
        print("M24000_HISTORICAL_NOT_VERIFIED=34")
        print("M24000_PRIORITY_BACKLOG=84")
        print("M24000_AUTOMATIC_CLAUSE_CLOSURE=0")
        print("M24000_PRODUCTION_RELEASE=DENIED_PENDING_EVIDENCE")
        if args.priority:
            for c in clauses:
                if c["baseline_status"] in ("BLOQUEADO","NÃO VERIFICADO"):
                    print(f'{c["id"]}\t{c["baseline_status"]}\t'
                          f'{c["workstream"]}\t{c["next_action"]}')
    return 0


if __name__=="__main__":
    raise SystemExit(main())
