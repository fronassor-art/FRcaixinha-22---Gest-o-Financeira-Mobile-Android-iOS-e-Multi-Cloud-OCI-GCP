"""FR Finance AI Studio — sandbox-only special-credit permissions and campaigns.

No loan approval, reservation, Pix or external delivery. All operations are
transactional through the EXISTING RLS session-scoped PostgreSQL connection.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
import os
from urllib.parse import urlparse
from uuid import UUID, uuid4
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from ..config import settings
from ..database import get_rls_db_connection
from ..dependencies import AuthenticatedSession, get_current_session, require_tenant_access
from ..special_credit_contract import (
    CHANNELS, SpecialCreditDenied, amount_brl, valid_expiry,
    validate_exception, request_is_permitted, public_push_preview,
)
from .loans import compute_price_schedule

router = APIRouter(prefix="/tenants/{tenant_id}/special-credit",
                   tags=["FR Finance — Crédito Especial (homologação)"])


def _enabled() -> bool:
    """Explicit *original local sandbox only*; a staging DB cannot opt in by accident."""
    try:
        db = urlparse(settings.DATABASE_URL)
        return (
            os.getenv("ENVIRONMENT", "development").lower() != "production"
            and os.getenv("FRCAIXINHA_TEST_AUTH") == "1"
            and os.getenv("FR_FINANCE_SPECIAL_CREDIT_SANDBOX") == "YES"
            and db.scheme in ("postgres", "postgresql")
            and db.username == "frc_ai_app"
            and db.hostname == "127.0.0.1"
            and db.port == 5433
            and db.path == "/frcaixinha_aistudio_dev"
            and db.query == "" and db.fragment == ""
        )
    except (ValueError, TypeError):
        return False


def _authorize(tenant_id: UUID, session: AuthenticatedSession,
               *allowed_roles: str) -> None:
    require_tenant_access(str(tenant_id), session)
    if session.role not in allowed_roles:
        raise HTTPException(403, "Perfil sem permissão para esta função.")
    if not _enabled():
        raise HTTPException(503, "Crédito especial indisponível fora da homologação offline.")


def _uid(session: AuthenticatedSession) -> UUID:
    try:
        return UUID(str(session.user_id))
    except (ValueError, TypeError) as exc:
        raise HTTPException(403, "Identidade da sessão inválida.") from exc


def _check_expiry(expires_at: datetime, end_date) -> None:
    try:
        valid_expiry(expires_at)
    except SpecialCreditDenied as exc:
        raise HTTPException(422, str(exc)) from exc
    # Maximum lifetime is the active cycle; never cross into next cycle.
    final_in_utc = datetime.combine(end_date + timedelta(days=1), time.min,
                                    tzinfo=timezone.utc)
    if expires_at > final_in_utc:
        raise HTTPException(422, "Autorização não pode ultrapassar o ciclo.")


async def _cycle(conn, tenant_id: UUID):
    cycle = await conn.fetchrow(
        "SELECT id,end_date FROM public.cycles WHERE tenant_id=$1 "
        "AND status='ABERTO' AND start_date<=CURRENT_DATE "
        "AND end_date>=CURRENT_DATE "
        "ORDER BY start_date DESC,id DESC LIMIT 1", tenant_id)
    if cycle is None:
        raise HTTPException(409, "Não há ciclo vigente e aberto na caixinha.")
    return cycle


async def _check_admin(conn, tenant_id: UUID, session: AuthenticatedSession):
    owner = await conn.fetchval(
        "SELECT admin_user_id FROM public.tenants WHERE id=$1 AND status='ATIVO'",
        tenant_id)
    if owner != _uid(session):
        raise HTTPException(403, "Administrador titular da caixinha não confirmado.")


async def _audit(conn, tenant: UUID, actor: UUID, kind: str, obj: UUID,
                 action: str, detail: str):
    await conn.execute(
        "INSERT INTO public.special_credit_audit "
        "(tenant_id,actor_id,entity_kind,entity_id,action,detail) "
        "VALUES($1,$2,$3,$4,$5,$6)",
        tenant, actor, kind, obj, action, detail[:250])


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GrantBatch(StrictModel):
    member_ids: list[UUID] = Field(min_length=1, max_length=50)
    # The current authoritative Price engine has a hard ceiling of R$ 50,000.
    # Never promise a higher exception before a separately reviewed engine/policy migration.
    ceiling_brl: Decimal = Field(gt=Decimal("0"), le=Decimal("50000.00"))
    expires_at: datetime
    reason: str = Field(min_length=20, max_length=2000)
    request_id: UUID


class CampaignDraft(StrictModel):
    grant_ids: list[UUID] = Field(min_length=1, max_length=50)
    title: str = Field(min_length=4, max_length=100)
    body: str = Field(min_length=10, max_length=500)
    expires_at: datetime
    request_id: UUID


class MarketingPreference(StrictModel):
    channel: Literal["PUSH", "EMAIL", "WHATSAPP", "SMS"]
    opted_in: bool


class OpportunityReply(StrictModel):
    status: Literal["INTERESTED", "DECLINED"]


class SpecialSimulation(StrictModel):
    grant_id: UUID
    principal: Decimal
    term_months: int = Field(ge=1, le=6)


@router.get("/capabilities")
async def capabilities(tenant_id: UUID,
                       session: AuthenticatedSession = Depends(get_current_session)):
    require_tenant_access(str(tenant_id), session)
    return {
        "contract": "FR_FINANCE_SPECIAL_CREDIT_SANDBOX_V1",
        "sandbox_enabled": _enabled(),
        "grants_allow_request_only": True,
        "real_credit_enabled": False, "pix_real_enabled": False,
        "channels": {ch: {"code_present": True, "real_delivery_enabled": False}
                     for ch in CHANNELS},
        "safe_push_preview": public_push_preview(),
    }


@router.get("/members")
async def eligible_members(tenant_id: UUID,
                           session: AuthenticatedSession = Depends(get_current_session),
                           conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_ADMIN")
    await _check_admin(conn, tenant_id, session)
    rows = await conn.fetch(
        "SELECT m.id,m.user_id,u.full_name FROM public.memberships m "
        "JOIN public.users u ON u.id=m.user_id "
        "WHERE m.tenant_id=$1 AND m.role='TENANT_MEMBER' AND m.status='ATIVA' "
        "ORDER BY u.full_name,m.id LIMIT 200", tenant_id)
    return [{"id":str(r["id"]), "name":r["full_name"]} for r in rows]


@router.post("/grants")
async def create_grants(tenant_id: UUID, payload: GrantBatch,
                        session: AuthenticatedSession = Depends(get_current_session),
                        conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_ADMIN")
    await _check_admin(conn, tenant_id, session)
    if len(set(payload.member_ids)) != len(payload.member_ids):
        raise HTTPException(422, "Membro duplicado na seleção.")
    cycle = await _cycle(conn, tenant_id)
    _check_expiry(payload.expires_at, cycle["end_date"])
    actor = _uid(session)
    results = []
    for member_id in payload.member_ids:
        m = await conn.fetchrow(
            "SELECT id,tenant_id,status,role FROM public.memberships "
            "WHERE id=$1 AND tenant_id=$2 AND role='TENANT_MEMBER' FOR SHARE",
            member_id, tenant_id)
        if m is None:
            raise HTTPException(403, "Membro não pertence à caixinha.")
        try:
            ceiling = validate_exception(
                tenant_id=str(tenant_id), member_tenant_id=str(m["tenant_id"]),
                member_status=m["status"], cycle_status="ABERTO",
                amount=payload.ceiling_brl, expires_at=payload.expires_at,
                reason=payload.reason)
        except SpecialCreditDenied as exc:
            raise HTTPException(422, str(exc)) from exc
        record = await conn.fetchrow(
            "INSERT INTO public.special_credit_grants "
            "(tenant_id,cycle_id,member_id,created_by,ceiling_brl,reason,expires_at,request_id) "
            "VALUES($1,$2,$3,$4,$5,$6,$7,$8) "
            "ON CONFLICT DO NOTHING "
            "RETURNING id,ceiling_brl,expires_at,reason",
            tenant_id, cycle["id"], member_id, actor, ceiling, payload.reason.strip(),
            payload.expires_at, payload.request_id)
        if record is None:
            record = await conn.fetchrow(
                "SELECT id,ceiling_brl,expires_at,reason "
                "FROM public.special_credit_grants "
                "WHERE tenant_id=$1 AND created_by=$2 AND request_id=$3 AND member_id=$4",
                tenant_id, actor, payload.request_id, member_id)
            if (record is None or record["ceiling_brl"] != ceiling
                    or record["expires_at"] != payload.expires_at
                    or record["reason"] != payload.reason.strip()):
                raise HTTPException(409, "Reutilização inválida da chave de idempotência.")
        else:
            await _audit(conn, tenant_id, actor, "GRANT", record["id"],
                         "GRANT_CREATED", "Permissão de solicitação excepcional sem dinheiro")
        results.append({"grant_id":str(record["id"]),"member_id":str(member_id),
                        "ceiling_brl":str(ceiling),"expires_at":payload.expires_at.isoformat()})
    return {"grants":results,"real_credit_enabled":False}


@router.get("/grants")
async def list_grants(tenant_id: UUID,
                      session: AuthenticatedSession = Depends(get_current_session),
                      conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_ADMIN", "TENANT_MEMBER")
    rows = await conn.fetch(
        "SELECT g.id,g.member_id,g.ceiling_brl,g.expires_at,g.status,g.created_at,"
        "u.full_name AS member_name FROM public.special_credit_grants g "
        "JOIN public.memberships m ON m.id=g.member_id "
        "JOIN public.users u ON u.id=m.user_id "
        "WHERE g.tenant_id=$1 ORDER BY g.created_at DESC LIMIT 150", tenant_id)
    return [{"id":str(r["id"]),"member_id":str(r["member_id"]),
             "member_name":r["member_name"],"ceiling_brl":str(r["ceiling_brl"]),
             "expires_at":r["expires_at"],"status":r["status"]} for r in rows]


@router.post("/grants/{grant_id}/revoke")
async def revoke_grant(tenant_id: UUID, grant_id: UUID,
                       session: AuthenticatedSession = Depends(get_current_session),
                       conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_ADMIN")
    await _check_admin(conn, tenant_id, session)
    row = await conn.fetchrow(
        "UPDATE public.special_credit_grants "
        "SET status='REVOKED',updated_at=now() "
        "WHERE id=$1 AND tenant_id=$2 AND status='ACTIVE' RETURNING id",
        grant_id, tenant_id)
    if not row:
        raise HTTPException(409, "Autorização indisponível para revogação.")
    await _audit(conn, tenant_id, _uid(session), "GRANT", grant_id,
                 "GRANT_REVOKED", "Revogação de novas solicitações")
    return {"status":"REVOKED"}


@router.post("/campaigns")
async def create_campaign(tenant_id: UUID, payload: CampaignDraft,
                          session: AuthenticatedSession = Depends(get_current_session),
                          conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_ADMIN")
    await _check_admin(conn, tenant_id, session)
    if len(set(payload.grant_ids)) != len(payload.grant_ids):
        raise HTTPException(422, "Autorização duplicada.")
    cycle = await _cycle(conn, tenant_id)
    _check_expiry(payload.expires_at, cycle["end_date"])
    actor = _uid(session)
    grants = await conn.fetch(
        "SELECT g.id,g.member_id,m.user_id,g.expires_at,g.status "
        "FROM public.special_credit_grants g "
        "JOIN public.memberships m ON m.id=g.member_id "
        "WHERE g.tenant_id=$1 AND g.cycle_id=$2 AND g.id=ANY($3::uuid[]) "
        "AND m.status='ATIVA' AND m.role='TENANT_MEMBER'",
        tenant_id, cycle["id"], payload.grant_ids)
    if len(grants) != len(payload.grant_ids) or len({r["member_id"] for r in grants}) != len(grants):
        raise HTTPException(409, "Autorizações inválidas ou membros duplicados.")
    if any(r["status"] != "ACTIVE" or r["expires_at"] < payload.expires_at for r in grants):
        raise HTTPException(409, "Campanha ultrapassa validade de alguma autorização.")
    row = await conn.fetchrow(
        "INSERT INTO public.special_credit_campaigns "
        "(tenant_id,cycle_id,created_by,title,body,expires_at,request_id) "
        "VALUES($1,$2,$3,$4,$5,$6,$7) "
        "ON CONFLICT(tenant_id,created_by,request_id) DO NOTHING "
        "RETURNING id",
        tenant_id, cycle["id"], actor, payload.title.strip(), payload.body.strip(),
        payload.expires_at, payload.request_id)
    if row is None:
        old = await conn.fetchrow(
            "SELECT id,title,body,expires_at FROM public.special_credit_campaigns "
            "WHERE tenant_id=$1 AND created_by=$2 AND request_id=$3",
            tenant_id, actor, payload.request_id)
        if (old is None or old["title"] != payload.title.strip()
                or old["body"] != payload.body.strip()
                or old["expires_at"] != payload.expires_at):
            raise HTTPException(409, "Chave de idempotência incompatível.")
        old_grants = await conn.fetch(
            "SELECT grant_id FROM public.special_credit_recipients "
            "WHERE campaign_id=$1 AND tenant_id=$2", old["id"], tenant_id)
        if {r["grant_id"] for r in old_grants} != set(payload.grant_ids):
            raise HTTPException(409, "Reutilização de campanha com destinatários diferentes.")
        return {"id":str(old["id"]),"status":"DRAFT_OR_EXISTING","created":False}
    campaign = row["id"]
    for grant in grants:
        await conn.execute(
            "INSERT INTO public.special_credit_recipients "
            "(tenant_id,campaign_id,grant_id,member_id,user_id) VALUES($1,$2,$3,$4,$5)",
            tenant_id, campaign, grant["id"], grant["member_id"], grant["user_id"])
    await _audit(conn, tenant_id, actor, "CAMPAIGN", campaign,
                 "CAMPAIGN_DRAFTED", "Rascunho sem entrega ou efeito financeiro")
    return {"id":str(campaign),"status":"DRAFT","created":True}


@router.get("/campaigns")
async def list_campaigns(tenant_id: UUID,
                         session: AuthenticatedSession = Depends(get_current_session),
                         conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_ADMIN")
    await _check_admin(conn, tenant_id, session)
    rows = await conn.fetch(
        "SELECT c.id,c.title,c.status,c.expires_at,c.created_at,"
        "(SELECT count(*) FROM public.special_credit_recipients r "
        "WHERE r.campaign_id=c.id AND r.tenant_id=c.tenant_id) AS recipients "
        "FROM public.special_credit_campaigns c WHERE c.tenant_id=$1 "
        "ORDER BY c.created_at DESC LIMIT 100", tenant_id)
    return [dict(r) for r in rows]


@router.post("/campaigns/{campaign_id}/publish")
async def publish_campaign(tenant_id: UUID, campaign_id: UUID,
                           session: AuthenticatedSession = Depends(get_current_session),
                           conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_ADMIN")
    await _check_admin(conn, tenant_id, session)
    c = await conn.fetchrow(
        "SELECT id,status,expires_at FROM public.special_credit_campaigns "
        "WHERE id=$1 AND tenant_id=$2 FOR UPDATE", campaign_id, tenant_id)
    if c is None or c["status"] not in ("DRAFT","PUBLISHED"):
        raise HTTPException(409, "Campanha indisponível.")
    if c["expires_at"] <= datetime.now(timezone.utc):
        raise HTTPException(409, "Campanha expirada.")
    invalid = await conn.fetchval(
        "SELECT count(*) FROM public.special_credit_recipients r "
        "JOIN public.special_credit_grants g ON g.id=r.grant_id "
        "JOIN public.memberships m ON m.id=r.member_id "
        "WHERE r.campaign_id=$1 AND r.tenant_id=$2 "
        "AND (g.status <> 'ACTIVE' OR g.expires_at <= now() "
        " OR g.expires_at < (SELECT c.expires_at FROM public.special_credit_campaigns c "
        " WHERE c.id=$1 AND c.tenant_id=$2) "
        " OR m.status <> 'ATIVA' OR g.tenant_id<>r.tenant_id)", campaign_id, tenant_id)
    if invalid:
        raise HTTPException(409, "Uma das autorizações ou adesões está inválida.")
    if c["status"] == "DRAFT":
        await conn.execute(
            "UPDATE public.special_credit_campaigns "
            "SET status='PUBLISHED',published_at=now() WHERE id=$1 AND tenant_id=$2",
            campaign_id, tenant_id)
        await conn.execute(
            "INSERT INTO public.special_credit_outbox "
            "(tenant_id,campaign_id,recipient_id,channel,state) "
            "SELECT r.tenant_id,r.campaign_id,r.id,p.channel,'BLOCKED_EXTERNAL' "
            "FROM public.special_credit_recipients r "
            "JOIN public.special_credit_preferences p "
            "ON p.tenant_id=r.tenant_id AND p.user_id=r.user_id AND p.opted_in=true "
            "WHERE r.tenant_id=$1 AND r.campaign_id=$2 "
            "ON CONFLICT(campaign_id,recipient_id,channel) DO NOTHING",
            tenant_id, campaign_id)
        await _audit(conn, tenant_id, _uid(session), "CAMPAIGN", campaign_id,
                     "CAMPAIGN_PUBLISHED_IN_APP",
                     "Oportunidade consultável; entrega externa permanece bloqueada")
    return {"status":"PUBLISHED","in_app":True,"external_dispatch":False}


@router.post("/campaigns/{campaign_id}/cancel")
async def cancel_campaign(tenant_id: UUID, campaign_id: UUID,
                          session: AuthenticatedSession = Depends(get_current_session),
                          conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_ADMIN")
    await _check_admin(conn, tenant_id, session)
    updated = await conn.fetchval(
        "UPDATE public.special_credit_campaigns SET status='CANCELLED' "
        "WHERE id=$1 AND tenant_id=$2 AND status IN ('DRAFT','PUBLISHED') "
        "RETURNING id", campaign_id, tenant_id)
    if updated is None:
        raise HTTPException(409, "Campanha indisponível.")
    await _audit(conn, tenant_id, _uid(session), "CAMPAIGN", campaign_id,
                 "CAMPAIGN_CANCELLED", "Cancelada sem lançamento financeiro")
    return {"status":"CANCELLED"}


@router.get("/opportunities")
async def member_opportunities(tenant_id: UUID,
                               session: AuthenticatedSession = Depends(get_current_session),
                               conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_MEMBER")
    rows = await conn.fetch(
        "SELECT r.id AS recipient_id,r.response_status,c.id AS campaign_id,"
        "c.title,c.body,c.expires_at,g.id AS grant_id,g.ceiling_brl "
        "FROM public.special_credit_recipients r "
        "JOIN public.special_credit_campaigns c ON c.id=r.campaign_id "
        "JOIN public.special_credit_grants g ON g.id=r.grant_id "
        "JOIN public.memberships m ON m.id=r.member_id "
        "WHERE r.tenant_id=$1 AND r.user_id=$2 AND c.tenant_id=$1 "
        "AND c.status='PUBLISHED' AND c.expires_at>now() "
        "AND g.status='ACTIVE' AND g.expires_at>now() AND m.status='ATIVA' "
        "ORDER BY c.published_at DESC LIMIT 100", tenant_id, _uid(session))
    return [{"recipient_id":str(r["recipient_id"]),"campaign_id":str(r["campaign_id"]),
             "grant_id":str(r["grant_id"]),"title":r["title"],"message":r["body"],
             "ceiling_brl":str(r["ceiling_brl"]),"expires_at":r["expires_at"],
             "response_status":r["response_status"]} for r in rows]


@router.post("/opportunities/{recipient_id}/reply")
async def reply(tenant_id: UUID, recipient_id: UUID, payload: OpportunityReply,
                session: AuthenticatedSession = Depends(get_current_session),
                conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_MEMBER")
    row = await conn.fetchrow(
        "UPDATE public.special_credit_recipients r "
        "SET response_status=$1,responded_at=now() "
        "WHERE r.id=$2 AND r.tenant_id=$3 AND r.user_id=$4 "
        "AND r.response_status='PENDING' "
        "AND EXISTS (SELECT 1 FROM public.special_credit_campaigns c "
        "WHERE c.id=r.campaign_id AND c.tenant_id=$3 "
        " AND c.status='PUBLISHED' AND c.expires_at>now()) "
        "AND EXISTS (SELECT 1 FROM public.special_credit_grants g "
        "WHERE g.id=r.grant_id AND g.tenant_id=$3 "
        " AND g.status='ACTIVE' AND g.expires_at>now()) "
        "RETURNING r.id", payload.status, recipient_id, tenant_id, _uid(session))
    if row is None:
        raise HTTPException(409, "Oferta indisponível ou já respondida.")
    await _audit(conn, tenant_id, _uid(session), "RECIPIENT", recipient_id,
                 "OPPORTUNITY_"+payload.status, "Resposta voluntária sem solicitação financeira")
    return {"status":payload.status,"loan_created":False}


@router.get("/preferences")
async def get_preferences(tenant_id: UUID,
                          session: AuthenticatedSession = Depends(get_current_session),
                          conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_MEMBER")
    rows = await conn.fetch(
        "SELECT channel,opted_in FROM public.special_credit_preferences "
        "WHERE tenant_id=$1 AND user_id=$2", tenant_id, _uid(session))
    selected = {r["channel"]:r["opted_in"] is True for r in rows}
    return {"preferences":{ch:selected.get(ch,False) for ch in CHANNELS},
            "external_dispatch":False}


@router.post("/preferences")
async def set_preference(tenant_id: UUID, payload: MarketingPreference,
                         session: AuthenticatedSession = Depends(get_current_session),
                         conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_MEMBER")
    user = _uid(session)
    active = await conn.fetchval(
        "SELECT EXISTS(SELECT 1 FROM public.memberships m WHERE m.tenant_id=$1 "
        "AND m.user_id=$2 AND m.role='TENANT_MEMBER' AND m.status='ATIVA')",
        tenant_id, user)
    if not active:
        raise HTTPException(403, "Vínculo de membro não ativo.")
    await conn.execute(
        "INSERT INTO public.special_credit_preferences "
        "(tenant_id,user_id,channel,opted_in) VALUES($1,$2,$3,$4) "
        "ON CONFLICT(tenant_id,user_id,channel) "
        "DO UPDATE SET opted_in=EXCLUDED.opted_in,changed_at=now()",
        tenant_id, user, payload.channel, payload.opted_in)
    await _audit(conn, tenant_id, user, "PREFERENCE", user,
                 "MARKETING_PREFERENCE_CHANGED", payload.channel+":"+
                 ("OPT_IN" if payload.opted_in else "OPT_OUT"))
    return {"channel":payload.channel,"opted_in":payload.opted_in,
            "external_dispatch":False}


@router.post("/simulate")
async def simulate_special(tenant_id: UUID, payload: SpecialSimulation,
                           session: AuthenticatedSession = Depends(get_current_session),
                           conn=Depends(get_rls_db_connection)):
    _authorize(tenant_id, session, "TENANT_MEMBER")
    row = await conn.fetchrow(
        "SELECT g.id,g.status,g.expires_at,g.ceiling_brl,m.status AS member_status,"
        "c.start_date,c.end_date,c.status AS cycle_status,c.id AS cycle_id "
        "FROM public.special_credit_grants g "
        "JOIN public.memberships m ON m.id=g.member_id "
        "JOIN public.cycles c ON c.id=g.cycle_id "
        "WHERE g.id=$1 AND g.tenant_id=$2 AND m.user_id=$3 AND c.tenant_id=$2",
        payload.grant_id, tenant_id, _uid(session))
    if row is None or not request_is_permitted(
        grant_status=row["status"],valid_until=row["expires_at"],
        requested=payload.principal,granted_limit=row["ceiling_brl"],
        member_active=row["member_status"]=="ATIVA",
        cycle_open=row["cycle_status"]=="ABERTO"):
        raise HTTPException(403, "Autorização especial não é elegível.")
    policy = await conn.fetchrow(
        "SELECT monthly_interest_rate,max_installments FROM public.policies "
        "WHERE tenant_id=$1 AND cycle_id=$2 AND status='ACTIVE' "
        "ORDER BY version DESC,id DESC LIMIT 1", tenant_id,row["cycle_id"])
    if policy is None or payload.term_months>policy["max_installments"]:
        raise HTTPException(422, "Prazo incompatível com a política.")
    try:
        preview = compute_price_schedule(
            amount_brl(payload.principal),payload.term_months,
            Decimal(str(policy["monthly_interest_rate"])),
            cycle_start_date=row["start_date"],cycle_end_date=row["end_date"])
    except (ValueError, ArithmeticError, SpecialCreditDenied) as exc:
        raise HTTPException(422, "Simulação financeira indisponível.") from exc
    return {"grant_id":str(payload.grant_id),"simulation":preview,
            "approved":False,"reserved":False,"disbursed":False}
