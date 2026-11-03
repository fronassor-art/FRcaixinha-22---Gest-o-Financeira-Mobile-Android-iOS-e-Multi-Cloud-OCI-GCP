"""
FRcaixinha 2.2 — Rotas do Livro-Razão Contábil (Partidas Dobradas Imutáveis)
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 14.1 e 16.4)
Precisão Monetária: Uso de Decimal com ROUND_HALF_UP.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
import uuid
from decimal import Decimal, ROUND_HALF_UP
from ..models import LedgerAccountResponse, LedgerTransactionResponse, LedgerEntryResponse, LedgerIntegrityPreviewResponse
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection

router = APIRouter(prefix="/tenants/{tenant_id}/ledger", tags=["Livro-Razão e Contabilidade"])

CENTS = Decimal("0.01")


def _summarize_integrity_rows(rows, tenant_id: str):
    """Pure aggregation: detect imbalanced postings, never assert bank reconciliation."""
    if len(rows) > 500:
        raise HTTPException(status_code=503, detail="Prévia contábil indisponível: limite de consulta.")
    seen = set()
    invalid = 0
    for row in rows:
        try:
            identifier = str(uuid.UUID(str(row["transaction_id"])))
            entries = row["entry_count"]
            dr_count = row["debit_entries"]
            cr_count = row["credit_entries"]
            bad_entries = row["invalid_entries"]
            dr = row["debit_cents"]
            cr = row["credit_cents"]
            if (not identifier or identifier in seen or
                    any(type(x) is not int for x in
                        (entries, dr_count, cr_count, bad_entries, dr, cr)) or
                    min(entries, dr_count, cr_count, bad_entries, dr, cr) < 0):
                raise ValueError("Invalid ledger aggregates")
        except (KeyError, ValueError, TypeError, OverflowError):
            raise HTTPException(status_code=503, detail="Prévia contábil indisponível: dados inválidos.")
        seen.add(identifier)
        if (entries < 2 or dr_count < 1 or cr_count < 1 or
                entries != dr_count + cr_count or bad_entries > 0 or
                dr <= 0 or cr <= 0 or dr != cr):
            invalid += 1
    total = len(rows)
    return LedgerIntegrityPreviewResponse(
        source="POSTGRESQL_RLS",
        scope="TENANT_ADMIN_READ_ONLY",
        tenant_id=tenant_id,
        checked_transactions=total,
        balanced_transactions=total-invalid,
        review_required_transactions=invalid,
        status="NO_TRANSACTIONS" if total == 0 else
            ("REVIEW_REQUIRED" if invalid else "BALANCED"),
        bank_reconciled=False,
        financial_closing_authorized=False,
    )


@router.get("/integrity-preview", response_model=LedgerIntegrityPreviewResponse)
async def get_ledger_integrity_preview(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Aggregate ledger only for authorized tenant Admin; no journal entries exposed."""
    require_tenant_access(tenant_id, session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403, detail="Prévia contábil exclusiva do administrador.")
    try:
        tenant=uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Identificador de caixinha inválido.")
    rows = await conn.fetch("""
        SELECT t.id AS transaction_id,
               count(e.id)::integer AS entry_count,
               count(e.id) FILTER (WHERE e.entry_type='DR')::integer AS debit_entries,
               count(e.id) FILTER (WHERE e.entry_type='CR')::integer AS credit_entries,
               COALESCE(sum(e.amount_cents) FILTER (WHERE e.entry_type='DR'),0)::bigint AS debit_cents,
               COALESCE(sum(e.amount_cents) FILTER (WHERE e.entry_type='CR'),0)::bigint AS credit_cents,
               count(e.id) FILTER (WHERE e.amount_cents IS NULL
                       OR e.amount_cents<=0 OR a.id IS NULL
                       OR e.entry_type NOT IN ('DR','CR'))::integer AS invalid_entries
        FROM public.ledger_transactions t
        LEFT JOIN public.ledger_entries e
          ON e.transaction_id=t.id AND e.tenant_id=t.tenant_id
        LEFT JOIN public.ledger_accounts a
          ON a.id=e.account_id AND a.tenant_id=t.tenant_id
        WHERE t.tenant_id=$1
        GROUP BY t.id
        ORDER BY t.id
        LIMIT 501
    """, tenant)
    return _summarize_integrity_rows(rows, tenant_id)


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
