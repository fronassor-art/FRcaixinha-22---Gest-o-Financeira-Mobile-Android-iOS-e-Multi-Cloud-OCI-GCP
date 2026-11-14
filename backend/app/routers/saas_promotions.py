"""FR Finance M39067 — promoções SaaS, somente Master, sem cobranças.

Campanhas comerciais (assinatura de administradores) NÃO se confundem
com Oportunidades de Crédito de membros. SQL113 é mandatória.
Todas as escritas passam pelo contexto de sessão + RLS e mesma transação
em get_rls_db_connection. Nenhum envio externo ou ativação real.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from ..database import get_rls_db_connection
from ..dependencies import (
    AuthenticatedSession, get_current_session, require_master,
    require_tenant_access,
)

master_router = APIRouter(
    prefix="/master/saas-promotions",
    tags=["Promoções SaaS somente Master"],
)
tenant_router = APIRouter(
    prefix="/tenants", tags=["Ofertas SaaS para novos administradores"],
)


class SaaSPromotionDraft(BaseModel):
    plan_tier: Literal["ESSENCIAL", "INTERMEDIARIO"]
    billing_period: Literal["MONTHLY", "ANNUAL"]
    base_price_version_id: uuid.UUID
    promotional_price: Decimal = Field(
        ..., gt=Decimal("0"), le=Decimal("999999.99"), decimal_places=2
    )
    title: str = Field(..., min_length=5, max_length=120)
    benefit_description: str = Field(..., min_length=10, max_length=500)
    starts_at: datetime
    ends_at: datetime
    reason: str = Field(..., min_length=15, max_length=500)

    @model_validator(mode="after")
    def verify_period_and_copy(self):
        if (self.starts_at.tzinfo is None
                or self.starts_at.utcoffset() is None
                or self.ends_at.tzinfo is None
                or self.ends_at.utcoffset() is None
                or self.ends_at <= self.starts_at):
            raise ValueError("Vigência exige datas com fuso e fim posterior ao início.")
        if (len(self.title.strip()) < 5
                or len(self.benefit_description.strip()) < 10
                or len(self.reason.strip()) < 15):
            raise ValueError("Título, benefício e justificativa devem conter texto.")
        return self


class SaaSPromotionTransition(BaseModel):
    campaign_id: uuid.UUID
    expected_revision: int = Field(..., ge=1)
    action: Literal["PUBLISH", "CANCEL"]
    reason: str = Field(..., min_length=15, max_length=500)


async def require_sql113(conn) -> None:
    ready = await conn.fetchval(
        "SELECT to_regclass('public.platform_saas_promotion_revisions') "
        "IS NOT NULL AND to_regprocedure("
        "'public.frfinance_saas_new_admin_published_promotions()') IS NOT NULL"
    )
    if ready is not True:
        raise HTTPException(
            status_code=503,
            detail="Promoções comerciais indisponíveis até migração SQL113.",
        )


def format_promotion(row) -> dict:
    return {
        "campaign_id": str(row["campaign_id"]),
        "revision": row["revision"],
        "plan_tier": row["plan_tier"],
        "billing_period": row["billing_period"],
        "base_price_version_id": str(row["base_price_version_id"]),
        "promotional_price": str(row["promotional_price"]),
        "audience": "NEW_ADMIN_ONLY",
        "title": row["title"],
        "benefit_description": row["benefit_description"],
        "starts_at": row["starts_at"].isoformat(),
        "ends_at": row["ends_at"].isoformat(),
        "state": row["state"],
    }


@master_router.get("")
async def list_master_promotions(
    session: AuthenticatedSession = Depends(require_master),
    conn=Depends(get_rls_db_connection),
):
    """Última revisão de cada campanha; não retorna valores fictícios."""
    await require_sql113(conn)
    rows = await conn.fetch(
        "SELECT p.* FROM "
        "(SELECT DISTINCT ON (campaign_id) campaign_id,revision,plan_tier,"
        "billing_period,base_price_version_id,promotional_price,audience,"
        "title,benefit_description,starts_at,ends_at,state,created_at "
        "FROM public.platform_saas_promotion_revisions "
        "ORDER BY campaign_id,revision DESC) p "
        "ORDER BY p.created_at DESC,p.campaign_id DESC LIMIT 100"
    )
    return {
        "source": "POSTGRESQL_RLS",
        "scope": "MASTER_SAAS_PROMOTIONS",
        "delivery": "IN_APP_ONLY_NO_EXTERNAL_DISPATCH",
        "billing": "OFF_NO_PROVIDER_NO_CHARGE",
        "promotions": [format_promotion(r) for r in rows],
    }


@master_router.post("/draft", status_code=201)
async def create_master_promotion_draft(
    payload: SaaSPromotionDraft,
    session: AuthenticatedSession = Depends(require_master),
    conn=Depends(get_rls_db_connection),
):
    """Criar rascunho não visível ao administrador, sem assinatura nem Pix."""
    await require_sql113(conn)
    if payload.ends_at <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Vigência comercial já encerrada.")
    latest = await conn.fetchrow(
        "SELECT p.status,v.id AS version_id,v.plan_tier "
        "FROM public.platform_license_plans p "
        "JOIN LATERAL "
        "(SELECT id,plan_tier FROM public.platform_license_price_versions "
        "WHERE plan_tier=p.tier ORDER BY created_at DESC,id DESC LIMIT 1) v ON true "
        "WHERE p.tier=$1",
        payload.plan_tier,
    )
    if not latest or latest["status"] != "ACTIVE":
        raise HTTPException(status_code=422, detail="Plano indisponível.")
    if str(latest["version_id"]) != str(payload.base_price_version_id):
        raise HTTPException(status_code=409, detail="Versão de preço desatualizada.")

    campaign_id = uuid.uuid4()
    actor = uuid.UUID(session.user_id)
    row = await conn.fetchrow(
        "INSERT INTO public.platform_saas_promotion_revisions "
        "(campaign_id,revision,plan_tier,billing_period,base_price_version_id,"
        "promotional_price,audience,title,benefit_description,starts_at,ends_at,"
        "state,reason,created_by) "
        "VALUES ($1,1,$2,$3,$4,$5,'NEW_ADMIN_ONLY',$6,$7,$8,$9,'DRAFT',$10,$11) "
        "RETURNING campaign_id,revision,plan_tier,billing_period,"
        "base_price_version_id,promotional_price,audience,title,"
        "benefit_description,starts_at,ends_at,state",
        campaign_id,payload.plan_tier,payload.billing_period,
        payload.base_price_version_id,payload.promotional_price,
        payload.title.strip(),payload.benefit_description.strip(),
        payload.starts_at,payload.ends_at,payload.reason.strip(),actor,
    )
    await conn.execute(
        "INSERT INTO public.audit_events "
        "(actor_id,actor_role,action,object_type,object_id,reason,evidence_ref) "
        "VALUES($1,'MASTER','SAAS_PROMOTION_DRAFT_CREATED',"
        "'SAAS_PROMOTION',$2,$3,'M39067_SQL113')",
        actor,str(campaign_id),payload.reason.strip(),
    )
    return {
        "status": "DRAFT_PERSISTED_NO_BILLING",
        "promotion": format_promotion(row),
        "delivery": "NONE_DRAFT",
    }


@master_router.post("/transition")
async def transition_master_promotion(
    payload: SaaSPromotionTransition,
    session: AuthenticatedSession = Depends(require_master),
    conn=Depends(get_rls_db_connection),
):
    """Publicação/cancelamento: nova revisão append-only, nenhum UPDATE."""
    await require_sql113(conn)
    await conn.fetchval(
        "SELECT pg_advisory_xact_lock(39067,hashtext($1::text))",
        str(payload.campaign_id),
    )
    old = await conn.fetchrow(
        "SELECT * FROM public.platform_saas_promotion_revisions "
        "WHERE campaign_id=$1 ORDER BY revision DESC LIMIT 1",
        payload.campaign_id,
    )
    if not old:
        raise HTTPException(status_code=404, detail="Campanha não encontrada.")
    if old["revision"] != payload.expected_revision:
        raise HTTPException(
            status_code=409, detail="Campanha alterada; recarregue antes de publicar."
        )

    target = "PUBLISHED" if payload.action == "PUBLISH" else "CANCELED"
    if (payload.action == "PUBLISH" and old["state"] != "DRAFT"):
        raise HTTPException(status_code=409, detail="Apenas rascunhos podem ser publicados.")
    if (payload.action == "CANCEL" and old["state"] != "PUBLISHED"):
        raise HTTPException(status_code=409, detail="Apenas campanhas publicadas podem ser canceladas.")
    if payload.action == "PUBLISH":
        if old["ends_at"] <= datetime.now(timezone.utc):
            raise HTTPException(status_code=409, detail="Vigência já encerrada.")
        await conn.fetchval(
            "SELECT pg_advisory_xact_lock(39068,hashtext($1::text))",
            old["plan_tier"] + ":" + old["billing_period"],
        )
        conflict = await conn.fetchval(
            "SELECT EXISTS (SELECT 1 FROM "
            "(SELECT DISTINCT ON (campaign_id) * "
            "FROM public.platform_saas_promotion_revisions "
            "ORDER BY campaign_id,revision DESC) p "
            "WHERE p.campaign_id<>$1 AND p.state='PUBLISHED' "
            "AND p.plan_tier=$2 AND p.billing_period=$3 "
            "AND p.ends_at>$4 AND p.starts_at<$5)",
            payload.campaign_id,old["plan_tier"],old["billing_period"],
            old["starts_at"],old["ends_at"],
        )
        if conflict:
            raise HTTPException(
                status_code=409, detail="Já existe promoção publicada nesse período."
            )
    actor = uuid.UUID(session.user_id)
    row = await conn.fetchrow(
        "INSERT INTO public.platform_saas_promotion_revisions "
        "(campaign_id,revision,plan_tier,billing_period,base_price_version_id,"
        "promotional_price,audience,title,benefit_description,starts_at,ends_at,"
        "state,reason,created_by) "
        "VALUES($1,$2,$3,$4,$5,$6,'NEW_ADMIN_ONLY',$7,$8,$9,$10,$11,$12,$13) "
        "RETURNING campaign_id,revision,plan_tier,billing_period,"
        "base_price_version_id,promotional_price,audience,title,"
        "benefit_description,starts_at,ends_at,state",
        payload.campaign_id,old["revision"]+1,old["plan_tier"],
        old["billing_period"],old["base_price_version_id"],
        old["promotional_price"],old["title"],old["benefit_description"],
        old["starts_at"],old["ends_at"],target,payload.reason.strip(),actor,
    )
    await conn.execute(
        "INSERT INTO public.audit_events "
        "(actor_id,actor_role,action,object_type,object_id,reason,evidence_ref) "
        "VALUES($1,'MASTER',$2,'SAAS_PROMOTION',$3,$4,'M39067_SQL113')",
        actor,"SAAS_PROMOTION_" + target,str(payload.campaign_id),payload.reason.strip(),
    )
    return {
        "status": "REVISION_PERSISTED_NO_BILLING",
        "promotion": format_promotion(row),
        "external_delivery": "OFF",
    }


@tenant_router.get("/{tenant_id}/saas-promotions")
async def get_new_admin_saas_promotions(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Somente novo TENANT_ADMIN do tenant vigente lê campanhas publicadas."""
    require_tenant_access(tenant_id,session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403,detail="Promoção exclusiva de administradores.")
    try:
        uuid.UUID(tenant_id)
    except ValueError:
        raise HTTPException(status_code=422,detail="Caixinha inválida.") from None
    await require_sql113(conn)
    rows = await conn.fetch(
        "SELECT campaign_id,plan_tier,billing_period,promotional_price,"
        "title,benefit_description,starts_at,ends_at,revision,base_price_version_id "
        "FROM public.frfinance_saas_new_admin_published_promotions()"
    )
    return {
        "source": "POSTGRESQL_RLS",
        "scope": "ELIGIBLE_NEW_TENANT_ADMIN_ONLY",
        "tenant_id": tenant_id,
        "billing": "OFF_NO_PROVIDER_NO_CHARGE",
        "offers": [
            {
                "campaign_id":str(r["campaign_id"]),
                "plan_tier":r["plan_tier"],
                "billing_period":r["billing_period"],
                "promotional_price":str(r["promotional_price"]),
                "title":r["title"],
                "benefit_description":r["benefit_description"],
                "starts_at":r["starts_at"].isoformat(),
                "ends_at":r["ends_at"].isoformat(),
                "revision":r["revision"],
                "base_price_version_id":str(r["base_price_version_id"]),
            } for r in rows
        ],
    }
