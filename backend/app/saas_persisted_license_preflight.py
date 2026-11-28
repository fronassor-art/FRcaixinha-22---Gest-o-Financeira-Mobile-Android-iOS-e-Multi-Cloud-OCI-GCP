"""M35400-M35800: Master RLS SaaS payment snapshot to existing read-only MP GET.

Internal service, no public endpoint or real activation. The caller must
supply a server-authenticated get_rls_db_connection transaction.
"""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from uuid import UUID
import httpx
from .dependencies import AuthenticatedSession
from .saas_platform_payment_readback import (
    SaaSPlatformPaymentRecord, review_platform_saas_payment_get,
)
from .platform_provider_adapters import PlatformMpConfig

PAYMENT_QUERY = (
    "SELECT i.tenant_id,i.admin_user_id,i.provider_payment_id,"
    "i.platform_collector_id,i.external_reference,i.expected_amount_cents,"
    "i.live_mode,i.status AS payment_status,i.currency,i.provider,"
    "s.billing_period,s.status AS preparation_status,"
    "v.monthly_price,v.annual_price "
    "FROM public.saas_payment_intents i "
    "JOIN public.saas_subscription_preparations s "
    "ON s.id=i.preparation_id AND s.tenant_id=i.tenant_id "
    "AND s.admin_user_id=i.admin_user_id "
    "AND s.price_version_id=i.price_version_id "
    "JOIN public.platform_license_price_versions v "
    "ON v.id=s.price_version_id AND v.plan_tier=s.plan_tier "
    "JOIN public.tenants t ON t.id=s.tenant_id AND t.status='ATIVO' "
    "WHERE i.id=$1::uuid AND i.provider='MERCADO_PAGO' LIMIT 1"
)

@dataclass(frozen=True)
class LicenseReadback:
    state: str
    matched: bool = False
    digest: str | None = None
    payment_settled: bool = False
    license_activated: bool = False
    member_activated: bool = False
    pix_authorized: bool = False
    production_authorized: bool = False
    writes_performed: bool = False

def _price_cents(value):
    if type(value) not in (Decimal,int,str):
        return None
    try:
        cents = Decimal(value)*100
        if not cents.is_finite() or cents != cents.to_integral_value() or not 0 < cents <= 999999999999:
            return None
        return int(cents)
    except (InvalidOperation,ValueError,TypeError):
        return None

def _master(session):
    try:
        return (type(session) is AuthenticatedSession and session.role=="MASTER"
            and session.is_master is True and session.tenant_id is None
            and UUID(str(session.user_id)).int != 0)
    except (ValueError,TypeError,AttributeError):
        return False

async def readback_persisted_platform_payment(
    *, session: AuthenticatedSession, intent_id: UUID,
    conn, config: PlatformMpConfig, client: httpx.AsyncClient,
) -> LicenseReadback:
    """A repeatable review; NEVER a release/settlement token."""
    if not _master(session):
        return LicenseReadback("MASTER_SESSION_DENIED")
    if type(intent_id) is not UUID or not intent_id.int:
        return LicenseReadback("INVALID_PAYMENT_INTENT_ID")
    if type(config) is not PlatformMpConfig or type(client) is not httpx.AsyncClient:
        return LicenseReadback("PROVIDER_SCOPE_DENIED")
    if not callable(getattr(conn,"fetchrow",None)):
        return LicenseReadback("RLS_CONNECTION_MISSING")
    data=await conn.fetchrow(PAYMENT_QUERY,intent_id)
    if data is None:
        return LicenseReadback("RLS_PAYMENT_NOT_VISIBLE")
    try:
        d=dict(data)
        if (type(d["tenant_id"]) is not UUID
            or type(d["admin_user_id"]) is not UUID
            or d["provider"]!="MERCADO_PAGO"
            or d["preparation_status"]!="PENDING_PAYMENT"
            or d["billing_period"] not in ("MONTHLY","ANNUAL")):
            return LicenseReadback("INVALID_PREPARATION_SCOPE")
        price = d["monthly_price"] if d["billing_period"]=="MONTHLY" else d["annual_price"]
        cents=_price_cents(price)
        if cents is None or type(d["expected_amount_cents"]) is not int or cents!=d["expected_amount_cents"]:
            return LicenseReadback("STORED_PRICE_VERSION_MISMATCH")
        record=SaaSPlatformPaymentRecord(
            tenant_id=d["tenant_id"],admin_user_id=d["admin_user_id"],
            provider_payment_id=d["provider_payment_id"],
            platform_collector_id=d["platform_collector_id"],
            external_reference=d["external_reference"],
            expected_amount_cents=d["expected_amount_cents"],
            live_mode=d["live_mode"],status=d["payment_status"],currency=d["currency"],
        )
    except (KeyError,TypeError,ValueError):
        return LicenseReadback("INVALID_DATABASE_SNAPSHOT")
    # This macropackage does not authorize production readback.
    if record.live_mode is not False or config.live_mode is not False:
        return LicenseReadback("LIVE_PROVIDER_READBACK_DISABLED")
    result=await review_platform_saas_payment_get(record=record,config=config,client=client)
    if result.state!="READBACK_MATCH_REVIEW_ONLY":
        return LicenseReadback(result.state)
    return LicenseReadback("RLS_PRICE_PROVIDER_MATCH_REVIEW_ONLY",
        matched=True,digest=result.evidence_sha256)
