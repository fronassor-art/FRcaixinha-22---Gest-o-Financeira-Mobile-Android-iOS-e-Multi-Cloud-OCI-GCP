"""
FRcaixinha 2.2 — Rotas de Fechamento de Ciclo Anual (Capital-Dias V2)
Contrato Técnico Mestre (Cláusulas 6.5, 6.6, 10.3, 10.4, 16.2 e 16.4)
Precisão Monetária: Uso de Decimal com ROUND_HALF_UP e Método dos Maiores Restos (Hamilton/Hare-Niemeyer).
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
import uuid
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from datetime import datetime, date
from ..models import (
    CycleClosePayload, CycleClosingResponse, MemberDistributionResponse
)
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection
from ..config import settings

router = APIRouter(prefix="/tenants/{tenant_id}/closings", tags=["Fechamento Anual de Ciclo"])

CENTS = Decimal("0.01")
WEIGHT_PRECISION = Decimal("0.0001")

def to_cents(val) -> Decimal:
    if isinstance(val, Decimal):
        return val.quantize(CENTS, rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(CENTS, rounding=ROUND_HALF_UP)

def capital_days_weight(amount: Decimal, paid_on: date, cycle_end: date) -> Decimal:
    """Corte na data de encerramento; data de liquidação não estende o ciclo."""
    return (amount * Decimal(max(0, (cycle_end - paid_on).days))).quantize(WEIGHT_PRECISION)

@router.post("", response_model=CycleClosingResponse)
async def close_cycle(
    tenant_id: str,
    payload: CycleClosePayload,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Fechamento e Liquidação de Ciclo Anual (Capital-Dias V2):
    - Apenas Administrador da caixinha pode executar;
    - Apura receita realizada contábil da conta canônica 4.1.1 (Receitas Operacionais);
    - Split contratual: 15% taxa administrativa / 85% pool dos membros;
    - Ponderação Capital-Dias V2: peso exato com base nos dias civis entre o pagamento conciliado e 31/12;
    - Membros com 3 meses consecutivos inadimplentes são excluídos do lucro, preservando o capital integralmente;
    - Distribuição de centavos residuais pelo Método dos Maiores Restos (Hare-Niemeyer) com desempate por membership_id.
    """
    require_tenant_access(tenant_id, session)

    if session.role != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores de caixinha podem realizar o fechamento anual de ciclo."
        )

    # M22800: fechamento financeiro LEGADO removido da rota pública.
    # Simulações contratuais ficam em módulos próprios e não liquidam ciclos.
    raise HTTPException(
        status_code=503,
        detail="Fechamento indisponível até conciliação independente, perdas e rateio auditado.",
    )


@router.get("/{cycle_id}", response_model=CycleClosingResponse)
async def get_cycle_closing(
    tenant_id: str,
    cycle_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Recupera dados de apuração e rateio de um ciclo já fechado.
    Usa u.full_name em conformidade com o schema 001.
    """
    require_tenant_access(tenant_id, session)
    # A API antiga retornava o rateio global sem uma verificação explícita
    # de papel. O membro recebe somente seu demonstrativo INDIVIDUAL
    # (endpoint separado, ainda não implementado).
    if session.role != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fechamento consolidado exclusivo do administrador.",
        )

    closing = await conn.fetchrow("""
        SELECT * FROM cycle_closings WHERE tenant_id = $1 AND cycle_id = $2;
    """, uuid.UUID(tenant_id), uuid.UUID(cycle_id))

    if not closing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fechamento do ciclo não encontrado.")

    dist_rows = await conn.fetch("""
        SELECT d.*, u.full_name as member_name
        FROM cycle_profit_distributions d
        JOIN memberships m ON d.membership_id = m.id
        JOIN users u ON m.user_id = u.id
        WHERE d.tenant_id = $1 AND d.cycle_closing_id = $2
        ORDER BY d.final_profit_share DESC, d.membership_id ASC;
    """, uuid.UUID(tenant_id), closing["id"])

    distributions = [
        MemberDistributionResponse(
            membership_id=str(r["membership_id"]),
            member_name=r["member_name"],
            is_eligible=r["is_eligible"],
            capital_dias_weight=Decimal(str(r["capital_dias_weight"])),
            weight_percentage=to_cents(Decimal(str(r["final_profit_share"])) / to_cents(closing["member_pool_amount"]) * Decimal("100")) if to_cents(closing["member_pool_amount"]) > Decimal("0.00") else Decimal("0.00"),
            exact_share=Decimal(str(r["exact_share"])),
            truncated_share=to_cents(r["truncated_share"]),
            bonus_centavos=to_cents(r["bonus_centavos"]),
            final_profit_share=to_cents(r["final_profit_share"])
        )
        for r in dist_rows
    ]

    return CycleClosingResponse(
        closing_id=str(closing["id"]),
        tenant_id=str(closing["tenant_id"]),
        cycle_id=str(closing["cycle_id"]),
        total_net_profit=to_cents(closing["total_net_profit"]),
        admin_share_amount=to_cents(closing["admin_share_amount"]),
        member_pool_amount=to_cents(closing["member_pool_amount"]),
        total_capital_dias_weights=Decimal(str(closing["total_capital_dias_weights"])),
        residual_cents_distributed=closing["residual_cents_distributed"],
        status=closing["status"],
        closed_at=closing["closed_at"],
        distributions=distributions
    )
