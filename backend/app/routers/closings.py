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

    # A rotina abaixo ainda marca o ciclo como liquidado sem confirmação bancária,
    # e o histórico de pagamentos parciais não permite apuração completa.
    raise HTTPException(status_code=503, detail="Fechamento indisponível até validação da apuração e conciliação da liquidação.")

    # 1. Busca dados do ciclo
    cycle = await conn.fetchrow("""
        SELECT id, year, start_date, end_date, settlement_date, status
        FROM cycles
        WHERE id = $1 AND tenant_id = $2
        FOR UPDATE;
    """, uuid.UUID(payload.cycle_id), uuid.UUID(tenant_id))

    if not cycle:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ciclo anual não encontrado.")

    if cycle["status"] == "LIQUIDADO":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ciclo já se encontra liquidado.")

    cycle_end_date = cycle["end_date"]

    # 2. Busca receita realizada na conta contábil canônica 4.1.1 (Receita Realizada de Juros, Mora e Multas)
    acc_receita = await conn.fetchrow("""
        SELECT balance_cents FROM ledger_accounts
        WHERE tenant_id = $1 AND account_code = '4.1.1';
    """, uuid.UUID(tenant_id))

    if not acc_receita:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro contábil crítico: conta de receita 4.1.1 não configurada no livro-razão."
        )

    net_profit_cents = acc_receita["balance_cents"]
    net_profit = to_cents(Decimal(str(net_profit_cents)) / Decimal("100"))

    # 3. Split 85% Membros / 15% Administrador
    admin_pool = to_cents(net_profit * Decimal("0.15"))
    member_pool = to_cents(net_profit - admin_pool)

    # 4. Membros e elegibilidade
    members_rows = await conn.fetch("""
        SELECT m.id, m.consecutive_unpaid_months, m.is_profit_eligible, u.full_name as member_name
        FROM memberships m
        JOIN users u ON m.user_id = u.id
        WHERE m.tenant_id = $1 AND m.status = 'ATIVA';
    """, uuid.UUID(tenant_id))

    # 5. Busca contribuições conciliadas (QUITADA) para cálculo exato Capital-Dias V2
    contrib_rows = await conn.fetch("""
        SELECT c.membership_id, c.amount_paid, c.paid_at
        FROM contributions c
        WHERE c.tenant_id = $1 AND c.cycle_id = $2
          AND c.payment_status = 'QUITADA' AND c.amount_paid > 0 AND c.paid_at IS NOT NULL;
    """, uuid.UUID(tenant_id), uuid.UUID(payload.cycle_id))

    # Agrupa pesos por membro
    member_weights: dict = {}
    for cr in contrib_rows:
        m_id = str(cr["membership_id"])
        amt = Decimal(str(cr["amount_paid"]))
        p_date = cr["paid_at"].date() if isinstance(cr["paid_at"], datetime) else cr["paid_at"]
        weight_item = capital_days_weight(amt, p_date, cycle_end_date)
        member_weights[m_id] = member_weights.get(m_id, Decimal("0.0000")) + weight_item

    class MemberCalc:
        def __init__(self, m_id: str, name: str, is_eligible: bool, weight: Decimal):
            self.id = m_id
            self.name = name
            self.is_eligible = is_eligible
            self.weight = weight if is_eligible else Decimal("0.0000")
            self.weight_pct = Decimal("0.00")
            self.exact_share = Decimal("0.0000")
            self.truncated_share = Decimal("0.00")
            self.remainder_fraction = Decimal("0.0000")
            self.bonus_centavos = Decimal("0.00")
            self.final_share = Decimal("0.00")

    calc_list: List[MemberCalc] = []
    for mr in members_rows:
        m_id_str = str(mr["id"])
        is_elig = (mr["consecutive_unpaid_months"] < 3) and bool(mr["is_profit_eligible"])
        raw_w = member_weights.get(m_id_str, Decimal("0.0000"))
        calc_list.append(MemberCalc(m_id_str, mr["member_name"], is_elig, raw_w))

    total_weights = sum((m.weight for m in calc_list if m.is_eligible), Decimal("0.0000"))

    # Distribuição com Método dos Maiores Restos
    if total_weights > Decimal("0.0000") and member_pool > Decimal("0.00"):
        for m in calc_list:
            if m.is_eligible and m.weight > Decimal("0.0000"):
                m.weight_pct = ((m.weight / total_weights) * Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                m.exact_share = (member_pool * (m.weight / total_weights)).quantize(Decimal("0.0001"))
                m.truncated_share = m.exact_share.quantize(CENTS, rounding=ROUND_FLOOR)
                m.remainder_fraction = m.exact_share - m.truncated_share
                m.final_share = m.truncated_share

        sum_trunc = sum((m.truncated_share for m in calc_list), Decimal("0.00"))
        residual_cents = int(((member_pool - sum_trunc) * Decimal("100")).quantize(Decimal("1")))

        sorted_m = sorted(
            [m for m in calc_list if m.is_eligible and m.weight > Decimal("0.0000")],
            key=lambda x: (-x.remainder_fraction, x.id)
        )

        idx = 0
        while residual_cents > 0 and idx < len(sorted_m):
            target = next(m for m in calc_list if m.id == sorted_m[idx].id)
            target.bonus_centavos += Decimal("0.01")
            target.final_share = to_cents(target.final_share + Decimal("0.01"))
            residual_cents -= 1
            idx += 1

    # Validação exata da soma distribuída
    total_distributed = sum((m.final_share for m in calc_list), Decimal("0.00"))
    if total_weights > Decimal("0.0000") and total_distributed != member_pool:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inconsistência de centavos no rateio: Soma distribuída R$ {total_distributed} diverge do pool de membros R$ {member_pool}."
        )

    # 6. Gravação no PostgreSQL
    closing_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO cycle_closings (
            id, tenant_id, cycle_id, closed_by_user_id, total_net_profit,
            admin_share_amount, member_pool_amount, total_capital_dias_weights,
            residual_cents_distributed, status, closed_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'CONCLUIDO', NOW());
    """, closing_id, uuid.UUID(tenant_id), uuid.UUID(payload.cycle_id), uuid.UUID(session.user_id),
       net_profit, admin_pool, member_pool, total_weights,
       int(((member_pool - sum((m.truncated_share for m in calc_list), Decimal("0.00"))) * Decimal("100")).quantize(Decimal("1"))))

    distributions_resp: List[MemberDistributionResponse] = []
    for m in calc_list:
        await conn.execute("""
            INSERT INTO cycle_profit_distributions (
                id, tenant_id, cycle_closing_id, membership_id, is_eligible,
                capital_dias_weight, exact_share, truncated_share, bonus_centavos,
                final_profit_share, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, NOW());
        """, uuid.uuid4(), uuid.UUID(tenant_id), closing_id, uuid.UUID(m.id),
           m.is_eligible, m.weight, m.exact_share, m.truncated_share,
           m.bonus_centavos, m.final_share)

        distributions_resp.append(MemberDistributionResponse(
            membership_id=m.id,
            member_name=m.name,
            is_eligible=m.is_eligible,
            capital_dias_weight=m.weight,
            weight_percentage=m.weight_pct,
            exact_share=m.exact_share,
            truncated_share=m.truncated_share,
            bonus_centavos=m.bonus_centavos,
            final_profit_share=m.final_share
        ))

    await conn.execute("""
        UPDATE cycles SET status = 'LIQUIDADO' WHERE id = $1;
    """, uuid.UUID(payload.cycle_id))

    return CycleClosingResponse(
        closing_id=str(closing_id),
        tenant_id=tenant_id,
        cycle_id=payload.cycle_id,
        total_net_profit=net_profit,
        admin_share_amount=admin_pool,
        member_pool_amount=member_pool,
        total_capital_dias_weights=total_weights,
        residual_cents_distributed=int(((member_pool - sum((m.truncated_share for m in calc_list), Decimal("0.00"))) * Decimal("100")).quantize(Decimal("1"))),
        status="CONCLUIDO",
        closed_at=datetime.utcnow(),
        distributions=distributions_resp
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
