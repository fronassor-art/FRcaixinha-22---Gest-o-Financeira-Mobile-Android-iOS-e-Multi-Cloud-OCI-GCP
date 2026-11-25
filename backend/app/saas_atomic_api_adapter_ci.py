"""M37465: CI-only adapter from SaaS API contract into the M37464 atomic DB function.

There is NO production factory, endpoint or payment entitlement writer here.
Only a disposable PostgreSQL worker role can execute the guarded function.
Server-bound authenticated principal, offer and bearer token are required;
the SQL function locks and rechecks canonical public.sessions in the SAME
transaction that records the synthetic contract transition.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime,timedelta
from hashlib import sha256
from typing import Mapping
from uuid import UUID
import re

from .dependencies import AuthenticatedSession
from .saas_acceptance_api_contract_ci import (
    CIPrincipal,CIPublishedOffer,CITransition,
    evaluate_api_contract_ci,APIContractDecision,
)

_HEX=re.compile(r"[0-9a-f]{64}\Z")
_ACTIONS=frozenset(("ISSUE","ACCEPT","PREPARE"))
_SQL=(
    "SELECT public.m37464_atomic_consent_ci("
    "%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"
)
_ALLOWED_ENV={
    "GITHUB_ACTIONS":"true",
    "FRCAIXINHA_CI_ISOLATED":"1",
    "ENVIRONMENT":"ci",
    "FR_FINANCE_SAAS_REAL":"OFF",
    "FR_FINANCE_PIX_REAL":"OFF",
}


def ci_environment(env: Mapping[str,str])->bool:
    return (all(env.get(k)==v for k,v in _ALLOWED_ENV.items())
        and env.get("FRCAIXINHA_TERMUX_LOCAL_API")!="1")


def _aware(x:object)->bool:
    return type(x) is datetime and x.tzinfo is not None and x.utcoffset() is not None


def _uuid(x:object)->bool:
    return type(x) is UUID and x.int!=0


def _parsed_id(value:object)->UUID|None:
    try:
        uid=UUID(value)
        return uid if str(uid)==value and uid.int else None
    except (ValueError,TypeError,AttributeError):
        return None


@dataclass(frozen=True)
class CIAtomicServerBinding:
    """All values must be assembled by the CI service after DB authentication."""
    verified_session_id: UUID
    administrator_id: UUID
    tenant_id: UUID
    verified_at: datetime
    expires_at: datetime
    token_sha256: str
    source: str = "CI_AUTH_TOKEN_HASH_SESSION_SERVER_ONLY"


class CIAtomicSQLExecutor:
    """Use only inside an already-open disposable PostgreSQL transaction."""
    def __init__(
        self, *, worker_conn, binding:CIAtomicServerBinding,
        authenticated_session:AuthenticatedSession,
        offer:CIPublishedOffer, env:Mapping[str,str],
        now:datetime,
    ):
        if not ci_environment(env):
            raise ValueError("M37465_DISPOSABLE_CI_ONLY")
        if (type(binding) is not CIAtomicServerBinding
            or binding.source!="CI_AUTH_TOKEN_HASH_SESSION_SERVER_ONLY"
            or type(authenticated_session) is not AuthenticatedSession
            or type(offer) is not CIPublishedOffer
            or not _aware(now)
            or not _aware(binding.verified_at)
            or not _aware(binding.expires_at)
            or not all(_uuid(x) for x in (
                binding.verified_session_id,binding.administrator_id,binding.tenant_id,
                offer.tenant_id,offer.document_id,offer.price_version_id))
            or not isinstance(binding.token_sha256,str)
            or _HEX.fullmatch(binding.token_sha256) is None
            or authenticated_session.verification_source!="POSTGRES_TOKEN_HASH_REFRESH"
            or authenticated_session.role!="TENANT_ADMIN"
            or authenticated_session.is_master is not False
            or _parsed_id(authenticated_session.user_id)!=binding.administrator_id
            or _parsed_id(authenticated_session.tenant_id)!=binding.tenant_id
            or _parsed_id(authenticated_session.verified_session_id)!=binding.verified_session_id
            or not _aware(authenticated_session.verified_session_at)
            or not _aware(authenticated_session.verified_session_expires_at)
            or authenticated_session.verified_session_at!=binding.verified_at
            or authenticated_session.verified_session_expires_at!=binding.expires_at
            or binding.verified_at>now
            or now-binding.verified_at>timedelta(minutes=5)
            or now>=binding.expires_at
            or offer.tenant_id!=binding.tenant_id
            or offer.source!="CI_SYNTHETIC_SERVER_OFFER_READBACK"
            or offer.state!="ACTIVE"
            or offer.billing_period not in ("MONTHLY","ANNUAL")
            or not _aware(offer.published_at)
            or offer.published_at>binding.verified_at
            or type(offer.price_cents) is not int or offer.price_cents<=0
            or not callable(getattr(worker_conn,"execute",None))):
            raise ValueError("M37465_UNTRUSTED_CI_SESSION_OR_OFFER")
        # The worker must be scoped to disposable CI. This check also
        # guards against accidental substitution with a local app DB.
        meta=worker_conn.execute(
            "SELECT current_database(),session_user,current_setting('is_superuser'),"
            "current_setting('frcaixinha.saas_atomic_ci',true),"
            "current_setting('frcaixinha.saas_preprep_ci',true),inet_server_port()"
        ).fetchone()
        if meta!=("frcaixinha_staging","frcaixinha_saas_preprep_ci","off","1","1",5432):
            raise ValueError("M37465_WRONG_DATABASE_OR_SQL_WORKER_ROLE")
        self._conn=worker_conn
        self._binding=binding
        self._offer=offer

    def transition(
        self, *, action:str,request_id:UUID,challenge_id:UUID,
        principal:CIPrincipal,offer:CIPublishedOffer,confirmation:str|None,
    )->CITransition:
        if (action not in _ACTIONS
            or not _uuid(request_id) or not _uuid(challenge_id)
            or type(principal) is not CIPrincipal
            or type(offer) is not CIPublishedOffer
            or principal.source!="CI_SYNTHETIC_SERVER_AUTH_READBACK"
            or principal.user_id!=self._binding.administrator_id
            or principal.tenant_id!=self._binding.tenant_id
            or principal.session_id!=self._binding.verified_session_id
            or principal.active_role!="TENANT_ADMIN"
            or principal.active is not True
            or principal.email_verified is not True
            or not _aware(principal.server_checked_at)
            or not _aware(principal.expires_at)
            or principal.server_checked_at!=self._binding.verified_at
            or principal.expires_at!=self._binding.expires_at
            or offer!=self._offer):
            return CITransition("DENIED_CI")
        if (action=="ACCEPT" and confirmation!="ACEITO_CONTRATO_DE_LICENCA_FR_FINANCE"
            or action!="ACCEPT" and confirmation is not None):
            return CITransition("DENIED_CI")
        row=self._conn.execute(_SQL,(
            action,self._binding.token_sha256,self._binding.verified_session_id,
            challenge_id,request_id,self._binding.tenant_id,
            self._binding.administrator_id,offer.document_id,
            offer.price_version_id,offer.billing_period,confirmation,
        )).fetchone()
        if not row or type(row[0]) is not str:
            return CITransition("DENIED_CI")
        return CITransition(row[0])


def derive_server_binding_ci(
    session:AuthenticatedSession,raw_bearer:str,*,now:datetime,
)->CIAtomicServerBinding|None:
    """Compute digest from a real get_current_session-verified bearer IN CI.

    Raw bearer is transient, never stored in a context, log or receipt.
    This function is not proof of an actual person's authentication. The
    PostgreSQL M37464 function must independently match digest to session.
    """
    if (type(session) is not AuthenticatedSession
        or type(raw_bearer) is not str
        or not 24<=len(raw_bearer)<=512
        or any(ord(c)>127 or c.isspace() for c in raw_bearer)
        or session.verification_source!="POSTGRES_TOKEN_HASH_REFRESH"
        or not _aware(now) or not _aware(session.verified_session_at)
        or not _aware(session.verified_session_expires_at)
        or session.verified_session_at>now
        or now-session.verified_session_at>timedelta(minutes=5)
        or now>=session.verified_session_expires_at):
        return None
    sid=_parsed_id(session.verified_session_id)
    uid=_parsed_id(session.user_id)
    tenant=_parsed_id(session.tenant_id)
    if (sid is None or uid is None or tenant is None
        or session.role!="TENANT_ADMIN" or session.is_master is not False):
        return None
    return CIAtomicServerBinding(
        verified_session_id=sid,administrator_id=uid,tenant_id=tenant,
        verified_at=session.verified_session_at,
        expires_at=session.verified_session_expires_at,
        token_sha256=sha256(raw_bearer.encode("ascii")).hexdigest(),
    )


def evaluate_atomic_api_ci(
    *,body:dict[str,object],principal:CIPrincipal,offer:CIPublishedOffer,
    request_id_server:UUID,challenge_id_server:UUID,
    executor:CIAtomicSQLExecutor|None,env:Mapping[str,str],now:datetime,
)->APIContractDecision:
    """Existing M37459 policy drives M37464 DB executor, CI ONLY.

    The caller must open exactly one DB transaction across all three
    actions; this helper never commits and cannot grant production rights.
    """
    if not ci_environment(env):
        return APIContractDecision(503,"M37465_CI_ROUTE_UNAVAILABLE")
    if type(executor) is not CIAtomicSQLExecutor:
        return APIContractDecision(503,"M37465_CI_EXECUTOR_REQUIRED")
    return evaluate_api_contract_ci(
        body=body,principal=principal,offer=offer,
        request_id_server=request_id_server,
        challenge_id_server=challenge_id_server,
        executor=executor,env=env,now=now,
    )
