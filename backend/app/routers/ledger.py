"""
FRcaixinha AI Studio Mobile — Leitura do Livro-Razão (partidas dobradas)
Projeto isolado. Consultas autorizadas por sessao, tenant e RLS.
Precisão Monetária: Uso de Decimal com ROUND_HALF_UP.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import List
import uuid
from decimal import Decimal, ROUND_HALF_UP
from ..models import (
    LedgerAccountResponse, LedgerTransactionResponse, LedgerEntryResponse,
    LedgerIntegrityPreviewResponse, LedgerAccountJournalEntryResponse,
    LedgerAccountJournalPageResponse, LedgerAccountDirectoryResponse,
    LedgerAccountDirectoryItemResponse,
)
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection

router = APIRouter(prefix="/tenants/{tenant_id}/ledger", tags=["Livro-Razão e Contabilidade"])

CENTS = Decimal("0.01")
MAX_LEDGER_ACCOUNTS = 500
MAX_LEDGER_TRANSACTIONS = 500
MAX_LEDGER_ENTRIES_PER_TRANSACTION = 100
MAX_LEDGER_ACCOUNT_JOURNAL_PAGE_SIZE = 50


def _require_ledger_bound(rows, limit: int):
    """Recusa resposta truncada: nunca apresenta extrato incompleto como completo."""
    if len(rows) > limit:
        raise HTTPException(
            status_code=503,
            detail="Consulta contábil excede o limite seguro; paginação pendente.",
        )
    return rows


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



def _validate_directory_accounts(rows, tenant: uuid.UUID) -> list:
    """Rejeita metadados de conta duplicados, cross-tenant ou malformados."""
    _require_ledger_bound(rows, MAX_LEDGER_ACCOUNTS)
    accounts = []
    seen_ids, seen_codes = set(), set()
    for row in rows:
        try:
            identifier = str(uuid.UUID(str(row["id"])))
            owner = str(uuid.UUID(str(row["tenant_id"])))
            code, name, kind = (row["account_code"], row["account_name"],
                                row["account_type"])
            if (
                owner != str(tenant) or identifier in seen_ids
                or not isinstance(code, str) or not 1 <= len(code) <= 24
                or not code[0].isalnum()
                or not all(c.isascii() and (c.isalnum() or c in "._-") for c in code)
                or code in seen_codes
                or not isinstance(name, str) or not 1 <= len(name.strip()) <= 160
                or not isinstance(kind, str) or not 1 <= len(kind.strip()) <= 48
                or any(ord(c) < 32 for c in name + kind)
            ):
                raise ValueError("Unsafe account metadata")
        except (KeyError, TypeError, ValueError, OverflowError):
            raise HTTPException(
                status_code=503,
                detail="Diretório contábil indisponível: metadados inválidos.",
            )
        seen_ids.add(identifier)
        seen_codes.add(code)
        accounts.append(LedgerAccountDirectoryItemResponse(
            id=identifier, account_code=code, account_name=name, account_type=kind,
        ))
    return accounts


@router.get("/accounts/directory", response_model=LedgerAccountDirectoryResponse)
async def list_ledger_account_directory(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn=Depends(get_rls_db_connection),
):
    """Metadados das contas, SEM saldos, inclusive quando nao ha transacoes.

    Esta consulta NAO autoriza auditoria, fechamento, valor de saldo ou
    lançamentos financeiros, e nunca usa o Master para ler contas de tenants.
    """
    require_tenant_access(tenant_id, session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403, detail="Diretório contábil exclusivo do administrador.")
    try:
        tenant = uuid.UUID(tenant_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Identificador de caixinha inválido.")
    rows = await conn.fetch("""
        SELECT id, tenant_id, account_code, account_name, account_type
        FROM public.ledger_accounts
        WHERE tenant_id=$1
        ORDER BY account_code ASC, id ASC
        LIMIT 501
    """, tenant)
    return LedgerAccountDirectoryResponse(
        tenant_id=str(tenant),
        accounts=_validate_directory_accounts(rows, tenant),
        balance_values_hidden=True,
        complete_ledger_verified=False,
        bank_reconciled=False,
        financial_closing_authorized=False,
    )


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
        ORDER BY account_code ASC
        LIMIT 501;
    """, uuid.UUID(tenant_id))
    _require_ledger_bound(rows, MAX_LEDGER_ACCOUNTS)

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
        ORDER BY transaction_date DESC, id DESC
        LIMIT 501;
    """, uuid.UUID(tenant_id))
    _require_ledger_bound(tx_rows, MAX_LEDGER_TRANSACTIONS)

    results = []
    for tx in tx_rows:
        entries = await conn.fetch("""
            SELECT e.id, e.account_id, a.account_name, e.entry_type, e.amount_cents
            FROM ledger_entries e
            JOIN ledger_accounts a
              ON e.account_id = a.id AND a.tenant_id = e.tenant_id
            WHERE e.transaction_id = $1 AND e.tenant_id = $2
            ORDER BY e.entry_type DESC, e.id ASC
            LIMIT 101;
        """, tx["id"], uuid.UUID(tenant_id))
        _require_ledger_bound(entries, MAX_LEDGER_ENTRIES_PER_TRANSACTION)

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


# Consulta analitica paginada de UMA conta. Nao altera as rotas antigas,
# nem pretende validar saldo/conciliacao de todo o livro-razão.
@router.get(
    "/accounts/{account_id}/entries",
    response_model=LedgerAccountJournalPageResponse,
)
async def list_ledger_account_entries(
    tenant_id: str,
    account_id: str,
    page: int = Query(1, ge=1, le=1000),
    page_size: int = Query(25, ge=1, le=MAX_LEDGER_ACCOUNT_JOURNAL_PAGE_SIZE),
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection),
):
    require_tenant_access(tenant_id, session)
    if session.role != "TENANT_ADMIN":
        raise HTTPException(status_code=403, detail="Consulta exclusiva do administrador da caixinha.")
    try:
        tenant = uuid.UUID(tenant_id)
        account = uuid.UUID(account_id)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Identificador contábil inválido.")
    if type(page) is not int or not (1 <= page <= 1000) or (
        type(page_size) is not int or not (1 <= page_size <= MAX_LEDGER_ACCOUNT_JOURNAL_PAGE_SIZE)
    ):
        raise HTTPException(status_code=422, detail="Paginação inválida.")

    # Diferencia conta inexistente de ausência de lançamentos, sempre no mesmo tenant.
    active = await conn.fetchrow(
        "SELECT id FROM public.ledger_accounts "
        "WHERE tenant_id=$1 AND id=$2 LIMIT 1",
        tenant, account,
    )
    if active is None:
        raise HTTPException(status_code=404, detail="Conta contábil não encontrada.")

    rows = await conn.fetch("""
        SELECT e.id, e.transaction_id, t.transaction_date, t.description,
               t.reference_id, e.entry_type, e.amount_cents
        FROM public.ledger_entries e
        JOIN public.ledger_transactions t
          ON t.id=e.transaction_id AND t.tenant_id=e.tenant_id
        WHERE e.tenant_id=$1 AND e.account_id=$2
        ORDER BY t.transaction_date DESC, t.id DESC, e.id DESC
        LIMIT $3 OFFSET $4
    """, tenant, account, page_size + 1, (page - 1) * page_size)

    has_more = len(rows) > page_size
    result = []
    seen = set()
    for record in rows[:page_size]:
        try:
            entry_id = str(uuid.UUID(str(record["id"])))
            tx_id = str(uuid.UUID(str(record["transaction_id"])))
            cents = record["amount_cents"]
            entry_type = record["entry_type"]
            posted = record["transaction_date"]
            description = record["description"]
            reference = record["reference_id"]
            if (
                entry_id in seen
                or type(cents) is not int or cents <= 0 or cents > 100000000000
                or entry_type not in ("DR", "CR")
                or not isinstance(description, str) or not description.strip()
                or len(description) > 500
                or not isinstance(reference, str) or not reference.strip()
                or len(reference) > 200
                or posted is None
            ):
                raise ValueError("Invalid journal entry")
        except (KeyError, TypeError, ValueError, OverflowError):
            raise HTTPException(status_code=503, detail="Dados contábeis inválidos: consulta não exibida.")
        seen.add(entry_id)
        result.append(LedgerAccountJournalEntryResponse(
            id=entry_id,
            transaction_id=tx_id,
            transaction_date=posted,
            description=description,
            reference_id=reference,
            entry_type=entry_type,
            amount_cents=cents,
            amount_brl=(Decimal(cents) / Decimal(100)).quantize(CENTS),
        ))
    return LedgerAccountJournalPageResponse(
        tenant_id=str(tenant),
        account_id=str(account),
        page=page,
        page_size=page_size,
        has_more=has_more,
        entries=result,
        complete_ledger_verified=False,
        bank_reconciled=False,
        financial_closing_authorized=False,
    )
