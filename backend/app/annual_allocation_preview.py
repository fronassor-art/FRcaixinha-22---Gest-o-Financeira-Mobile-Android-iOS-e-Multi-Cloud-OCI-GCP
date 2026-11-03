"""FRcaixinha AI Studio — cálculo PURO de prévia de rateio.
Não recebe conexão, não persiste, não faz Pix e não autoriza fechamento.
"""
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR, InvalidOperation

CENT=Decimal("0.01")
ADMIN_RATE=Decimal("0.15")
MAX_AMOUNT=Decimal("1000000000.00")

def _cent_amount(value):
    try:
        amount=Decimal(str(value))
        if (not amount.is_finite() or amount < 0 or amount > MAX_AMOUNT
                or amount!=amount.quantize(CENT)):
            raise ValueError("Valor financeiro fora de centavos.")
        return amount
    except (InvalidOperation,TypeError,OverflowError) as exc:
        raise ValueError("Valor financeiro inválido.") from exc

def annual_allocation_preview(net_profit, member_capital_days):
    """Hamilton with deterministic id tie-break; no transfer instruction."""
    profit=_cent_amount(net_profit)
    if not isinstance(member_capital_days,dict) or len(member_capital_days)>1000:
        raise ValueError("Conjunto de pesos inválido.")
    clean={}
    for member_id,raw_weight in member_capital_days.items():
        if not isinstance(member_id,str) or not member_id or len(member_id)>128:
            raise ValueError("Identificador inválido.")
        try:
            weight=Decimal(str(raw_weight))
        except (InvalidOperation,TypeError,ValueError):
            raise ValueError("Peso inválido.")
        if not weight.is_finite() or weight<0 or weight>Decimal("1000000000000000"):
            raise ValueError("Peso inválido.")
        clean[member_id]=weight
    admin=(profit*ADMIN_RATE).quantize(CENT,rounding=ROUND_HALF_UP)
    members=profit-admin
    pool_cents=int(members*100)
    total_weight=sum(clean.values(),Decimal(0))
    if total_weight==0:
        return {
            "state":"PREVIEW_NOT_SETTLED",
            "admin_provisional_cents":int(admin*100),
            "member_pool_cents":pool_cents,
            "member_shares_cents":{member_id:0 for member_id in sorted(clean)},
            "segregated_undistributed_cents":pool_cents
        }
    bases={}
    fractions=[]
    for member_id in sorted(clean):
        exact=Decimal(pool_cents)*clean[member_id]/total_weight
        whole=int(exact.to_integral_value(rounding=ROUND_FLOOR))
        bases[member_id]=whole
        fractions.append((exact-Decimal(whole),member_id))
    remaining=pool_cents-sum(bases.values())
    for _,member_id in sorted(fractions,key=lambda row:(-row[0],row[1]))[:remaining]:
        bases[member_id]+=1
    if sum(bases.values())!=pool_cents:
        raise ValueError("Rateio não fecha nos centavos.")
    return {
        "state":"PREVIEW_NOT_SETTLED",
        "admin_provisional_cents":int(admin*100),
        "member_pool_cents":pool_cents,
        "member_shares_cents":bases,
        "segregated_undistributed_cents":0
    }
