"""M38990 FR Finance: real, opt-in transactional mail outbox on ONE existing PG18.

This module does not create DBs, schemas, roles, directories or FastAPI apps.
M047 must already have been reviewed and applied to the SAME original database.
The live app does not install this module by default. Secrets never reach logs.
Never confuse SMTP submission with recipient verification or account activation.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import HTTPException

from .access_delivery_binding import AccessDeliveryBinding, AccessDeliveryReceipt
from .config import safe_public_https_origin
from .dependencies import auth_database_url
from .onboarding_mail_transport import (
    MailConfigurationBlocked, MailSubmissionFailed,
    SmtpSubmissionConfig, submit_access_message, verify_smtp_configuration,
    _mailbox,
)

_ORIGINAL_DB = "frcaixinha_aistudio_dev"
_ORIGINAL_HOST = "127.0.0.1"
_ORIGINAL_PORT = 5433
_UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\Z")
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+\Z")
_STATEMENTS = {
    "invite": (
        "SELECT public.frfinance_enqueue_member_invite("
        "$1::uuid,$2::uuid,$3::uuid,$4::uuid,"
        "$5::varchar,$6::char(64),$7::char(64),$8::char(64),$9::bytea)"
    ),
    "reset": (
        "SELECT public.frfinance_enqueue_password_reset("
        "$1::uuid,$2::varchar,$3::char(64),$4::char(64),$5::char(64),$6::bytea)"
    ),
    "claim": "SELECT * FROM public.frfinance_claim_access_mail()",
    "ack": "SELECT public.frfinance_ack_access_mail($1::uuid,$2::boolean)",
    "verify_invite": "SELECT public.frfinance_verify_invite_email($1::char(64))",
    "consume_reset": "SELECT public.frfinance_redeem_reset_token($1::char(64),$2::varchar(255))",
}


class AccessQueueBlocked(RuntimeError):
    pass


@dataclass(frozen=True, repr=False)
class AccessQueueConfig:
    dsn: str = field(repr=False)
    encryption_key: bytes = field(repr=False)
    hmac_key: bytes = field(repr=False)
    smtp: SmtpSubmissionConfig = field(repr=False)

    def __repr__(self) -> str:
        return "AccessQueueConfig(redacted=True, single_existing_db=True)"


def _email(raw: str) -> str:
    if (type(raw) is not str or raw != raw.strip()
            or not 5 <= len(raw) <= 254
            or any(ord(c) > 127 for c in raw)):
        raise AccessQueueBlocked("MAILBOX_INVALID")
    result = raw.lower()
    if not _EMAIL.fullmatch(result):
        raise AccessQueueBlocked("MAILBOX_INVALID")
    try:
        return _mailbox(result)  # identical syntax gate as existing Brevo adapter
    except MailConfigurationBlocked:
        raise AccessQueueBlocked("MAILBOX_INVALID") from None


def _key(value: str, *, raw: bool = False) -> bytes:
    if raw:
        if not isinstance(value, str) or len(value.encode("utf-8")) < 32:
            raise AccessQueueBlocked("SECRET_UNAVAILABLE")
        return value.encode("utf-8")
    try:
        data = base64.b64decode(value, validate=True)
    except (ValueError, TypeError):
        raise AccessQueueBlocked("ENCRYPTION_KEY_INVALID") from None
    if len(data) != 32:
        raise AccessQueueBlocked("ENCRYPTION_KEY_INVALID")
    return data


def require_reviewed_config(env: Mapping[str, str]) -> AccessQueueConfig:
    """Explicit local approval + existing auth role + public APP_URL syntax.

    The flags reflect the operator's deployment review, not independent proof
    of DNS, SMTP or bank state. No real user is activated by this component.
    """
    if (env.get("FR_FINANCE_ACCESS_MAIL_ENABLE") != "REVIEWED_SINGLE_DB"
            or env.get("FR_FINANCE_OUTBOX_047_VERIFIED") != "YES"
            or env.get("FR_FINANCE_SMTP_OPERATOR_APPROVED") != "YES"
            or env.get("ENVIRONMENT") != "homologation"
            or env.get("FRCAIXINHA_TERMUX_LOCAL_API") != "1"
            or safe_public_https_origin(env.get("APP_URL", "")) is None):
        raise AccessQueueBlocked("ACCESS_DELIVERY_NOT_AUTHORIZED")
    dsn = env.get("AUTH_DATABASE_URL", "")
    try:
        parsed = urlsplit(dsn)
        if (parsed.scheme != "postgresql"
                or parsed.hostname != _ORIGINAL_HOST
                or parsed.port != _ORIGINAL_PORT
                or parsed.path != "/" + _ORIGINAL_DB
                or parsed.username != "frc_ai_auth"
                or not parsed.password or parsed.query or parsed.fragment):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise AccessQueueBlocked("ORIGINAL_POSTGRES_IDENTITY_INVALID") from None
    enc = _key(env.get("FR_FINANCE_ACCESS_ENCRYPTION_KEY_B64", ""))
    pepper = _key(env.get("FR_FINANCE_ACCESS_HMAC_KEY", ""), raw=True)
    if hmac.compare_digest(enc, pepper):
        raise AccessQueueBlocked("SECRET_REUSE_DENIED")
    try:
        smtp = verify_smtp_configuration(env)
    except MailConfigurationBlocked:
        raise AccessQueueBlocked("SMTP_CONFIG_INVALID") from None
    return AccessQueueConfig(dsn=dsn, encryption_key=enc,
                             hmac_key=pepper, smtp=smtp)


def _digest(config: AccessQueueConfig, purpose: str, value: str) -> str:
    return hmac.new(
        config.hmac_key, (purpose + ":" + value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _sealed(config: AccessQueueConfig, *, event: UUID, kind: str,
            recipient: str, token: str) -> bytes:
    nonce = secrets.token_bytes(12)
    payload = json.dumps(
        {"recipient": recipient, "token": token, "reset": kind == "RESET"},
        separators=(",", ":"), ensure_ascii=True,
    ).encode("ascii")
    associated = (str(event) + ":" + kind).encode("ascii")
    return nonce + AESGCM(config.encryption_key).encrypt(nonce, payload, associated)


def _unseal(config: AccessQueueConfig, *, event: UUID, kind: str,
            ciphertext: bytes) -> tuple[str, str]:
    if (type(event) is not UUID or kind not in ("RESET", "INVITE_MEMBER")
            or type(ciphertext) is not bytes or not 44 <= len(ciphertext) <= 8192):
        raise AccessQueueBlocked("OUTBOX_PAYLOAD_INVALID")
    try:
        nonce, data = ciphertext[:12], ciphertext[12:]
        associated = (str(event) + ":" + kind).encode("ascii")
        raw = AESGCM(config.encryption_key).decrypt(nonce, data, associated)
        payload = json.loads(raw)
        recipient = _email(payload["recipient"])
        token = payload["token"]
        if (type(payload) is not dict
                or set(payload) != {"recipient", "token", "reset"}
                or payload["reset"] != (kind == "RESET")
                or type(token) is not str
                or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", token)):
            raise ValueError()
        return recipient, token
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise AccessQueueBlocked("OUTBOX_PAYLOAD_INVALID") from None
    except Exception:
        raise AccessQueueBlocked("OUTBOX_DECRYPT_FAILED") from None


async def _connect(config: AccessQueueConfig):
    try:
        return await asyncpg.connect(config.dsn, timeout=5)
    except (asyncpg.PostgresError, OSError, asyncio.TimeoutError):
        raise AccessQueueBlocked("ORIGINAL_DB_CONNECTION_FAILED") from None


async def verify_existing_schema(config: AccessQueueConfig) -> None:
    """Read only original DB, queue RLS and SQL functions; no schema mutations."""
    db = await _connect(config)
    try:
        row = await db.fetchrow(
            "SELECT current_database() AS db,session_user AS role,"
            "inet_server_port() AS port,"
            "current_setting('server_version_num')::integer AS ver,"
            "EXISTS(SELECT 1 FROM pg_class "
            " WHERE oid=to_regclass('public.frfinance_access_delivery_outbox') "
            " AND relrowsecurity AND relforcerowsecurity) AS rls,"
            "to_regprocedure('public.frfinance_enqueue_member_invite("
            "uuid,uuid,uuid,uuid,character varying,character,character,character,bytea"
            ")') IS NOT NULL AS invite,"
            "to_regprocedure('public.frfinance_enqueue_password_reset("
            "uuid,character varying,character,character,character,bytea"
            ")') IS NOT NULL AS reset"
        )
        if (not row or row["db"] != _ORIGINAL_DB
                or row["role"] != "frc_ai_auth"
                or row["port"] != _ORIGINAL_PORT
                or not 180000 <= row["ver"] < 190000
                or row["rls"] is not True
                or row["invite"] is not True
                or row["reset"] is not True):
            raise AccessQueueBlocked("ORIGINAL_ACCESS_SCHEMA_NOT_ATTESTED")
    except asyncpg.PostgresError:
        raise AccessQueueBlocked("ORIGINAL_ACCESS_SCHEMA_NOT_ATTESTED") from None
    finally:
        await db.close()



def _verified_access_token(raw: str) -> str:
    """Validate only opaque URL-safe access tokens; never print or persist raw."""
    if type(raw) is not str or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", raw):
        raise AccessQueueBlocked("ACCESS_TOKEN_INVALID")
    return hashlib.sha256(raw.encode("ascii")).hexdigest()


async def verify_existing_redemption_schema(config: AccessQueueConfig) -> None:
    """M048: attest original DB/version and exact least-privilege function grants.

    A non-superuser auth connection cannot reliably read the restricted
    PostgreSQL data_directory setting. The original PGDATA was already
    verified under frc_ai_owner when M048 was applied (M38994); here we
    verify its ORIGINAL TCP endpoint, database, role and installed functions
    without acquiring extra privileges or touching schema/data.
    """
    db = await _connect(config)
    try:
        row = await db.fetchrow(
            "SELECT current_database() AS db,"
            "session_user AS login_role,current_user AS active_role,"
            "inet_server_port() AS port,"
            "current_setting('server_version_num')::integer AS ver,"
            "to_regprocedure('public.frfinance_verify_invite_email(character)') "
            "IS NOT NULL AS invite,"
            "to_regprocedure('public.frfinance_redeem_reset_token("
            "character,character varying)') IS NOT NULL AS reset,"
            "has_function_privilege('frc_ai_auth',"
            "'public.frfinance_verify_invite_email(character)','EXECUTE') "
            "AS auth_invite,"
            "has_function_privilege('frc_ai_auth',"
            "'public.frfinance_redeem_reset_token(character,character varying)',"
            "'EXECUTE') AS auth_reset,"
            "has_function_privilege('frc_ai_app',"
            "'public.frfinance_verify_invite_email(character)','EXECUTE') "
            "AS app_invite,"
            "has_function_privilege('frc_ai_app',"
            "'public.frfinance_redeem_reset_token(character,character varying)',"
            "'EXECUTE') AS app_reset"
        )
        if (not row or row["db"] != _ORIGINAL_DB
                or row["login_role"] != "frc_ai_auth"
                or row["active_role"] != "frc_ai_auth"
                or row["port"] != _ORIGINAL_PORT
                or not 180000 <= row["ver"] < 190000
                or row["invite"] is not True
                or row["reset"] is not True
                or row["auth_invite"] is not True
                or row["auth_reset"] is not True
                or row["app_invite"] is not False
                or row["app_reset"] is not False):
            raise AccessQueueBlocked("M048_REDEMPTION_NOT_ATTESTED")
    except asyncpg.PostgresError:
        # Do not put SQL details or credentials into app/user logs.
        raise AccessQueueBlocked("M048_REDEMPTION_NOT_ATTESTED") from None
    finally:
        await db.close()


class Pg18AccessDelivery:
    def __init__(self, config: AccessQueueConfig):
        self.config = config

    async def invite(self, *, session, payload) -> AccessDeliveryReceipt:
        from .dependencies import AuthenticatedSession
        if (type(session) is not AuthenticatedSession
                or session.role != "TENANT_ADMIN"
                or session.verification_source != "POSTGRES_TOKEN_HASH_REFRESH"
                or not session.verified_session_id
                or not session.tenant_id
                or not payload.tenant_id
                or session.tenant_id != str(payload.tenant_id)
                or not payload.required_document_id):
            raise HTTPException(403, "Sessão administrativa não verificada.")
        try:
            session_id = UUID(session.verified_session_id)
            tenant_id = UUID(session.tenant_id)
            doc_id = UUID(str(payload.required_document_id))
            recipient = _email(str(payload.target_email))
        except (ValueError, TypeError, AccessQueueBlocked):
            raise HTTPException(422, "Convite inválido.") from None
        event, token = uuid4(), secrets.token_urlsafe(48)
        envelope = _sealed(self.config, event=event, kind="INVITE_MEMBER",
                           recipient=recipient, token=token)
        db = await _connect(self.config)
        try:
            async with db.transaction():
                accepted = await db.fetchval(
                    _STATEMENTS["invite"], event, session_id, tenant_id, doc_id,
                    recipient, hashlib.sha256(token.encode("ascii")).hexdigest(),
                    _digest(self.config, "email", recipient),
                    _digest(self.config, "source", str(session_id)), envelope,
                )
                if accepted is not True:
                    raise AccessQueueBlocked("INVITE_NOT_COMMITTED")
        except (asyncpg.PostgresError, AccessQueueBlocked):
            raise HTTPException(503, "Convite não registrado no banco original.") from None
        finally:
            await db.close()
        return AccessDeliveryReceipt(event_id=event, persisted=True,
                                     durable_outbox_queued=True)

    async def reset(self, *, email: str, source_ip: str = "") -> AccessDeliveryReceipt:
        try:
            recipient = _email(email)
        except AccessQueueBlocked:
            raise HTTPException(422, "Solicitação inválida.") from None
        if not isinstance(source_ip, str) or len(source_ip) > 128:
            raise HTTPException(503, "Origem da solicitação inválida.")
        event, token = uuid4(), secrets.token_urlsafe(48)
        envelope = _sealed(self.config, event=event, kind="RESET",
                           recipient=recipient, token=token)
        db = await _connect(self.config)
        try:
            async with db.transaction():
                accepted = await db.fetchval(
                    _STATEMENTS["reset"], event, recipient,
                    hashlib.sha256(token.encode("ascii")).hexdigest(),
                    _digest(self.config, "email", recipient),
                    _digest(self.config, "origin", source_ip or "unknown"),
                    envelope,
                )
                if accepted is not True:
                    raise AccessQueueBlocked("RESET_NOT_COMMITTED")
        except (asyncpg.PostgresError, AccessQueueBlocked):
            raise HTTPException(503, "Recuperação não registrada.") from None
        finally:
            await db.close()
        return AccessDeliveryReceipt(event_id=event, persisted=True,
                                     durable_outbox_queued=True)

    async def verify_invitation_email(self, *, token: str) -> bool:
        try:
            token_digest = _verified_access_token(token)
        except AccessQueueBlocked:
            raise HTTPException(400, "Convite inválido ou expirado.") from None
        db = await _connect(self.config)
        try:
            async with db.transaction():
                return await db.fetchval(_STATEMENTS["verify_invite"], token_digest) is True
        except asyncpg.PostgresError:
            raise HTTPException(503, "Verificação de e-mail indisponível.") from None
        finally:
            await db.close()

    async def complete_password_reset(self, *, token: str, new_password: str) -> bool:
        try:
            token_digest = _verified_access_token(token)
        except AccessQueueBlocked:
            raise HTTPException(400, "Link de recuperação inválido ou expirado.") from None
        if (type(new_password) is not str
                or not 12 <= len(new_password) <= 128
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in new_password)
                or new_password != new_password.strip()):
            raise HTTPException(422, "Escolha uma senha de 12 a 128 caracteres.")
        from .security import hash_password_secure
        try:
            encrypted_password = await asyncio.to_thread(
                hash_password_secure, new_password,
            )
        except (RuntimeError, ValueError):
            raise HTTPException(503, "Proteção de senhas indisponível.") from None
        # No bcrypt fallback for new recovery passwords; enforce Argon2id.
        if not (type(encrypted_password) is str
                and encrypted_password.startswith("$argon2id$")
                and 80 <= len(encrypted_password) <= 255):
            raise HTTPException(503, "Proteção Argon2id indisponível.")
        db = await _connect(self.config)
        try:
            async with db.transaction():
                return (await db.fetchval(
                    _STATEMENTS["consume_reset"],
                    token_digest, encrypted_password,
                )) is True
        except asyncpg.PostgresError:
            raise HTTPException(503, "Recuperação de senha indisponível.") from None
        finally:
            await db.close()

    async def dispatch_one(self) -> str:
        """Post-commit Brevo SMTP submission. Unknown result -> QUARANTINE, no
        blind retries; a worker never activates accounts or credits money.
        """
        db = await _connect(self.config)
        try:
            row = await db.fetchrow(_STATEMENTS["claim"])
        except asyncpg.PostgresError:
            raise AccessQueueBlocked("OUTBOX_CLAIM_FAILED") from None
        finally:
            await db.close()
        if not row:
            return "IDLE"
        event = row["event_id"]
        submitted = False
        try:
            if row["expires_at"].timestamp() <= __import__("time").time():
                raise AccessQueueBlocked("OUTBOX_EXPIRED")
            recipient, token = _unseal(
                self.config, event=event, kind=row["kind"],
                ciphertext=bytes(row["sealed_message"]),
            )
            result = await asyncio.to_thread(
                submit_access_message, config=self.config.smtp,
                recipient=recipient, token=token,
                reset=row["kind"] == "RESET",
            )
            submitted = result.smtp_accepted is True
        except (AccessQueueBlocked, MailSubmissionFailed, MailConfigurationBlocked):
            submitted = False
        db = await _connect(self.config)
        try:
            acknowledged = await db.fetchval(_STATEMENTS["ack"], event, submitted)
            if acknowledged is not True:
                raise AccessQueueBlocked("OUTBOX_ACK_NOT_CONFIRMED")
        except asyncpg.PostgresError:
            raise AccessQueueBlocked("OUTBOX_ACK_NOT_CONFIRMED") from None
        finally:
            await db.close()
        return "SMTP_ACCEPTED_NOT_DELIVERED" if submitted else "QUARANTINED_NO_RETRY"


async def install_existing_access_delivery(app, env: Mapping[str, str]) -> bool:
    """No-op unless explicitly reviewed; original app.state, not a new API."""
    if env.get("FR_FINANCE_ACCESS_MAIL_ENABLE") != "REVIEWED_SINGLE_DB":
        return False
    config = require_reviewed_config(env)
    await verify_existing_schema(config)
    service = Pg18AccessDelivery(config)
    redemption_approved = env.get("FR_FINANCE_ACCESS_REDEMPTION_048_VERIFIED") == "YES"
    if redemption_approved:
        await verify_existing_redemption_schema(config)
    app.state.access_delivery_runtime = AccessDeliveryBinding(
        invite=service.invite,
        reset=service.reset,
        verify_invitation_email=service.verify_invitation_email if redemption_approved else None,
        complete_password_reset=service.complete_password_reset if redemption_approved else None,
        original_db_verified=True,
        segregated_worker_verified=True,
        durable_outbox_verified=True,
        scoped_audit_verified=True,
        smtp_credential_protected=True,
        external_delivery_authorized=True,
    )
    # Does not start a daemon. Explicit operator enables post-commit worker.
    if env.get("FR_FINANCE_ACCESS_MAIL_WORKER") == "EXPLICITLY_APPROVED":
        app.state.access_delivery_worker = service
    return True
