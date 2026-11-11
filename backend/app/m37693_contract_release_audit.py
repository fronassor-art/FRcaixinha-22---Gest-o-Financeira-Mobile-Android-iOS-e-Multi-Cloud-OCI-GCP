"""M37693-M37973: offline clause and release audit for FR Finance AI Studio.

The 147 clauses are a historical inventory, not current contract approval.
No database, network, secrets, provider or runtime state are inspected here.
A planned review task never constitutes a real-world approval.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import re

from .release_evidence_matrix import build_release_matrix
from .m37500_release_workplan import workplan

ROOT = Path(__file__).resolve().parents[2]
SOURCE_BRANCH = "atualizacao-ai-studio-9b46a63187"
START_CHECKPOINT = "1b1a68ccd688a26c01a6e4598083503727d5298d"
BASELINE_PATH = "docs/FR_FINANCE_M24000_CONTRACT_GAP_REGISTER_147.json"
DOCS = (
    ("CADERNO_MESTRE", "docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md", 29, 6),
    ("CONTRATO_TECNICO", "docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md", 28, 7),
)
EXPECTED_BASELINE = {"PARCIAL": 58, "BLOQUEADO": 50, "DIVERGENTE": 5, "NÃO VERIFICADO": 34}
PENDING = "PENDING_INDEPENDENT_EVIDENCE"
START = 37693
END = 37973
TOTAL = 281


def _current_requirements(root: Path) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    documents: list[dict] = []
    for family, path, expected_bullets, expected_sections in DOCS:
        raw = (root / path).read_bytes()
        content = raw.decode("utf-8")
        lines = content.splitlines()
        section = None
        sections: set[str] = set()
        count = 0
        for line_number, line in enumerate(lines, 1):
            if line.startswith("## "):
                section = line[3:].strip()
                sections.add(section)
            if line.startswith("- "):
                if section is None:
                    raise ValueError("M37693_DOCUMENT_SECTION_MISSING")
                count += 1
                items.append({
                    "kind": "CURRENT_DOCUMENT_REQUIREMENT",
                    "source_id": f"{family}-{count:02d}",
                    "title": line[2:].strip(),
                    "section": section,
                    "source_path": path,
                    "source_line": line_number,
                    "baseline_status": None,
                    "review_status": PENDING,
                    "required_evidence": "Revisão individual do requisito, teste pertinente e evidência independente de aceite quando aplicável",
                })
        if count != expected_bullets or len(sections) != expected_sections:
            raise ValueError(f"M37693_CURRENT_DOCUMENT_DRIFT_{family}")
        documents.append({
            "family": family, "path": path, "sha256": sha256(raw).hexdigest(),
            "requirements": count, "sections": len(sections),
            "status": "SOURCE_READ_ONLY_NOT_REAL_ATTESTATION",
        })
    if len(items) != 57:
        raise ValueError("M37693_DOCUMENT_REQUIREMENT_COUNT_DRIFT")
    return items, documents


def _historical_requirements(root: Path) -> tuple[list[dict], dict]:
    baseline = json.loads((root / BASELINE_PATH).read_text(encoding="utf-8"))
    if not isinstance(baseline, dict) or baseline.get("kind") != "HISTORICAL_BASELINE_NOT_CURRENT_COMPLIANCE":
        raise ValueError("M37693_BASELINE_IDENTITY_INVALID")
    clauses = baseline.get("clauses")
    if not isinstance(clauses, list) or len(clauses) != 147:
        raise ValueError("M37693_BASELINE_147_REQUIRED")
    ids = [x.get("id") for x in clauses]
    if not all(isinstance(i, str) and i for i in ids) or len(set(ids)) != 147:
        raise ValueError("M37693_BASELINE_ID_DRIFT")
    counts = dict(Counter(x.get("baseline_status") for x in clauses))
    if counts != EXPECTED_BASELINE or baseline.get("counts") != EXPECTED_BASELINE:
        raise ValueError("M37693_BASELINE_STATUS_DRIFT")
    if baseline.get("production_release_authorized") is not False or any(
        x.get("production_verified") is not False
        or x.get("review_state") != "AWAITING_CLAUSE_EVIDENCE"
        for x in clauses
    ):
        raise ValueError("M37693_UNTRUSTED_CLAUSE_PROMOTION")
    tasks = [{
        "kind": "HISTORICAL_CLAUSE_REVIEW",
        "source_id": x["id"],
        "title": x["name"],
        "source_path": BASELINE_PATH,
        "source_hint": x.get("source_hint", ""),
        "section": x.get("workstream", ""),
        "baseline_status": x["baseline_status"],
        "review_status": PENDING,
        "required_evidence": x.get("required_evidence", ""),
        "remaining_evidence": x.get("remaining_evidence", ""),
    } for x in clauses]
    return tasks, baseline


def audit_checkpoint(root: Path = ROOT) -> dict:
    """Generate exactly 281 pending checks without issuing any authority."""
    current, documents = _current_requirements(root)
    historical, baseline = _historical_requirements(root)
    matrix = build_release_matrix(contract_baseline=baseline)
    if matrix["gate_count"] != 20 or matrix["provider_gate_count"] != 7:
        raise ValueError("M37693_RELEASE_MATRIX_DRIFT")
    previous = workplan()
    if len(previous) != 192 or previous[0].task_id != "M37501" or previous[-1].task_id != "M37692":
        raise ValueError("M37693_PREVIOUS_PLAN_DRIFT")

    checks = current + historical
    checks.extend({
        "kind": "LIVE_RELEASE_GATE",
        "source_id": gate["id"], "title": gate["id"],
        "source_path": "backend/app/release_evidence_matrix.py",
        "section": gate["category"],
        "baseline_status": None, "review_status": PENDING,
        "required_evidence": gate["required_evidence"],
        "acceptance_proof": gate["acceptance_proof"],
    } for gate in matrix["gates"])
    checks.extend({
        "kind": "EXTERNAL_PROVIDER_GATE",
        "source_id": gate["id"], "title": gate["id"],
        "source_path": "backend/app/operator_release_worklist.py",
        "section": "EXTERNAL_PROVIDER",
        "baseline_status": None, "review_status": PENDING,
        "required_evidence": "Comprovação independente do provedor, proprietário e operação em staging",
    } for gate in matrix["provider_gates"])
    checks.extend({
        "kind": "ACCEPTANCE_SCENARIO",
        "source_id": f"AT-{n:02d}",
        "title": f"Executar e evidenciar cenário AT-{n:02d} segundo o documento histórico aprovado",
        "source_path": "docs/CHECKPOINT_CONTRATO_2026-11-01.md",
        "section": "AT_01_50",
        "baseline_status": None, "review_status": PENDING,
        "required_evidence": "Resultado E2E reproduzível, referência à versão do contrato e aceite independente",
    } for n in range(1, 51))

    if len(checks) != TOTAL:
        raise ValueError("M37693_AUDIT_TASK_COUNT_DRIFT")
    tasks = [{**item, "task_id": f"M{START + i}", "production_verified": False}
             for i, item in enumerate(checks)]
    if tasks[-1]["task_id"] != f"M{END}" or len(set(x["task_id"] for x in tasks)) != TOTAL:
        raise ValueError("M37693_TASK_SEQUENCE_DRIFT")

    return {
        "project": "FR_FINANCE_AI_STUDIO_ONLY",
        "source_branch": SOURCE_BRANCH,
        "start_checkpoint": START_CHECKPOINT,
        "package": "M37693_M37973",
        "mode": "OFFLINE_READ_ONLY_NO_PROVIDER_NO_DATABASE",
        "status": "PRODUCTION_NOT_AUTHORIZED",
        "production_ready": False,
        "homologation_stage": "TECHNICAL_OFFLINE_COMPLETE_STAGING_E2E_PENDING",
        "current_documents": documents,
        "current_document_requirements_pending": 57,
        "historical_clauses_pending": 147,
        "historical_baseline_counts": dict(sorted(EXPECTED_BASELINE.items())),
        "historical_divergent_ids": [x["source_id"] for x in historical if x["baseline_status"] == "DIVERGENTE"],
        "live_release_gates_verified": 0, "live_release_gates_total": 20,
        "provider_gates_verified": 0, "provider_gates_total": 7,
        "acceptance_scenarios_real_attested": 0, "acceptance_scenarios_total": 50,
        "previous_plan_tasks_planned": 192,
        "new_review_tasks_planned": TOTAL,
        "new_review_tasks_real_verified": 0,
        "operational_proof_fetched": False,
        "cloud_mutations_performed": False,
        "postgresql_original_accessed": False,
        "sql_migrations_applied": False,
        "real_user_activation_authorized": False,
        "real_pix_authorized": False,
        "real_payment_authorized": False,
        "real_loan_authorized": False,
        "tasks": tasks,
    }


def checklist_markdown(report: dict) -> str:
    """Render a copyable checklist. Does not write files."""
    if report.get("status") != "PRODUCTION_NOT_AUTHORIZED" or len(report.get("tasks", [])) != TOTAL:
        raise ValueError("M37693_CHECKLIST_REQUIRES_VERIFIED_OFFLINE_REPORT")
    lines = [
        "# FR Finance — M37693-M37973 | Checklist contratual e de produção",
        "",
        "Estado: NÃO AUTORIZADO para produção, Pix, pagamentos, crédito ou contas reais.",
        "Os 147 registros são históricos; as 57 regras atuais e todas as evidências estão pendentes de validação item a item.",
        "",
    ]
    current_kind = None
    for t in report["tasks"]:
        if t["kind"] != current_kind:
            current_kind = t["kind"]
            lines.extend(["", "## " + current_kind, ""])
        title = " ".join(str(t["title"]).split())
        lines.append(f"- [ ] {t['task_id']} | {t['source_id']} | {title} | {t['review_status']}")
    lines.extend(["", "## Decisão", "", "- [ ] Parecer jurídico/regulatório independente", "- [ ] Aprovação operacional, segurança e produto independente", "- [ ] Evidência E2E de staging e registro formal GO/NO-GO; nenhuma ativação automática", ""])
    return "\n".join(lines)
