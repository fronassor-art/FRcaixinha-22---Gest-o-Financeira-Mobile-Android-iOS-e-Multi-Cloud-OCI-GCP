"""M25400 — canonical UTF-8 contract content, read-only and fail-closed.

Contracts are installed separately under a server-managed, read-only directory,
with immutable filename <document UUID>.txt. The authenticated caller must
first pass a tenant/role guard and RLS checks of the published digest. No file
is a signature, an invitation, or evidence of the invited person's consent.
"""
from __future__ import annotations

import asyncio
import hmac
import os
from hashlib import sha256
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException

from .invitation_preflight import authorize_invitation_intent

MAX_BYTES = 65536


class ContractBodyUnavailable(Exception):
    """Do not leak filesystem layout or candidate contract body on failure."""


def _read_immutable_document(document_id: UUID, expected_digest: str, root_setting: str) -> str:
    if (not isinstance(document_id, UUID) or
            not isinstance(expected_digest, str) or
            len(expected_digest) != 64 or
            not all(c in "0123456789abcdef" for c in expected_digest)):
        raise ContractBodyUnavailable()
    if (not isinstance(root_setting, str) or not root_setting or
            root_setting != root_setting.strip() or
            not os.path.isabs(root_setting)):
        raise ContractBodyUnavailable()
    root = Path(root_setting)
    # Strict permissions: the app must not be able to replace published source
    # via world/group-writable directories or symlinked files.
    if root.is_symlink() or not root.is_dir():
        raise ContractBodyUnavailable()
    try:
        info = root.stat()
        if info.st_mode & 0o022:
            raise ContractBodyUnavailable()
        location = root / (str(document_id) + ".txt")
        if location.is_symlink() or not location.is_file():
            raise ContractBodyUnavailable()
        if location.stat().st_size > MAX_BYTES or location.stat().st_size < 1:
            raise ContractBodyUnavailable()
        # The stored document must be owned by a different OS user from the
        # FastAPI process in production, or root-managed in a secure deployment.
        # We independently require no write bits for anyone on the file.
        if location.stat().st_mode & 0o222:
            raise ContractBodyUnavailable()
        raw = location.read_bytes()
        if not (0 < len(raw) <= MAX_BYTES):
            raise ContractBodyUnavailable()
        if not hmac.compare_digest(sha256(raw).hexdigest(), expected_digest):
            raise ContractBodyUnavailable()
        return raw.decode("utf-8", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise ContractBodyUnavailable() from exc


async def load_published_contract_body(*, session, payload, conn,
                                       content_root: str | None = None) -> dict:
    """Read exact canonical text only after RLS verifies tenant and publication."""
    authorize_invitation_intent(session=session, payload=payload)
    if not isinstance(payload.tenant_id, UUID) or not isinstance(payload.required_document_id, UUID):
        raise HTTPException(status_code=422, detail="Referências documentais inválidas.")
    active = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM public.tenants "
        "WHERE id=$1::uuid AND status='ATIVO')", payload.tenant_id,
    )
    if not active:
        raise HTTPException(status_code=404, detail="Documento indisponível.")
    row = await conn.fetchrow(
        "SELECT id,version_label,sha256,published_at "
        "FROM public.contract_documents "
        "WHERE id=$1::uuid AND document_kind='TENANT_MEMBERSHIP' "
        "AND published_at IS NOT NULL", payload.required_document_id,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Documento indisponível.")
    root = content_root if content_root is not None else os.getenv("FR_FINANCE_CANONICAL_CONTRACT_DIR", "")
    try:
        content = await asyncio.to_thread(
            _read_immutable_document, payload.required_document_id,
            row["sha256"].strip(), root,
        )
    except ContractBodyUnavailable:
        raise HTTPException(status_code=503, detail="Texto canônico do contrato ainda indisponível.") from None
    return {
        "source": "PUBLISHED_CONTRACT_VERIFIED",
        "scope": "AI_STUDIO_CANONICAL_CONTRACT_BODY",
        "document_id": str(row["id"]),
        "version": row["version_label"],
        "sha256": row["sha256"].strip(),
        "published_at": row["published_at"].isoformat(),
        "contract_text": content,
        "integrity_verified": True,
        "body_available": True,
        "acceptance_recorded": False,
        "invitation_created": False,
        "activation_authorized": False,
        "writes_performed": False,
    }
