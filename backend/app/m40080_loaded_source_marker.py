"""M40080 — non-secret import-time source fingerprints for loaded FastAPI.

Import-time hashes are evidence of source files PRESENT when this module
was imported, not cryptographic proof of executed bytecode or Git commit.
They are deliberately frozen in memory, not refreshed per HTTP request.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT = "FR_FINANCE_M40080_LOADED_SOURCE_V1"


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


_MAIN_SHA = _sha(_ROOT / "app/main.py")
_REVIEW_SHA = _sha(_ROOT / "app/routers/exclusive_cashbox_review_gaps.py")
_MARKER_SHA = _sha(Path(__file__))


def import_fingerprint_payload() -> dict[str, object]:
    """Never read disk again here; never return credentials or process info."""
    return {
        "product": "FR Finance",
        "workstream": "AI_STUDIO",
        "contract": _CONTRACT,
        "source_fingerprints_captured_on_import": True,
        "main_py_sha256_at_import": _MAIN_SHA,
        "review_router_sha256_at_import": _REVIEW_SHA,
        "marker_py_sha256_at_import": _MARKER_SHA,
        "git_commit_verified": False,
        "executable_bytecode_attested": False,
        "process_owner_verified": False,
        "real_session_revocation_attested": False,
        "review_policy_ratified": False,
        "financial_approval_enabled": False,
        "pix_real_enabled": False,
        "production_authorized": False,
    }
