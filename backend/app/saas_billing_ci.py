"""Motor de cobrança SaaS: transações de laboratório isolado.

O pagamento real só entra pelo adaptador do provedor, depois de autorização.
Este módulo CI testa as mesmas invariantes de idempotência, valor, vendedor,
reembolso e vencimento, sem usar o ledger financeiro de nenhuma caixinha.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4
import calendar
import secrets
import hashlib

from .account_lifecycle import _ci_only, LifecycleDenied
from .mercado_pago_safety import ExpectedPayment, matches_approved_payment, matches_full_refund


def _cents(amount: Decimal) -> int:
    value=Decimal(str(amount))*100
    if not value.is_finite() or value != value.to_integral_value() or value <= 0:
        raise LifecycleDenied("Valor da licença deve conter centavos exatos positivos.")
    return int(value)


def _end_of_term(start: datetime, period: str) -> datetime:
    if period not in ('MONTHLY','ANNUAL'):
        raise LifecycleDenied("Período de licença inválido.")
    months=1 if period=='MONTHLY' else 12
    year=start.year+(start.month-1+months)//12
    month=(start.month-1+months)%12+1
    day=min(start.day,calendar.monthrange(year,month)[1])
    return start.replace(year=year,month=month,day=day)


def stage_saas_payment_ci(conn, *, preparation_id: UUID,
                          platform_collector_id: str, live_mode: bool) -> UUID:
    """Preço é o fixado no DB, jamais um valor recebido do aplicativo."""
    _ci_only(conn)
    if not platform_collector_id.isdecimal() or not platform_collector_id:
        raise LifecycleDenied("Conta da plataforma não configurada.")
    with conn.transaction():
        row=conn.execute(
            "SELECT s.tenant_id,s.admin_user_id,s.price_version_id,s.billing_period,"
            "s.status,v.monthly_price,v.annual_price "
            "FROM public.saas_subscription_preparations s "
            "JOIN public.platform_license_price_versions v ON v.id=s.price_version_id "
            "WHERE s.id=%s FOR UPDATE OF s", (preparation_id,),
        ).fetchone()
        if not row or row[4]!='PENDING_PAYMENT':
            raise LifecycleDenied("Preparação de licença inválida para cobrança.")
        existing=conn.execute(
            "SELECT 1 FROM public.saas_payment_intents WHERE preparation_id=%s "
            "AND status IN ('PENDING','APPROVED')", (preparation_id,),
        ).fetchone()
        if existing:
            raise LifecycleDenied("Já existe cobrança pendente ou conciliada.")
        if not conn.execute(
            "SELECT 1 FROM public.memberships WHERE tenant_id=%s AND user_id=%s "
            "AND role='TENANT_ADMIN' AND status='ATIVA'",(row[0],row[1]),
        ).fetchone():
            raise LifecycleDenied("Administrador não possui vínculo ativo.")
        payment_id=uuid4()
        amount=_cents(row[5] if row[3]=='MONTHLY' else row[6])
        conn.execute(
            "INSERT INTO public.saas_payment_intents"
            "(id,preparation_id,tenant_id,admin_user_id,price_version_id,"
            "expected_amount_cents,external_reference,idempotency_key,"
            "platform_collector_id,live_mode) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (payment_id,preparation_id,row[0],row[1],row[2],amount,
             f"saas:{payment_id}",secrets.token_hex(20),
             platform_collector_id,live_mode),
        )
        return payment_id


def attach_mp_payment_identifier_ci(conn, *, intent_id: UUID, provider_payment_id: str) -> bool:
    _ci_only(conn)
    if not provider_payment_id.isdecimal() or len(provider_payment_id)>40:
        raise LifecycleDenied("ID de pagamento externo inválido.")
    with conn.transaction():
        row=conn.execute(
            "UPDATE public.saas_payment_intents "
            "SET provider_payment_id=%s WHERE id=%s AND status='PENDING' "
            "AND provider_payment_id IS NULL RETURNING id",
            (provider_payment_id,intent_id),
        ).fetchone()
        return bool(row)


def reconcile_approved_saas_payment_ci(conn, *, intent_id: UUID,
                                       authoritative_payment: dict,
                                       now: datetime | None = None) -> UUID | None:
    """NÃO usar com payload de webhook; somente GET autenticado do provedor.

    Transação e row lock garantem que evento repetido não renova a licença.
    """
    _ci_only(conn)
    with conn.transaction():
        row=conn.execute(
            "SELECT id,preparation_id,tenant_id,provider_payment_id,"
            "platform_collector_id,external_reference,expected_amount_cents,"
            "live_mode,status FROM public.saas_payment_intents "
            "WHERE id=%s FOR UPDATE", (intent_id,),
        ).fetchone()
        if not row or not row[3]:
            return None
        if row[8] not in ('PENDING','APPROVED'):
            return None
        # Mesmo chamadas repetidas devem trazer resposta autoritativa válida.
        # Um status já aprovado no banco não autoriza retornar entitlement
        # baseado em pagamento diferente ou resposta falsificada.
        if not matches_approved_payment(
            ExpectedPayment(provider_payment_id=row[3],collector_id=row[4],
                            external_reference=row[5],amount_cents=row[6],
                            live_mode=row[7]),authoritative_payment,
        ):
            return None
        if row[8]=='APPROVED':
            saved=conn.execute(
                "SELECT id FROM public.saas_license_entitlements WHERE payment_intent_id=%s",
                (intent_id,),
            ).fetchone()
            return saved[0] if saved else None
        preparation=conn.execute(
            "SELECT s.tenant_id,s.plan_tier,s.billing_period,s.status,"
            "s.admin_user_id FROM public.saas_subscription_preparations s "
            "WHERE s.id=%s FOR UPDATE",(row[1],),
        ).fetchone()
        if not preparation or preparation[3]!='PENDING_PAYMENT' or preparation[0]!=row[2]:
            return None
        if not conn.execute(
            "SELECT 1 FROM public.memberships WHERE tenant_id=%s AND user_id=%s "
            "AND role='TENANT_ADMIN' AND status='ATIVA'",
            (preparation[0],preparation[4]),
        ).fetchone():
            return None
        start=now or datetime.now(timezone.utc)
        end=_end_of_term(start,preparation[2])
        entitlement=uuid4()
        conn.execute(
            "INSERT INTO public.saas_license_entitlements"
            "(id,preparation_id,payment_intent_id,tenant_id,plan_tier,"
            "valid_from,valid_until) VALUES(%s,%s,%s,%s,%s,%s,%s)",
            (entitlement,row[1],intent_id,row[2],preparation[1],start,end),
        )
        conn.execute(
            "UPDATE public.saas_payment_intents "
            "SET status='APPROVED',paid_at=%s,reconciled_at=now() WHERE id=%s",
            (start,intent_id),
        )
        conn.execute(
            "INSERT INTO public.audit_events"
            "(actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref) "
            "VALUES(%s,'SYSTEM',%s,'CI_SAAS_LICENSE_ACTIVATED','SAAS_LICENSE',%s,%s,%s)",
            (preparation[4],row[2],str(entitlement),
             "Licença CI ativada somente após pagamento validado pelo provedor",
             row[3]),
        )
        return entitlement


def expire_saas_entitlement_ci(conn, *, entitlement_id: UUID,
                               now: datetime | None = None) -> bool:
    """Tolerância zero: expira ao chegar valid_until, sem saldo nem estado SaaS simulado."""
    _ci_only(conn)
    current=now or datetime.now(timezone.utc)
    result=conn.execute(
        "UPDATE public.saas_license_entitlements SET status='EXPIRED' "
        "WHERE id=%s AND status IN ('ACTIVE','SUSPENDED') AND valid_until<=%s RETURNING id",
        (entitlement_id,current),
    ).fetchone()
    return bool(result)


def revoke_after_verified_refund_ci(conn, *, intent_id: UUID,
                                    authoritative_payment: dict) -> bool:
    """Reembolso exige resposta autenticada do provedor, não o webhook isolado."""
    _ci_only(conn)
    with conn.transaction():
        row=conn.execute(
            "SELECT provider_payment_id,platform_collector_id,external_reference,"
            "expected_amount_cents,live_mode,status,tenant_id,admin_user_id "
            "FROM public.saas_payment_intents WHERE id=%s FOR UPDATE",
            (intent_id,),
        ).fetchone()
        if not row or row[5]!='APPROVED':
            return False
        if not matches_full_refund(
            ExpectedPayment(provider_payment_id=row[0],collector_id=row[1],
                            external_reference=row[2],amount_cents=row[3],
                            live_mode=row[4]),authoritative_payment):
            return False
        conn.execute(
            "UPDATE public.saas_payment_intents SET status='REFUNDED' WHERE id=%s",(intent_id,),
        )
        conn.execute(
            "UPDATE public.saas_license_entitlements "
            "SET status='REVOKED',suspended_at=now() "
            "WHERE payment_intent_id=%s AND status IN ('ACTIVE','SUSPENDED','EXPIRED')",(intent_id,),
        )
        conn.execute(
            "INSERT INTO public.audit_events"
            "(actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref)"
            "VALUES(%s,'SYSTEM',%s,'CI_SAAS_REFUND_REVOKED','SAAS_PAYMENT',%s,%s,%s)",
            (row[7],row[6],str(intent_id),
             "Estorno sintético verificado por consulta ao provedor",row[0]),
        )
        return True



def record_verified_saas_webhook_ci(conn, *, provider_payment_id: str,
                                    request_id: str, timestamp: int,
                                    payload: bytes, valid_signature: bool) -> bool:
    """Registra replay sem ativar licença; requer assinatura já verificada.

    A ativação exige uma segunda chamada AUTENTICADA GET ao provedor.
    """
    _ci_only(conn)
    if (valid_signature is not True or not provider_payment_id.isdecimal()
            or not request_id or len(request_id)>128
            or timestamp<=0 or not isinstance(payload,bytes) or len(payload)>65536):
        raise LifecycleDenied("Webhook inválido ou não verificado.")
    digest=hashlib.sha256(payload).hexdigest()
    stored=conn.execute(
        "INSERT INTO public.saas_provider_webhook_receipts"
        "(provider_payment_id,provider_request_id,signature_timestamp,"
        "payload_digest,verified)"
        "VALUES(%s,%s,%s,%s,true) "
        "ON CONFLICT (provider,provider_request_id) DO NOTHING RETURNING id",
        (provider_payment_id,request_id,timestamp,digest),
    ).fetchone()
    if stored:
        return True
    # Replay idêntico é inofensivo. Mesmo request-id com payload diferente
    # caracteriza colisão suspeita: falhar fechado, não sobrescrever auditoria.
    previous=conn.execute(
        "SELECT provider_payment_id,signature_timestamp,payload_digest,verified "
        "FROM public.saas_provider_webhook_receipts "
        "WHERE provider='MERCADO_PAGO' AND provider_request_id=%s",
        (request_id,),
    ).fetchone()
    if previous != (provider_payment_id,timestamp,digest,True):
        raise LifecycleDenied("Webhook com request-id repetido e conteúdo divergente.")
    return False



def suspend_saas_entitlement_ci(conn, *, entitlement_id: UUID,
                                master_user_id: UUID, reason: str,
                                now: datetime | None = None) -> bool:
    """Suspensão apenas por Master real, com motivo e trilha de auditoria CI."""
    _ci_only(conn)
    reason = reason.strip()
    if len(reason) < 12 or len(reason) > 240:
        raise LifecycleDenied("Justificativa de suspensão obrigatória.")
    instant = now or datetime.now(timezone.utc)
    with conn.transaction():
        actor = conn.execute(
            "SELECT 1 FROM public.users WHERE id=%s AND is_master "
            "AND status='ACTIVE'", (master_user_id,),
        ).fetchone()
        if not actor:
            raise LifecycleDenied("Apenas Master ativo pode suspender licença.")
        row = conn.execute(
            "UPDATE public.saas_license_entitlements "
            "SET status='SUSPENDED',suspended_at=%s "
            "WHERE id=%s AND status='ACTIVE' AND valid_until>%s "
            "RETURNING id,tenant_id", (instant,entitlement_id,instant),
        ).fetchone()
        if not row:
            return False
        conn.execute(
            "INSERT INTO public.audit_events(actor_id,actor_role,tenant_id,"
            "action,object_type,object_id,reason,evidence_ref)"
            "VALUES(%s,'MASTER',%s,'CI_SAAS_SUSPENDED','SAAS_LICENSE',%s,%s,%s)",
            (master_user_id,row[1],str(row[0]),reason,"CI_MANUAL_APPROVAL_ONLY"),
        )
        return True


def resume_saas_entitlement_ci(conn, *, entitlement_id: UUID,
                               master_user_id: UUID,
                               authoritative_payment: dict,
                               now: datetime | None = None) -> bool:
    """Reativa apenas licença não vencida, sem reiniciar prazo ou cobrar.

    Exige pagamento ainda aprovado na API de pagamentos autenticada.
    Bloqueia devoluções, tenants suspensos, licença expirada ou revogada.
    """
    _ci_only(conn)
    instant = now or datetime.now(timezone.utc)
    with conn.transaction():
        actor = conn.execute(
            "SELECT 1 FROM public.users WHERE id=%s AND is_master "
            "AND status='ACTIVE'", (master_user_id,),
        ).fetchone()
        if not actor:
            raise LifecycleDenied("Apenas Master ativo pode retomar licença.")
        license_row = conn.execute(
            "SELECT e.tenant_id,e.payment_intent_id,e.valid_until,e.status "
            "FROM public.saas_license_entitlements e WHERE e.id=%s FOR UPDATE",
            (entitlement_id,),
        ).fetchone()
        if (not license_row or license_row[3]!='SUSPENDED'
                or license_row[2]<=instant):
            return False
        tenant = conn.execute(
            "SELECT 1 FROM public.tenants WHERE id=%s AND status='ATIVO'",
            (license_row[0],),
        ).fetchone()
        if not tenant:
            return False
        payment = conn.execute(
            "SELECT provider_payment_id,platform_collector_id,external_reference,"
            "expected_amount_cents,live_mode,status "
            "FROM public.saas_payment_intents WHERE id=%s FOR UPDATE",
            (license_row[1],),
        ).fetchone()
        if not payment or payment[5]!='APPROVED' or not payment[0]:
            return False
        if not matches_approved_payment(
            ExpectedPayment(
                provider_payment_id=payment[0],collector_id=payment[1],
                external_reference=payment[2],amount_cents=payment[3],
                live_mode=payment[4]),
            authoritative_payment,
        ):
            return False
        updated = conn.execute(
            "UPDATE public.saas_license_entitlements "
            "SET status='ACTIVE',suspended_at=NULL "
            "WHERE id=%s AND status='SUSPENDED' AND valid_until>%s RETURNING id",
            (entitlement_id,instant),
        ).fetchone()
        if not updated:
            return False
        conn.execute(
            "INSERT INTO public.audit_events(actor_id,actor_role,tenant_id,"
            "action,object_type,object_id,reason,evidence_ref)"
            "VALUES(%s,'MASTER',%s,'CI_SAAS_RESUMED','SAAS_LICENSE',%s,%s,%s)",
            (master_user_id,license_row[0],str(entitlement_id),
             "Retomada em laboratório CI com pagamento aprovado revalidado",
             payment[0]),
        )
        return True
