"""
FRcaixinha 2.2 — Rotas de Contribuições Mensais e Cotas
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 4.5, 6.3, 6.4, 7.1, 14.1 e 16.4)
Precisão Monetária: Uso de Decimal com ROUND_HALF_UP e prevenção estrita de saldo fictício.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List, Optional
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date, timedelta
from ..models import ContributionResponse, ContributionPayRequest, ContributionPayResponse, QuotaResponse, MemberAnnualPreviewResponse
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection
from ..config import settings

router = APIRouter(prefix="/tenants/{tenant_id}", tags=["Contribuições e Cotas"])

CENTS = Decimal("0.01")

def to_cents(val) -> Decimal:
    if isinstance(val, Decimal):
        return val.quantize(CENTS, rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(CENTS, rounding=ROUND_HALF_UP)

@router.get("/quotas", response_model=List[QuotaResponse])
async def list_tenant_quotas(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Lista cotas ativas da caixinha:
    - Master: RECUSADO com 403 (Cláusula 2.8)
    - Admin: Vê todas as cotas do seu tenant
    - Membro: Vê apenas suas próprias cotas
    """
    require_tenant_access(tenant_id, session)

    if session.role == "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Master não possui autorização para consultar cotas patrimoniais de caixinhas."
        )

    query = """
        SELECT q.id, q.tenant_id, q.membership_id, q.quota_number, q.value_brl, q.status, q.created_at
        FROM quotas q
        JOIN memberships m ON q.membership_id = m.id
        WHERE q.tenant_id = $1
    """
    params = [uuid.UUID(tenant_id)]

    if session.role == "TENANT_MEMBER":
        query += " AND m.user_id = $2 AND m.role = 'TENANT_MEMBER' AND m.status = 'ATIVA'"
        params.append(uuid.UUID(session.user_id))

    query += " ORDER BY q.quota_number ASC;"

    rows = await conn.fetch(query, *params)
    return [
        QuotaResponse(
            id=str(r["id"]),
            tenant_id=str(r["tenant_id"]),
            membership_id=str(r["membership_id"]),
            quota_number=r["quota_number"],
            value_brl=to_cents(r["value_brl"]),
            status=r["status"],
            created_at=r["created_at"]
        )
        for r in rows
    ]


@router.get("/contributions", response_model=List[ContributionResponse])
async def list_tenant_contributions(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Lista contribuições mensais de cotas:
    Usa u.full_name em conformidade com o schema 001.
    """
    require_tenant_access(tenant_id, session)

    if session.role == "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Master não possui autorização para consultar contribuições de caixinhas."
        )

    query = """
        SELECT c.id, c.tenant_id, c.cycle_id, c.membership_id, u.full_name as member_name,
               c.competence, c.due_date, c.amount_due, c.amount_paid,
               c.payment_status, c.due_status, c.paid_at
        FROM contributions c
        JOIN memberships m ON c.membership_id = m.id
        JOIN users u ON m.user_id = u.id
        WHERE c.tenant_id = $1
    """
    params = [uuid.UUID(tenant_id)]

    if session.role == "TENANT_MEMBER":
        query += " AND m.user_id = $2 AND m.role = 'TENANT_MEMBER' AND m.status = 'ATIVA'"
        params.append(uuid.UUID(session.user_id))

    query += " ORDER BY c.competence DESC, c.due_date ASC;"

    rows = await conn.fetch(query, *params)
    return [
        ContributionResponse(
            id=str(r["id"]),
            tenant_id=str(r["tenant_id"]),
            cycle_id=str(r["cycle_id"]),
            membership_id=str(r["membership_id"]),
            member_name=r["member_name"],
            competence=r["competence"],
            due_date=r["due_date"],
            amount_due=to_cents(r["amount_due"]),
            amount_paid=to_cents(r["amount_paid"]),
            payment_status=r["payment_status"],
            due_status=r["due_status"],
            paid_at=r["paid_at"]
        )
        for r in rows
    ]



@router.get("/contributions/annual-preview/me", response_model=MemberAnnualPreviewResponse)
async def get_member_annual_preview(
    tenant_id: str,
    year: int = Query(default=2027, ge=2020, le=2100),
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection),
):
    """Resumo real de registros próprios, jamais apuração de lucro.

    SELECT executado com RLS do usuário e tenant ativos. A soma dos valores
    pagos é apenas dado cadastral; não presume conciliação bancária.
    """
    require_tenant_access(tenant_id, session)
    if session.role != "TENANT_MEMBER":
        raise HTTPException(
            status_code=403,
            detail="Demonstrativo individual exclusivo do perfil Membro."
        )

    row = await conn.fetchrow("""
        SELECT count(*)::integer AS contribution_count,
               count(*) FILTER (WHERE c.payment_status != 'QUITADA')::integer
                 AS pending_count,
               COALESCE(sum(c.amount_due),0) AS total_due,
               COALESCE(sum(c.amount_paid),0) AS amount_paid_recorded
        FROM public.contributions c
        JOIN public.memberships m ON m.id=c.membership_id
        WHERE c.tenant_id=$1
          AND m.tenant_id=$1 AND m.user_id=$2
          AND m.role='TENANT_MEMBER' AND m.status='ATIVA'
          AND c.competence LIKE $3
    """, uuid.UUID(tenant_id), uuid.UUID(session.user_id), f"{year:04d}-%")

    due = to_cents(row["total_due"])
    paid = to_cents(row["amount_paid_recorded"])
    if paid < 0 or due < 0 or paid > due:
        raise HTTPException(
            status_code=503,
            detail="Prévia indisponível: valores registrados inconsistentes."
        )
    return MemberAnnualPreviewResponse(
        tenant_id=tenant_id,
        year=year,
        contribution_count=row["contribution_count"],
        pending_count=row["pending_count"],
        total_due=due,
        amount_paid_recorded=paid,
        remaining_due=due-paid,
        profit_amount=None,
    )


@router.post("/contributions/{contribution_id}/pay", response_model=ContributionPayResponse)
async def pay_contribution(
    tenant_id: str,
    contribution_id: str,
    payload: ContributionPayRequest,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Registra intenção de pagamento de contribuição mensal (Cláusulas 4.5 e 16.4):
    REGRA DE SEGURANÇA PATRIMONIAL INVIOLÁVEL:
    - Sem provedor Pix/bancário ativo ou webhook autenticado, uma requisição do cliente
      NÃO pode marcar a contribuição como 'QUITADA' nem lançar caixa/capital no razão contábil.
    - Cria uma intenção em 'pix_payment_intents' com status 'PENDENTE'.
    - Lançamento contábil e reconhecimento de capital confirmado são estritamente condicionados
      à liquidação externa comprovada, impedindo a geração de saldo fictício.
    """
    require_tenant_access(tenant_id, session)

    # Não apresentar como pagável o código fictício sem provedor configurado.
    raise HTTPException(status_code=503, detail="Cobrança Pix indisponível até integração com provedor e conciliação autenticada.")

    if session.role == "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Master não realiza operações financeiras de caixinhas."
        )

    row = await conn.fetchrow("""
        SELECT c.id, c.tenant_id, c.cycle_id, c.membership_id, c.competence, c.due_date,
               c.amount_due, c.amount_paid, c.payment_status, c.due_status, m.user_id, u.full_name as member_name
        FROM contributions c
        JOIN memberships m ON c.membership_id = m.id
        JOIN users u ON m.user_id = u.id
        WHERE c.id = $1 AND c.tenant_id = $2
        FOR UPDATE;
    """, uuid.UUID(contribution_id), uuid.UUID(tenant_id))

    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contribuição não encontrada.")

    if session.role == "TENANT_MEMBER" and str(row["user_id"]) != str(session.user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Você só pode pagar contribuições vinculadas à sua própria cota."
        )

    amount_requested = to_cents(payload.amount)
    amount_cents = int((amount_requested * Decimal("100")).quantize(Decimal("1")))

    # Registro de Intenção Pix Pendente (Gera chave de idempotência e dados para QR Code)
    intent_id = uuid.uuid4()
    idempotency_key = f"contrib-{contribution_id}-{amount_cents}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
    pix_payload = f"00020126580014br.gov.bcb.pix0136{intent_id}5204000053039865406{amount_requested:.2f}5802BR5920FRcaixinha6009Belem62070503***6304"
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    await conn.execute("""
        INSERT INTO pix_payment_intents (
            id, tenant_id, contribution_id, payer_user_id, amount_cents,
            status, idempotency_key, pix_copy_paste, expires_at, created_at
        ) VALUES ($1, $2, $3, $4, $5, 'PENDENTE', $6, $7, $8, NOW())
        ON CONFLICT (tenant_id, idempotency_key) DO NOTHING;
    """, intent_id, uuid.UUID(tenant_id), uuid.UUID(contribution_id), uuid.UUID(session.user_id),
       amount_cents, idempotency_key, pix_payload, expires_at)

    await conn.execute("""
        INSERT INTO audit_events (id, actor_id, actor_role, tenant_id, action, object_type, object_id, reason, evidence_ref)
        VALUES ($1, $2, $3, $4, 'INTENCAO_PAGAMENTO_PIX', 'CONTRIBUTION', $5, $6, $7);
    """, uuid.uuid4(), uuid.UUID(session.user_id), session.role, uuid.UUID(tenant_id),
       contribution_id, f"Intenção de pagamento Pix de R$ {amount_requested} gerada. Aguardando conciliação.", f"INTENT-{intent_id}")

    return ContributionPayResponse(
        status="AGUARDANDO_CONCILIACAO",
        contribution_id=contribution_id,
        amount_requested=amount_requested,
        intent_id=str(intent_id),
        pix_copy_paste=pix_payload,
        message="Intenção de pagamento Pix registrada com sucesso. A baixa contábil e a confirmação de capital ocorrerão exclusivamente após a liquidação bancária via webhook autenticado.",
        is_reconciled=False
    )
