"""M17000: inbox page/cursor integrity, not a live DB or delivery adapter.

Use only after independent HTTP authentication and tenant-scoped SQL.
The caller is responsible for querying PostgreSQL using the authenticated
session; a validated preview never proves those prerequisites were met.
"""
from __future__ import annotations
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
from re import fullmatch
from typing import Mapping
from uuid import UUID

from .notifications_policy import NoticeKind, NoticeRole
from .pix_automation_contract import FinancialOperationBlocked

CONTRACT = "AI_STUDIO_M17000_NOTIFICATION_PAGE_CURSOR_OFFLINE_V1"
DOMAIN = b"AI_STUDIO_M17000_INBOX_CURSOR_ONLY\n"
CURSOR_TTL_SECONDS = 900
MAX_PAGE_SIZE = 50
MAX_TOKEN_SIZE = 1400

_REQUIRED_FIELDS = frozenset((
    "id", "tenant_id", "recipient_user_id", "recipient_role", "kind",
    "title", "message", "created_at", "read_at",
))


@dataclass(frozen=True)
class RecipientScope:
    user_id: UUID
    role: NoticeRole
    tenant_id: UUID | None


@dataclass(frozen=True)
class NoticePagePreview:
    contract: str
    scope: dict[str, str | None]
    items: tuple[dict[str, str | None], ...]
    has_more: bool
    next_cursor: str | None
    unread_count: None = None
    inbox_api_connected: bool = False
    production_auth_verified: bool = False
    external_send_authorized: bool = False
    bank_reconciled: bool = False


def _strict_scope(scope: RecipientScope) -> None:
    if (
        type(scope) is not RecipientScope
        or type(scope.user_id) is not UUID or scope.user_id.int == 0
        or type(scope.role) is not NoticeRole
        or (scope.tenant_id is not None and (
            type(scope.tenant_id) is not UUID or scope.tenant_id.int == 0))
        or (scope.role is NoticeRole.MASTER) != (scope.tenant_id is None)
    ):
        raise FinancialOperationBlocked("Escopo de notificação inválido")


def _time(raw: datetime) -> datetime:
    if (type(raw) is not datetime or raw.tzinfo is None
            or raw.utcoffset() is None):
        raise FinancialOperationBlocked("Carimbo de data sem timezone")
    return raw.astimezone(timezone.utc)


def _iso(time: datetime) -> str:
    return time.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _scope_fields(scope: RecipientScope) -> dict[str, str | None]:
    return {
        "recipient_user_id": str(scope.user_id),
        "recipient_role": scope.role.value,
        "tenant_id": str(scope.tenant_id) if scope.tenant_id else None,
    }


def _check_key(secret: bytes, now: datetime) -> None:
    if type(secret) is not bytes or len(secret) < 32:
        raise FinancialOperationBlocked("Chave de cursor ausente ou insuficiente")
    _time(now)


def encode_cursor(
    scope: RecipientScope,
    last_time: datetime,
    last_id: UUID,
    *,
    secret: bytes,
    now: datetime,
) -> str:
    _strict_scope(scope)
    _check_key(secret, now)
    if type(last_id) is not UUID or last_id.int == 0:
        raise FinancialOperationBlocked("UUID do cursor inválido")
    payload = dict(
        version=1,
        issued_at=_iso(_time(now)),
        last_at=_iso(_time(last_time)),
        last_id=str(last_id),
        **_scope_fields(scope),
    )
    data = _json(payload)
    sig = hmac.new(secret, DOMAIN+data, sha256).hexdigest()
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")+"."+sig


def decode_cursor(
    token: str, scope: RecipientScope, *,
    secret: bytes, now: datetime,
) -> tuple[datetime, UUID]:
    _strict_scope(scope)
    _check_key(secret, now)
    if (type(token) is not str or len(token) > MAX_TOKEN_SIZE
            or token.count(".") != 1):
        raise FinancialOperationBlocked("Cursor inválido")
    encoded, signature = token.split(".")
    if (not fullmatch(r"[A-Za-z0-9_-]+", encoded)
            or not fullmatch(r"[a-f0-9]{64}", signature)):
        raise FinancialOperationBlocked("Assinatura de cursor inválida")
    try:
        data = base64.b64decode(encoded+"="*((-len(encoded))%4),
                                altchars=b"-_", validate=True)
        if base64.urlsafe_b64encode(data).decode("ascii").rstrip("=") != encoded:
            raise ValueError("noncanonical base64")
        expected = hmac.new(secret, DOMAIN+data, sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("invalid cursor HMAC")
        payload = json.loads(data)
        if (type(payload) is not dict
                or frozenset(payload) != frozenset((
                    "version","issued_at","last_at","last_id",
                    "recipient_user_id","recipient_role","tenant_id"))
                or type(payload["version"]) is not int or payload["version"] != 1
                or any(payload[k] != v for k,v in _scope_fields(scope).items())):
            raise ValueError("wrong cursor scope")
        issued = datetime.fromisoformat(payload["issued_at"].replace("Z","+00:00"))
        last = datetime.fromisoformat(payload["last_at"].replace("Z","+00:00"))
        if (payload["issued_at"] != _iso(_time(issued))
                or payload["last_at"] != _iso(_time(last))):
            raise ValueError("noncanonical cursor time")
        age = (_time(now)-_time(issued)).total_seconds()
        if age < -30 or age > CURSOR_TTL_SECONDS:
            raise ValueError("expired cursor")
        uid = UUID(payload["last_id"])
        if str(uid) != payload["last_id"] or uid.int == 0:
            raise ValueError("bad cursor uuid")
        return _time(last), uid
    except (ValueError, TypeError, KeyError, UnicodeDecodeError,
            json.JSONDecodeError, OverflowError) as exc:
        raise FinancialOperationBlocked("Cursor expirado ou de outro contexto") from exc


def preview_notification_page(
    raw_rows: tuple[Mapping[str, object], ...],
    scope: RecipientScope,
    *,
    secret: bytes,
    now: datetime,
    limit: int = 20,
    after: str | None = None,
) -> NoticePagePreview:
    _strict_scope(scope)
    _check_key(secret, now)
    if (type(raw_rows) is not tuple or type(limit) is not int
            or not 1 <= limit <= MAX_PAGE_SIZE or len(raw_rows) > limit+1):
        raise FinancialOperationBlocked("Página de notificações acima do limite")
    prior = decode_cursor(after, scope, secret=secret, now=now) if after else None
    seen: set[UUID] = set()
    normalized = []
    last_key: tuple[datetime, UUID] | None = None
    for record in raw_rows:
        if (not isinstance(record, Mapping)
                or frozenset(record.keys()) != _REQUIRED_FIELDS):
            raise FinancialOperationBlocked("Linha de notificação sem esquema íntegro")
        try:
            uid = record["id"]
            role = record["recipient_role"]
            kind = NoticeKind(record["kind"])
            title = record["title"]
            message = record["message"]
            read_at = record["read_at"]
            created_at = _time(record["created_at"])
            if (type(uid) is not UUID or uid.int == 0 or uid in seen
                    or type(record["recipient_user_id"]) is not UUID
                    or record["recipient_user_id"] != scope.user_id
                    or role != scope.role.value
                    or record["tenant_id"] != scope.tenant_id
                    or type(title) is not str or not 1 <= len(title) <= 100
                    or type(message) is not str or not 1 <= len(message) <= 280
                    or any(ord(c) < 32 for c in title+message)
                    or (read_at is not None and _time(read_at) < created_at)):
                raise ValueError("untrusted inbox row")
            order = (created_at, uid)
            if ((last_key is not None and not order < last_key)
                    or (prior is not None and not order < prior)):
                raise ValueError("out-of-order or replayed page")
        except (TypeError, ValueError, KeyError) as exc:
            raise FinancialOperationBlocked("Registro de notificação incompatível com sessão") from exc
        seen.add(uid)
        last_key = order
        normalized.append({
            "id":str(uid), "kind":kind.value, "title":title,
            "message":message, "created_at":_iso(created_at),
            "read_at":_iso(_time(read_at)) if read_at is not None else None,
        })
    has_more = len(normalized) > limit
    displayed = normalized[:limit]
    token = None
    if has_more:
        marker = raw_rows[limit-1]
        token = encode_cursor(
            scope, marker["created_at"], marker["id"],secret=secret,now=now
        )
    return NoticePagePreview(
        contract=CONTRACT,scope=_scope_fields(scope),
        items=tuple(displayed),has_more=has_more,next_cursor=token,
    )
