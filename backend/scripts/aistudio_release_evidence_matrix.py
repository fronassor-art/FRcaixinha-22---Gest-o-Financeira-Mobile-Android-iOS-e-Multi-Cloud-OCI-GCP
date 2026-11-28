#!/usr/bin/env python3
"""M28800: nonsecret launch checklist for Termux and GitHub CI.

Never connects to OCI, Mercado Pago, SMTP or PostgreSQL. Never applies SQL,
creates accounts or changes environment flags.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.release_evidence_matrix import build_release_matrix
from aistudio_provider_intake import _default_file, read_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="FR Finance M28800 — auditoria somente leitura, sem ativacao"
    )
    parser.add_argument("action", choices=("audit", "plan", "json"), nargs="?", default="audit")
    args = parser.parse_args(argv)

    local = _default_file()
    # The operator's local provider metadata stays outside Git; only names
    # of missing fields appear in any output.
    if local.exists() or local.is_symlink():
        manifest = read_file(local)
        source = "OPERATOR_LOCAL_PUBLIC_MANIFEST"
    else:
        manifest = None
        source = "NO_LOCAL_PUBLIC_MANIFEST"

    baseline_path = ROOT / "docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    matrix = build_release_matrix(manifest, contract_baseline=baseline)
    matrix["public_manifest_source"] = source

    if args.action == "json":
        print(json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    print("=== FR FINANCE M28700-M29000 ===")
    print("BRANCH=AI_STUDIO_ONLY")
    print("RELEASE=BLOCKED_EXTERNAL_ATTESTATION")
    print(f"RELEASE_GATES_UNVERIFIED={matrix['gates_unverified']}")
    print(f"PROVIDER_GATES_UNVERIFIED={matrix['provider_gate_count']}")
    print(f"HISTORICAL_147_CLAUSES={matrix['historical_contract_baseline']['total']}")
    print(f"PUBLIC_FIELDS_MISSING={len(matrix['public_fields_absent'])}")
    print("PUBLIC_INPUTS_SOURCE=" + source)
    print("MIGRATIONS_APPLIED=NO")
    print("REAL_USERS=OFF")
    print("REAL_PIX=OFF")
    print("OCI_OPERATIONS=NONE")
    if args.action == "plan":
        print("=== PRIORIDADE DE HOMOLOGACAO ===")
        for item in matrix["gates"]:
            print(f"P{item['priority']:02d} {item['id']} {item['status']} {item['acceptance_proof']}")
        print("=== DADOS PUBLICOS PENDENTES (NOMES) ===")
        for key in matrix["public_fields_absent"]:
            print("PENDING_PUBLIC_FIELD=" + key)
    print("FR_FINANCE_M29000_AUDIT=PASS")
    print("PRODUCTION_AUTHORIZATION=NOT_GRANTED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        # Never print exception text: it could include a public or secret value
        # unexpectedly supplied in a malformed input.
        print("FR_FINANCE_M29000_AUDIT=BLOCKED_INVALID_INPUT", file=sys.stderr)
        raise SystemExit(2) from None
