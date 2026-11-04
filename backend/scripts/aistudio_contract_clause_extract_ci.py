"""Read-only contract fingerprint and clause checks for AI Studio CI.

The two PDF assets are versioned in THIS project's repository. Their historical
filenames do not authorize touching the separate FRcaixinha 2.2 project.
"""
from __future__ import annotations
from hashlib import sha256
from pathlib import Path
import re
import unicodedata
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2] / "public/assets/aistudio"
PDFS = (
    ("FRcaixinha_2.2___Caderno_Mestre_LIMPO___147_cl_usulas_94d2a15c.pdf",
     "94d2a15c54d3f5982c09fe78762ae0f1c76e03fa644cb05a6404f5c7b2feb0f6", 57),
    ("FRcaixinha_2.2___Contrato_T_cnico_Mestre_ORIGINAL_LIMPO_7b28d5d5.pdf",
     "7b28d5d5cf773fb5c35194bce64ebfdfec4d67422bafac4595a6662b4f45f468", 38),
)
CLAUSES = (
    "6.2", "6.3", "6.4", "6.5", "6.6",
    "8.6", "10.1", "10.2", "10.3", "10.4", "10.5", "10.6",
)
SPECIAL = (
    "tres contribuicoes mensais consecutivas",
    "capital-dias",
    "principal",
    "mora",
    "multa",
    "saida regular",
    "lucro",
    "maiores restos",
)


def normalize(s: str) -> str:
    x = unicodedata.normalize("NFKD", s)
    x = "".join(c for c in x if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", x.casefold())


for filename, expected_sha, expected_pages in PDFS:
    target=ROOT / filename
    content=target.read_bytes()
    digest=sha256(content).hexdigest()
    if digest!=expected_sha:
        raise RuntimeError(f"FINGERPRINT_MISMATCH {filename}")
    pdf=PdfReader(str(target))
    if len(pdf.pages)!=expected_pages:
        raise RuntimeError(f"PAGE_COUNT_MISMATCH {filename}")
    txt=normalize(" ".join(p.extract_text(extraction_mode="layout") or ""
                           for p in pdf.pages))
    for item in CLAUSES+SPECIAL:
        if normalize(item) not in txt:
            raise RuntimeError(f"CONTRACT_CLAUSE_NOT_LOCATED {filename}: {item}")
    print(f"CONTRACT_FINGERPRINT=PASS sha256={digest} pages={len(pdf.pages)} "
          f"clauses={len(CLAUSES)} topics={len(SPECIAL)}")
print("CONTRACT_MASTER_AI_STUDIO_READONLY=PASS")
