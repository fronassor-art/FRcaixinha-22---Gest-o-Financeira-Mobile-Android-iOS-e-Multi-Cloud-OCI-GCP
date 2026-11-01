"""
FRcaixinha 2.2 — Rotas do Livro-Razão Contábil (Partidas Dobradas Imutáveis)
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 14.1 e 16.4)
Precisão Monetária: Uso de Decimal com ROUND_HALF_UP.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid
from decimal import Decimal, ROUND_HALF_UP
from ..models import LedgerAccountResponse, LedgerTransactionResponse, LedgerEntryResponse
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection

router = APIRouter(prefix="/tenants/{tenant_id}/ledger", tags=["Livro-Razão e Contabilidade"])

CENTS = Decimal("0.01")

@router.get("/accounts", response_model=List[LedgerAccountResponse])
async def list_ledger_accounts(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Plano de contas e saldos consolidados da caixinha:
    - Master: RECUSADO com 403 (Cláusula 2.8 de Segregação Patrimonial);
    - Membro: RECUSADO com 403 (demonstrativo interno gerencial do administrador);
    - Admin: Acesso total às contas do seu próprio tenant.
    """
    require_tenant_access(tenant_id, session)

    if session.role == "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Master não possui autorização para consultar contas contábeis de caixinhas."
        )

    if session.role == "TENANT_MEMBER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Membros não possuem autorização analítica ao plano de contas administrativo."
        )

    rows = await conn.fetch("""
        SELECT id, tenant_id, account_code, account_name, account_type, balance_cents
        FROM ledger_accounts
        WHERE tenant_id = $1
        ORDER BY account_code ASC;
    """, uuid.UUID(tenant_id))

    return [
        LedgerAccountResponse(
            id=str(r["id"]),
            tenant_id=str(r["tenant_id"]),
            account_code=r["account_code"],
            account_name=r["account_name"],
            account_type=r["account_type"],
            balance_cents=r["balance_cents"],
            balance_brl=(Decimal(str(r["balance_cents"])) / Decimal("100")).quantize(CENTS, rounding=ROUND_HALF_UP)
        )
        for r in rows
    ]


@router.get("/transactions", response_model=List[LedgerTransactionResponse])
async def list_ledger_transactions(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Extrato de transações em partidas dobradas:
    - Master: RECUSADO com 403 (Cláusula 2.8);
    - Membro: RECUSADO com 403;
    - Admin: Vê as transações e entradas correspondentes.
    """
    require_tenant_access(tenant_id, session)

    if session.role in ("MASTER", "TENANT_MEMBER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido ao Livro-Razão Analítico."
        )

    tx_rows = await conn.fetch("""
        SELECT id, tenant_id, transaction_date, description, reference_id
        FROM ledger_transactions
        WHERE tenant_id = $1
        ORDER BY transaction_date DESC;
    """, uuid.UUID(tenant_id))

    results = []
    for tx in tx_rows:
        entries = await conn.fetch("""
            SELECT e.id, e.account_id, a.account_name, e.entry_type, e.amount_cents
            FROM ledger_entries e
            JOIN ledger_accounts a ON e.account_id = a.id
            WHERE e.transaction_id = $1 AND e.tenant_id = $2
            ORDER BY e.entry_type DESC;
        """, tx["id"], uuid.UUID(tenant_id))

        results.append(LedgerTransactionResponse(
            id=str(tx["id"]),
            tenant_id=str(tx["tenant_id"]),
            transaction_date=tx["transaction_date"],
            description=tx["description"],
            reference_id=tx["reference_id"],
            entries=[
                LedgerEntryResponse(
                    id=str(e["id"]),
                    account_id=str(e["account_id"]),
                    account_name=e["account_name"],
                    entry_type=e["entry_type"],
                    amount_cents=e["amount_cents"],
                    amount_brl=(Decimal(str(e["amount_cents"])) / Decimal("100")).quantize(CENTS, rounding=ROUND_HALF_UP)
                )
                for e in entries
            ]
        ))

    return results
