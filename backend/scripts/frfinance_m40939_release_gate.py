#!/usr/bin/env python3
"""M40939 source-only, machine-checked supermacropacote release gate.

No runtime database access, network, subprocess, credential reads, imports
from app, migration, checkout, Termux change or process/service management.
It cannot approve real production: a valid manifest still returns NO_GO.
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/FR_FINANCE_M40939_SUPERMACRO_GATES.json"
BACKEND = ROOT / "backend/app/launch_readiness.py"
SECURITY_CRITICAL = {
    "M40570_GUC_SPOOF", "M40730_INDEPENDENT_ISSUER",
    "M40840_PRODUCTION_SQL_GATE", "MIGRATION_ORIGINAL_APPROVAL",
    "CI_ALL_REQUIRED_JOBS",
}
REQUIRED_STATUSES = {
    "BLOCKED_SECURITY", "BLOCKED_EXTERNAL", "BLOCKED_AUTHORIZATION",
    "CI_PENDING", "DONE_SOURCE_ONLY",
}


# M40957 — canonical source-plan boundaries. These are minimum constraints,
# not external attestations or an authority to enable any real operation.
EXPECTED_REPOSITORY = "fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
EXPECTED_BRANCH = "atualizacao-ai-studio-9b46a63187"
BLOCKED_STATUSES = {"BLOCKED_SECURITY", "BLOCKED_EXTERNAL", "BLOCKED_AUTHORIZATION"}
EXPECTED_PHASES = {
    "P0": ("Arquitetura SQL e segregacao Master", "BLOCKED_SECURITY"),
    "P1": ("Identidade, auditoria, antifraude e RLS", "BLOCKED_SECURITY"),
    "P2": ("Staging OCI, restore, CI e integracao", "BLOCKED_EXTERNAL"),
    "P3": ("Android release, operacao e UX", "BLOCKED_EXTERNAL"),
    "P4": ("Provedor, financeiro e juridico", "BLOCKED_EXTERNAL"),
    "P5": ("Migracao autorizada, sync Termux e homologacao fisica", "BLOCKED_AUTHORIZATION"),
}
REQUIRED_TASK_DEPENDENCIES = {
    "M40570_GUC_SPOOF": {"TENANT_RLS"},
    "M40730_INDEPENDENT_ISSUER": {"M40570_GUC_SPOOF"},
    "M40840_PRODUCTION_SQL_GATE": {"M40730_INDEPENDENT_ISSUER"},
    "M40930_MASTER_WRITE_HTTP": {} or set(),
    "M40936_ACL_DISPOSABLE": {"M40930_MASTER_WRITE_HTTP"},
    "M40937_MASTER_NO_GO_UI": {"M40930_MASTER_WRITE_HTTP"},
    "M40938_MASTER_HTTP_RBAC": {"M40937_MASTER_NO_GO_UI"},
    "CI_ALL_REQUIRED_JOBS": {"M40936_ACL_DISPOSABLE", "M40937_MASTER_NO_GO_UI", "M40938_MASTER_HTTP_RBAC"},
    "OCI_A1_STAGING_CAPACITY": {} or set(),
    "LEGAL_LGPD_REGULATORY": {"CANONICAL_CONTRACT"},
    "MIGRATION_ORIGINAL_APPROVAL": {"CI_ALL_REQUIRED_JOBS", "M40730_INDEPENDENT_ISSUER", "MIGRATION_PARITY"},
    "TERMUX_SOURCE_SYNC": {"CI_ALL_REQUIRED_JOBS"},
    "ANDROID_PHYSICAL_RETEST": {"ANDROID_RELEASE", "M40937_MASTER_NO_GO_UI"},
    "MERCADO_PAGO_EXTERNAL_APPROVAL": {"MP_CONNECT", "PIX_OUTBOUND"},
}
# Only these engineering tasks may currently carry a source-only completion.
SOURCE_ONLY_COMPLETABLE = {
    "M40930_MASTER_WRITE_HTTP", "M40936_ACL_DISPOSABLE",
    "M40937_MASTER_NO_GO_UI", "M40938_MASTER_HTTP_RBAC",
}


class GateInvalid(ValueError):
    pass


def expected_production_gate_ids() -> set[str]:
    tree = ast.parse(BACKEND.read_text(encoding="utf-8"))
    for statement in tree.body:
        if not isinstance(statement, ast.Assign):
            continue
        if any(isinstance(t, ast.Name) and t.id == "REQUIREMENTS"
               for t in statement.targets):
            requirements = ast.literal_eval(statement.value)
            return {record[0] for record in requirements}
    raise GateInvalid("M40939_NO_CANONICAL_LAUNCH_REQUIREMENTS")


def validate(source: dict) -> dict:
    if (not isinstance(source, dict) or source.get("version") != "M40939"
            or source.get("project") != "FR Finance"
            or source.get("repository") != EXPECTED_REPOSITORY
            or source.get("branch") != EXPECTED_BRANCH
            or source.get("evidence_level") != "SOURCE_CATALOG_AND_CI_OBSERVATIONS_NOT_LIVE_ATTESTATION"
            or source.get("release_decision") != "NO_GO"
            or source.get("production_enabled") is not False
            or source.get("original_database_migrations_authorized") is not False
            or source.get("original_database_writes_authorized") is not False
            or source.get("termux_sync_executed") is not False
            or any(source.get(key) != "OFF" for key in (
                "pix_real", "pagamentos_reais", "ativacao_real"))
            or not isinstance(source.get("production_gates"), list)
            or not isinstance(source.get("tasks"), list)):
        raise GateInvalid("M40939_RELEASE_FIELDS_MUST_BE_NO_GO")

    phases = source.get("phases")
    if (type(phases) is not list or len(phases) != len(EXPECTED_PHASES)
            or any(type(p) is not dict for p in phases)
            or [(p.get("id"), p.get("name"), p.get("status")) for p in phases]
               != [(key, *value) for key, value in EXPECTED_PHASES.items()]):
        raise GateInvalid("M40957_PHASE_POLICY_INVALID")

    gates = source["production_gates"]
    tasks = source["tasks"]
    if (len(gates) != 20 or len(tasks) < 12
            or any(not isinstance(x, dict) for x in gates + tasks)):
        raise GateInvalid("M40939_GATE_COUNTS_OR_SHAPE_INVALID")
    ids = [row.get("id") for row in gates + tasks]
    if (any(not isinstance(i, str) or not i.isidentifier() for i in ids)
            or len(set(ids)) != len(ids)):
        raise GateInvalid("M40939_DUPLICATE_OR_UNSAFE_TASK_IDS")
    if {g["id"] for g in gates} != expected_production_gate_ids():
        raise GateInvalid("M40939_MISSING_CANONICAL_PRODUCTION_GATE")
    for g in gates:
        if (type(g.get("status")) is not str
                or g.get("status") not in BLOCKED_STATUSES
                or "depends_on" in g
                or g.get("production_verified") is not False
                or g.get("requires_independent_attestation") is not True):
            raise GateInvalid("M40939_FALSE_PRODUCTION_ATTESTATION")
    for task in tasks:
        if (type(task.get("status")) is not str
                or task.get("status") not in REQUIRED_STATUSES
                or (task.get("status") == "DONE_SOURCE_ONLY"
                    and task["id"] not in SOURCE_ONLY_COMPLETABLE)
                or task.get("production_verified") is not False
                or not isinstance(task.get("next_action"), str)
                or len(task["next_action"]) < 20
                or not isinstance(task.get("depends_on"), list)):
            raise GateInvalid("M40939_TASK_STATUS_OR_ACTION_INVALID")
    lookup = {row["id"]: row for row in gates + tasks}
    if not REQUIRED_TASK_DEPENDENCIES.keys() <= {t["id"] for t in tasks}:
        raise GateInvalid("M40957_REQUIRED_TASK_MISSING")
    for task in tasks:
        deps = task["depends_on"]
        if (any(type(dep) is not str for dep in deps)
                or not REQUIRED_TASK_DEPENDENCIES.get(task["id"], set()) <= set(deps)):
            raise GateInvalid("M40957_REQUIRED_DEPENDENCY_MISSING_OR_INVALID")
    for critical in SECURITY_CRITICAL:
        if critical not in lookup or lookup[critical]["status"] not in {
            "BLOCKED_SECURITY", "BLOCKED_AUTHORIZATION", "CI_PENDING",
        }:
            raise GateInvalid("M40939_PREMATURE_CRITICAL_GATE_RELEASE")
    for task in tasks:
        if (len(set(task["depends_on"])) != len(task["depends_on"])
                or any(d not in lookup for d in task["depends_on"])):
            raise GateInvalid("M40939_UNRECOGNIZED_DEPENDENCY")
    done, visiting = set(), set()
    def visit(node: str) -> None:
        if node in visiting:
            raise GateInvalid("M40939_CYCLIC_DEPENDENCIES")
        if node in done:
            return
        visiting.add(node)
        for next_node in lookup[node].get("depends_on", []):
            visit(next_node)
        visiting.remove(node)
        done.add(node)
    for node in ids:
        visit(node)
    return {
        "M40939_DECISION":"NO_GO",
        "M40939_MANIFEST":"VALIDATED_SOURCE_ONLY",
        "M40939_PRODUCTION_GATES":len(gates),
        "M40939_EXTRA_TASKS":len(tasks),
        "M40939_BLOCKED_OR_CI_PENDING":sum(
            row["status"]!="DONE_SOURCE_ONLY" for row in gates+tasks),
        "M40939_ORIGINAL_DB":"NOT_ACCESSED",
        "M40939_TERMUX_SYNC":"NOT_PERFORMED",
        "M40939_MIGRATION":"NOT_AUTHORIZED",
        "M40939_PIX_REAL":"OFF",
        "M40939_PAGAMENTOS_REAIS":"OFF",
        "M40939_ATIVACAO_REAL":"OFF",
        "M40939_PRODUCTION":"BLOCKED",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FR Finance M40939 release gate")
    parser.add_argument("--mode",choices=("audit","approve-production"),default="audit")
    args = parser.parse_args(argv)
    try:
        summary = validate(json.loads(MANIFEST.read_text(encoding="utf-8")))
    except (OSError,ValueError,TypeError,SyntaxError,KeyError) as exc:
        print("M40939_MANIFEST=BLOCKED_INVALID_" + type(exc).__name__)
        return 2
    for key,value in summary.items():
        print(f"{key}={value}")
    if args.mode=="approve-production":
        print("M40939_APPROVAL=DENIED_EXTERNAL_ATTESTATION_REQUIRED")
        return 2
    return 0


if __name__=="__main__":
    raise SystemExit(main())
