"""M40963 public integrity manifest for draft contract models; GET-only, no DB."""
from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/public/contract-models", tags=["Modelos contratuais públicos"])

_MANIFEST_PATH = Path(__file__).with_name("contract_model_manifest_v22.json")
try:
    _MANIFEST = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
except (OSError, UnicodeError, json.JSONDecodeError) as exc:
    raise RuntimeError("FR_FINANCE_CONTRACT_MODEL_MANIFEST_UNAVAILABLE") from exc

_KINDS = {"SAAS_LICENSE", "MEMBER_ADHESION"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


def contract_model_manifest(kind: str) -> dict:
    """Return only the pinned digest for one generic, unpublished V2.2 model."""
    if type(kind) is not str or kind not in _KINDS:
        raise HTTPException(status_code=404, detail="Modelo contratual indisponível.")
    hashes = _MANIFEST.get("models")
    digest = hashes.get(kind) if type(hashes) is dict else None
    if (type(digest) is not str or not _SHA256.fullmatch(digest)
            or _MANIFEST.get("schema") != "FR_FINANCE_CONTRACT_MODEL_MANIFEST_V22"
            or _MANIFEST.get("version") != "2.2"
            or _MANIFEST.get("state") != "DRAFT_ONLY"
            or _MANIFEST.get("acceptance_enabled") is not False):
        raise HTTPException(status_code=503, detail="Integridade do modelo contratual indisponível.")
    return {
        "schema": _MANIFEST["schema"],
        "version": "2.2",
        "state": "DRAFT_ONLY",
        "acceptance_enabled": False,
        "kind": kind,
        "sha256": digest,
    }


@router.get("/v2.2/{kind}")
def read_contract_model_manifest(kind: str) -> dict:
    """Public integrity metadata only; no body, identity, DB, consent or action."""
    return contract_model_manifest(kind)
