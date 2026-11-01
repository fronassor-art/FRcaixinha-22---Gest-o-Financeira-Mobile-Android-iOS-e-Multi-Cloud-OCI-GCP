"""
FRcaixinha 2.2 — Rotas de Empréstimos (Tabela Price, Imputação e Quitação Antecipada)
Contrato Técnico Mestre (Cláusulas 2.3, 2.8, 4.2, 5.4, 8.2, 8.4, 8.5, 8.6, 8.8, 16.2 e 16.4)
Precisão Monetária: Uso de Decimal com ROUND_HALF_UP (Sem uso de float para cálculos autoritativos).
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
import uuid
from decimal import Decimal, ROUND_HALF_UP, ROUND_FLOOR
from datetime import date, datetime, timedelta
from ..models import (
    LoanSimulateRequest, LoanSimulateResponse, InstallmentScheduleItem,
    LoanRequestPayload, LoanResponse, LoanInstallmentResponse,
    LoanRepayPayload, LoanRepayResponse, LoanEarlySettlementResponse
)
from ..dependencies import get_current_session, require_tenant_access, AuthenticatedSession
from ..database import get_rls_db_connection
from ..config import settings

router = APIRouter(prefix="/tenants/{tenant_id}/loans", tags=["Empréstimos e Tabela Price"])

CENTS = Decimal("0.01")
RATE_PRECISION = Decimal("0.0001")

def to_cents(val) -> Decimal:
    """Arredonda estritamente para centavos usando ROUND_HALF_UP contratual."""
    if isinstance(val, Decimal):
        return val.quantize(CENTS, rounding=ROUND_HALF_UP)
    return Decimal(str(val)).quantize(CENTS, rounding=ROUND_HALF_UP)

def compute_price_schedule(
    principal: Decimal,
    term_months: int,
    monthly_rate: Decimal = Decimal("0.20"),
    disbursement_date: Optional[date] = None,
    first_due_date: Optional[date] = None
) -> LoanSimulateResponse:
    """
    Tabela Price com amortização decrescente de juros e absorção do resíduo de centavos na última parcela.
    Suporta 1º período irregular pró-rata die (Cláusula 8.4 e 8.5).
    Precisão decimal pura via Decimal e ROUND_HALF_UP.
    """
    P = to_cents(principal)
    n = term_months
    i = Decimal(str(monthly_rate))

    is_irregular = False
    first_period_days = None
    effective_first_rate = i

    if disbursement_date and first_due_date:
        diff_days = (first_due_date - disbursement_date).days
        first_period_days = diff_days
        if diff_days != 30 and diff_days > 0:
            is_irregular = True
            # Taxa diária contratual: i * (dias / 30)
            effective_first_rate = (i * Decimal(str(diff_days)) / Decimal("30")).quantize(RATE_PRECISION, rounding=ROUND_HALF_UP)

    # Cálculo da prestação uniforme padrão: PMT = P * [i / (1 - (1+i)^-n)]
    if n > 0:
        # (1+i)^-n = 1 / (1+i)^n
        one_plus_i = Decimal("1.0") + i
        pow_val = one_plus_i ** n
        factor = Decimal("1.0") / pow_val
        pmt_regular = (P * (i / (Decimal("1.0") - factor))).quantize(CENTS, rounding=ROUND_HALF_UP)
    else:
        pmt_regular = P

    schedule: List[InstallmentScheduleItem] = []
    current_balance = P
    total_interest = Decimal("0.00")

    current_due = first_due_date or (date.today() + timedelta(days=30))

    for k in range(1, n + 1):
        rate_k = effective_first_rate if (k == 1 and is_irregular) else i
        interest_k = (current_balance * rate_k).quantize(CENTS, rounding=ROUND_HALF_UP)

        if k == n:
            # Última parcela: amortização absorve exatamente o saldo devedor restante
            amort_k = current_balance
            payment_k = to_cents(amort_k + interest_k)
            is_adjusted = (payment_k != pmt_regular)
            closing = Decimal("0.00")
        else:
            payment_k = pmt_regular
            amort_k = to_cents(payment_k - interest_k)
            if amort_k < Decimal("0.00"):
                amort_k = Decimal("0.00")
            closing = to_cents(current_balance - amort_k)
            is_adjusted = False

        total_interest = to_cents(total_interest + interest_k)

        schedule.append(InstallmentScheduleItem(
            installment_number=k,
            due_date=current_due.isoformat(),
            opening_balance=current_balance,
            monthly_payment=payment_k,
            interest_portion=interest_k,
            amortization_portion=amort_k,
            closing_balance=closing,
            is_cents_adjusted=is_adjusted
        ))

        current_balance = closing
        current_due = current_due + timedelta(days=30)

    last_payment = schedule[-1].monthly_payment if schedule else pmt_regular

    return LoanSimulateResponse(
        principal=P,
        monthly_rate=i,
        term_months=n,
        uniform_payment=pmt_regular,
        last_payment=last_payment,
        total_interest=total_interest,
        total_payable=to_cents(P + total_interest),
        is_irregular_first_period=is_irregular,
        first_period_days=first_period_days,
        effective_first_rate=effective_first_rate,
        schedule=schedule
    )


@router.post("/simulate", response_model=LoanSimulateResponse)
def simulate_loan_price(
    tenant_id: str,
    payload: LoanSimulateRequest,
    session: AuthenticatedSession = Depends(get_current_session)
):
    """
    Simulação determinística oficial da Tabela Price (Cláusula 4.2 e 8.2):
    - Executa cálculo puramente matemático sem necessidade de escrita em banco.
    - Aberto a Membros e Administradores autenticados.
    """
    require_tenant_access(tenant_id, session)

    if session.role == "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Master não simula nem gerencia empréstimos de caixinhas."
        )

    return compute_price_schedule(
        principal=payload.principal,
        term_months=payload.term_months,
        monthly_rate=payload.monthly_rate,
        disbursement_date=payload.disbursement_date,
        first_due_date=payload.first_due_date
    )


@router.get("", response_model=List[LoanResponse])
async def list_tenant_loans(
    tenant_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Lista de empréstimos da caixinha:
    - Master: RECUSADO com 403 (Cláusula 2.8)
    - Admin: Vê todos os empréstimos do seu tenant
    - Membro: Vê apenas seus próprios empréstimos
    Usa u.full_name em estrita conformidade com o schema 001.
    """
    require_tenant_access(tenant_id, session)

    if session.role == "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Master não possui acesso a empréstimos de caixinhas."
        )

    query = """
        SELECT l.id, l.tenant_id, l.cycle_id, l.borrower_membership_id, u.full_name as borrower_name,
               l.is_admin_loan, l.principal, l.monthly_rate, l.term_months,
               l.monthly_payment, l.last_payment, l.total_interest, l.status,
               l.created_at, l.disbursed_at
        FROM loans l
        JOIN memberships m ON l.borrower_membership_id = m.id
        JOIN users u ON m.user_id = u.id
        WHERE l.tenant_id = $1
    """
    params = [uuid.UUID(tenant_id)]

    if session.role == "TENANT_MEMBER":
        query += " AND m.user_id = $2"
        params.append(uuid.UUID(session.user_id))

    query += " ORDER BY l.created_at DESC;"

    rows = await conn.fetch(query, *params)
    results = []

    for r in rows:
        loan_id = r["id"]
        inst_rows = await conn.fetch("""
            SELECT id, installment_number, due_date, principal_due, interest_due, total_due,
                   paid_principal, paid_interest, paid_mora, paid_fine, status
            FROM loan_installments
            WHERE loan_id = $1 AND tenant_id = $2
            ORDER BY installment_number ASC;
        """, loan_id, uuid.UUID(tenant_id))

        today = date.today()
        installments = []
        for ir in inst_rows:
            due_d = ir["due_date"]
            days_over = max(0, (today - due_d).days) if ir["status"] != "QUITADA" and today > due_d else 0
            
            calc_fine = Decimal("10.00") if days_over > 0 else Decimal("0.00")
            unpaid_p = Decimal(str(ir["principal_due"])) - Decimal(str(ir["paid_principal"]))
            mora_factor = (Decimal("0.20") / Decimal("30")) * Decimal(str(days_over))
            calc_mora = (unpaid_p * mora_factor).quantize(CENTS, rounding=ROUND_HALF_UP) if days_over > 0 else Decimal("0.00")
            total_up = to_cents(Decimal(str(ir["total_due"])) - Decimal(str(ir["paid_principal"])) - Decimal(str(ir["paid_interest"])) + calc_fine + calc_mora)

            installments.append(LoanInstallmentResponse(
                id=str(ir["id"]),
                installment_number=ir["installment_number"],
                due_date=ir["due_date"],
                principal_due=to_cents(ir["principal_due"]),
                interest_due=to_cents(ir["interest_due"]),
                total_due=to_cents(ir["total_due"]),
                paid_principal=to_cents(ir["paid_principal"]),
                paid_interest=to_cents(ir["paid_interest"]),
                paid_mora=to_cents(ir["paid_mora"]),
                paid_fine=to_cents(ir["paid_fine"]),
                status=ir["status"],
                days_overdue=days_over,
                calculated_mora=calc_mora,
                calculated_fine=calc_fine,
                total_due_updated=total_up
            ))

        results.append(LoanResponse(
            id=str(r["id"]),
            tenant_id=str(r["tenant_id"]),
            cycle_id=str(r["cycle_id"]),
            borrower_membership_id=str(r["borrower_membership_id"]),
            borrower_name=r["borrower_name"],
            is_admin_loan=r["is_admin_loan"],
            principal=to_cents(r["principal"]),
            monthly_rate=Decimal(str(r["monthly_rate"])),
            term_months=r["term_months"],
            monthly_payment=to_cents(r["monthly_payment"]),
            last_payment=to_cents(r["last_payment"]),
            total_interest=to_cents(r["total_interest"]),
            status=r["status"],
            created_at=r["created_at"],
            disbursed_at=r["disbursed_at"],
            installments=installments
        ))

    return results


@router.post("/request", response_model=LoanResponse)
async def request_loan(
    tenant_id: str,
    payload: LoanRequestPayload,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Solicita um novo empréstimo sob Tabela Price:
    - Validação de prazo máximo (6 meses);
    - Detecção automática de autoempréstimo de administrador (Cláusula 5.4 e 8.8);
    - Persistência com status 'SOLICITADO'.
    """
    require_tenant_access(tenant_id, session)

    if session.role == "MASTER":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso Proibido: Master não solicita empréstimos em caixinhas."
        )

    mem_row = await conn.fetchrow("""
        SELECT id, role, status FROM memberships
        WHERE tenant_id = $1 AND user_id = $2 AND status = 'ATIVA';
    """, uuid.UUID(tenant_id), uuid.UUID(session.user_id))

    if not mem_row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas membros ativos da caixinha podem solicitar empréstimo."
        )

    is_admin_loan = (mem_row["role"] == "TENANT_ADMIN") or payload.is_admin_loan

    cycle_row = await conn.fetchrow("""
        SELECT id FROM cycles WHERE tenant_id = $1 AND status = 'ABERTO' LIMIT 1;
    """, uuid.UUID(tenant_id))
    if not cycle_row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhum ciclo anual aberto encontrado.")

    policy_row = await conn.fetchrow("""
        SELECT id, monthly_interest_rate, max_installments FROM policies
        WHERE tenant_id = $1 AND cycle_id = $2 AND status = 'ACTIVE' LIMIT 1;
    """, uuid.UUID(tenant_id), cycle_row["id"])
    if not policy_row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Política financeira não configurada.")

    rate = Decimal(str(policy_row["monthly_interest_rate"]))

    # Cálculo da simulação Price com Decimal
    sim = compute_price_schedule(payload.principal, payload.term_months, rate)

    loan_id = uuid.uuid4()
    await conn.execute("""
        INSERT INTO loans (
            id, tenant_id, cycle_id, borrower_membership_id, policy_id, is_admin_loan,
            principal, monthly_rate, term_months, monthly_payment, last_payment,
            total_interest, status, created_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 'SOLICITADO', NOW());
    """, loan_id, uuid.UUID(tenant_id), cycle_row["id"], mem_row["id"], policy_row["id"],
       is_admin_loan, sim.principal, sim.monthly_rate, sim.term_months,
       sim.uniform_payment, sim.last_payment, sim.total_interest)

    await conn.execute("""
        INSERT INTO audit_events (id, actor_id, actor_role, tenant_id, action, object_type, object_id, reason, evidence_ref)
        VALUES ($1, $2, $3, $4, 'SOLICITACAO_EMPRESTIMO', 'LOAN', $5, $6, $7);
    """, uuid.uuid4(), uuid.UUID(session.user_id), session.role, uuid.UUID(tenant_id),
       str(loan_id), f"Solicitação de empréstimo R$ {sim.principal} em {sim.term_months}x", f"SIM-PMT-{sim.uniform_payment}")

    return await list_tenant_loans(tenant_id, session, conn)


@router.post("/{loan_id}/approve", response_model=LoanResponse)
async def approve_loan(
    tenant_id: str,
    loan_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Aprova empréstimo e gera cronograma de parcelas (Cláusula 5.4 e 8.8):
    - Apenas Administrador pode aprovar;
    - Se for autoempréstimo de Administrador, exige 100% de consentimento dos demais membros;
    - Gera registros em 'loan_installments'.
    """
    require_tenant_access(tenant_id, session)

    if session.role != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores de caixinha podem aprovar empréstimos."
        )

    loan = await conn.fetchrow("""
        SELECT * FROM loans WHERE id = $1 AND tenant_id = $2 FOR UPDATE;
    """, uuid.UUID(loan_id), uuid.UUID(tenant_id))

    if not loan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empréstimo não encontrado.")

    if loan["status"] != "SOLICITADO":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Empréstimo com status '{loan['status']}' não pode ser aprovado.")

    if loan["is_admin_loan"]:
        # A contagem de votos abaixo não comprova autorização anual vigente,
        # unanimidade dos demais membros ou revalidação após revogação.
        raise HTTPException(status_code=503, detail="Autoempréstimo indisponível até validar a autorização anual dos demais membros.")

    if loan["is_admin_loan"]:
        other_members_count = await conn.fetchval("""
            SELECT COUNT(*) FROM memberships
            WHERE tenant_id = $1 AND status = 'ATIVA' AND id != $2;
        """, uuid.UUID(tenant_id), loan["borrower_membership_id"])

        consent_votes = await conn.fetchval("""
            SELECT COUNT(*) FROM admin_self_loan_consents
            WHERE tenant_id = $1 AND loan_id = $2 AND decision = 'FAVORAVEL';
        """, uuid.UUID(tenant_id), uuid.UUID(loan_id))

        if other_members_count > 0 and consent_votes < other_members_count:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Autoempréstimo de Administrador requer aprovação unânime de todos os demais membros ativos ({consent_votes}/{other_members_count} votos favoráveis)."
            )

    sim = compute_price_schedule(
        principal=Decimal(str(loan["principal"])),
        term_months=loan["term_months"],
        monthly_rate=Decimal(str(loan["monthly_rate"]))
    )

    for item in sim.schedule:
        await conn.execute("""
            INSERT INTO loan_installments (
                id, tenant_id, loan_id, installment_number, due_date,
                principal_due, interest_due, total_due, status, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'PENDENTE', NOW());
        """, uuid.uuid4(), uuid.UUID(tenant_id), uuid.UUID(loan_id), item.installment_number,
           date.fromisoformat(item.due_date), item.amortization_portion, item.interest_portion, item.monthly_payment)

    await conn.execute("""
        UPDATE loans SET status = 'APROVADO' WHERE id = $1;
    """, uuid.UUID(loan_id))

    return await list_tenant_loans(tenant_id, session, conn)


@router.post("/{loan_id}/disburse", response_model=LoanResponse)
async def disburse_loan(
    tenant_id: str,
    loan_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Efetua desembolso financeiro do empréstimo e realiza lançamento contábil de partidas dobradas atômico:
    - Débito: Crédito Interno a Receber (1.2.1)
    - Crédito: Caixa Financeiro Reconciliado (1.1.1)
    Falha imediatamente se qualquer conta contábil canônica estiver ausente.
    """
    require_tenant_access(tenant_id, session)

    raise HTTPException(status_code=503, detail="Desembolso indisponível até integração e confirmação bancária.")

    if session.role != "TENANT_ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores de caixinha podem desembolsar empréstimos."
        )

    loan = await conn.fetchrow("""
        SELECT * FROM loans WHERE id = $1 AND tenant_id = $2 FOR UPDATE;
    """, uuid.UUID(loan_id), uuid.UUID(tenant_id))

    if not loan or loan["status"] != "APROVADO":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empréstimo deve estar APROVADO para desembolso.")

    principal_dec = Decimal(str(loan["principal"]))
    amount_cents = int((principal_dec * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    tx_id = uuid.uuid4()

    # Contas Canônicas: 1.2.1 Crédito Interno a Receber e 1.1.1 Caixa Financeiro
    acc_credito = await conn.fetchrow("SELECT id FROM ledger_accounts WHERE tenant_id = $1 AND account_code = '1.2.1';", uuid.UUID(tenant_id))
    acc_caixa = await conn.fetchrow("SELECT id FROM ledger_accounts WHERE tenant_id = $1 AND account_code = '1.1.1';", uuid.UUID(tenant_id))

    if not acc_credito or not acc_caixa:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro contábil crítico: contas do livro-razão canônico (1.1.1 Caixa / 1.2.1 Crédito) não configuradas no tenant. Desembolso abortado."
        )

    # Lançamento atômico em partidas dobradas
    await conn.execute("""
        INSERT INTO ledger_transactions (id, tenant_id, transaction_date, description, reference_id)
        VALUES ($1, $2, NOW(), $3, $4);
    """, tx_id, uuid.UUID(tenant_id), f"Desembolso de empréstimo aprovado {loan_id}", str(loan_id))

    await conn.execute("""
        INSERT INTO ledger_entries (id, tenant_id, transaction_id, account_id, entry_type, amount_cents)
        VALUES ($1, $2, $3, $4, 'DR', $5);
    """, uuid.uuid4(), uuid.UUID(tenant_id), tx_id, acc_credito["id"], amount_cents)

    await conn.execute("""
        INSERT INTO ledger_entries (id, tenant_id, transaction_id, account_id, entry_type, amount_cents)
        VALUES ($1, $2, $3, $4, 'CR', $5);
    """, uuid.uuid4(), uuid.UUID(tenant_id), tx_id, acc_caixa["id"], amount_cents)

    await conn.execute("UPDATE ledger_accounts SET balance_cents = balance_cents + $1 WHERE id = $2;", amount_cents, acc_credito["id"])
    await conn.execute("UPDATE ledger_accounts SET balance_cents = balance_cents - $1 WHERE id = $2;", amount_cents, acc_caixa["id"])

    await conn.execute("""
        UPDATE loans SET status = 'DESEMBOLSADO', disbursed_at = NOW() WHERE id = $1;
    """, uuid.UUID(loan_id))

    return await list_tenant_loans(tenant_id, session, conn)


@router.post("/{loan_id}/repay", response_model=LoanRepayResponse)
async def repay_loan_installment(
    tenant_id: str,
    loan_id: str,
    payload: LoanRepayPayload,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Pagamento de empréstimo com Imputação em 4 Etapas (Cláusula 8.6 e 16.2):
    1. Juros remuneratórios vencidos;
    2. Mora simples acumulada (20%/30 ao dia sobre o principal vencido);
    3. Multa única de R$ 10,00 da parcela;
    4. Principal vencido.
    Lançamento contábil atômico: Débito em 1.1.1 (Caixa), Crédito em 1.2.1 (Crédito) e 4.1.1 (Receitas).
    """
    require_tenant_access(tenant_id, session)

    raise HTTPException(status_code=503, detail="Baixa de pagamento indisponível até conciliação bancária.")

    loan = await conn.fetchrow("""
        SELECT * FROM loans WHERE id = $1 AND tenant_id = $2 FOR UPDATE;
    """, uuid.UUID(loan_id), uuid.UUID(tenant_id))

    if not loan or loan["status"] not in ("DESEMBOLSADO", "INADIMPLENTE"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empréstimo não está ativo para recebimento.")

    inst = await conn.fetchrow("""
        SELECT * FROM loan_installments
        WHERE loan_id = $1 AND tenant_id = $2 AND status != 'QUITADA'
        ORDER BY installment_number ASC LIMIT 1
        FOR UPDATE;
    """, uuid.UUID(loan_id), uuid.UUID(tenant_id))

    if not inst:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nenhuma parcela pendente encontrada.")

    today = date.today()
    due_d = inst["due_date"]
    days_over = max(0, (today - due_d).days) if today > due_d else 0

    fine_due = Decimal("10.00") if days_over > 0 else Decimal("0.00")
    unpaid_principal = Decimal(str(inst["principal_due"])) - Decimal(str(inst["paid_principal"]))
    mora_rate = (Decimal("0.20") / Decimal("30")) * Decimal(str(days_over))
    mora_due = (unpaid_principal * mora_rate).quantize(CENTS, rounding=ROUND_HALF_UP) if days_over > 0 else Decimal("0.00")
    interest_due = Decimal(str(inst["interest_due"])) - Decimal(str(inst["paid_interest"]))

    rem = to_cents(payload.amount)

    # 1. Juros
    alloc_interest = min(rem, interest_due)
    rem = to_cents(rem - alloc_interest)

    # 2. Mora
    alloc_mora = min(rem, mora_due)
    rem = to_cents(rem - alloc_mora)

    # 3. Multa
    alloc_fine = min(rem, fine_due)
    rem = to_cents(rem - alloc_fine)

    # 4. Principal
    alloc_principal = min(rem, unpaid_principal)
    rem = to_cents(rem - alloc_principal)

    new_paid_principal = to_cents(Decimal(str(inst["paid_principal"])) + alloc_principal)
    new_paid_interest = to_cents(Decimal(str(inst["paid_interest"])) + alloc_interest)
    new_paid_mora = to_cents(Decimal(str(inst["paid_mora"])) + alloc_mora)
    new_paid_fine = to_cents(Decimal(str(inst["paid_fine"])) + alloc_fine)

    is_settled = (new_paid_principal >= Decimal(str(inst["principal_due"]))) and (new_paid_interest >= Decimal(str(inst["interest_due"])))
    new_status = "QUITADA" if is_settled else "PARCIAL"

    await conn.execute("""
        UPDATE loan_installments
        SET paid_principal = $1, paid_interest = $2, paid_mora = $3, paid_fine = $4,
            status = $5, paid_at = CASE WHEN $5 = 'QUITADA' THEN NOW() ELSE paid_at END
        WHERE id = $6;
    """, new_paid_principal, new_paid_interest, new_paid_mora, new_paid_fine, new_status, inst["id"])

    await conn.execute("""
        INSERT INTO loan_payments (
            id, tenant_id, loan_id, installment_id, amount_paid,
            allocated_interest, allocated_mora, allocated_fine, allocated_principal,
            payment_type, payment_date
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'PARCIAL', NOW());
    """, uuid.uuid4(), uuid.UUID(tenant_id), uuid.UUID(loan_id), inst["id"],
       to_cents(payload.amount), alloc_interest, alloc_mora, alloc_fine, alloc_principal)

    # Contabilidade: Contas Canônicas 1.1.1 (Caixa), 1.2.1 (Crédito) e 4.1.1 (Receitas)
    acc_caixa = await conn.fetchrow("SELECT id FROM ledger_accounts WHERE tenant_id = $1 AND account_code = '1.1.1';", uuid.UUID(tenant_id))
    acc_credito = await conn.fetchrow("SELECT id FROM ledger_accounts WHERE tenant_id = $1 AND account_code = '1.2.1';", uuid.UUID(tenant_id))
    acc_receita = await conn.fetchrow("SELECT id FROM ledger_accounts WHERE tenant_id = $1 AND account_code = '4.1.1';", uuid.UUID(tenant_id))

    if not acc_caixa or not acc_credito or not acc_receita:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro contábil crítico: contas do livro-razão canônico (1.1.1, 1.2.1, 4.1.1) não configuradas. Operação abortada."
        )

    tx_id = uuid.uuid4()
    tot_cents = int((to_cents(payload.amount) * Decimal("100")).quantize(Decimal("1")))
    princ_cents = int((alloc_principal * Decimal("100")).quantize(Decimal("1")))
    rec_cents = int(((alloc_interest + alloc_mora + alloc_fine) * Decimal("100")).quantize(Decimal("1")))

    # Validação de partidas dobradas
    if tot_cents != (princ_cents + rec_cents):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inconsistência contábil: Débito R$ {tot_cents/100:.2f} diverge dos créditos R$ {(princ_cents+rec_cents)/100:.2f}"
        )

    await conn.execute("""
        INSERT INTO ledger_transactions (id, tenant_id, transaction_date, description, reference_id)
        VALUES ($1, $2, NOW(), $3, $4);
    """, tx_id, uuid.UUID(tenant_id), f"Amortização parcela empréstimo {loan_id}", str(loan_id))

    await conn.execute("INSERT INTO ledger_entries (id, tenant_id, transaction_id, account_id, entry_type, amount_cents) VALUES ($1, $2, $3, $4, 'DR', $5);", uuid.uuid4(), uuid.UUID(tenant_id), tx_id, acc_caixa["id"], tot_cents)
    if princ_cents > 0:
        await conn.execute("INSERT INTO ledger_entries (id, tenant_id, transaction_id, account_id, entry_type, amount_cents) VALUES ($1, $2, $3, $4, 'CR', $5);", uuid.uuid4(), uuid.UUID(tenant_id), tx_id, acc_credito["id"], princ_cents)
        await conn.execute("UPDATE ledger_accounts SET balance_cents = balance_cents - $1 WHERE id = $2;", princ_cents, acc_credito["id"])
    if rec_cents > 0:
        await conn.execute("INSERT INTO ledger_entries (id, tenant_id, transaction_id, account_id, entry_type, amount_cents) VALUES ($1, $2, $3, $4, 'CR', $5);", uuid.uuid4(), uuid.UUID(tenant_id), tx_id, acc_receita["id"], rec_cents)
        await conn.execute("UPDATE ledger_accounts SET balance_cents = balance_cents + $1 WHERE id = $2;", rec_cents, acc_receita["id"])

    await conn.execute("UPDATE ledger_accounts SET balance_cents = balance_cents + $1 WHERE id = $2;", tot_cents, acc_caixa["id"])

    unsettled_count = await conn.fetchval("SELECT COUNT(*) FROM loan_installments WHERE loan_id = $1 AND status != 'QUITADA';", uuid.UUID(loan_id))
    if unsettled_count == 0:
        await conn.execute("UPDATE loans SET status = 'QUITADO' WHERE id = $1;", uuid.UUID(loan_id))

    return LoanRepayResponse(
        loan_id=loan_id,
        amount_received=to_cents(payload.amount),
        allocated_interest=alloc_interest,
        allocated_mora=alloc_mora,
        allocated_fine=alloc_fine,
        allocated_principal=alloc_principal,
        remaining_balance=to_cents(unpaid_principal - alloc_principal),
        is_fully_settled=(unsettled_count == 0)
    )


@router.post("/{loan_id}/early-settlement", response_model=LoanEarlySettlementResponse)
async def settle_loan_early(
    tenant_id: str,
    loan_id: str,
    session: AuthenticatedSession = Depends(get_current_session),
    conn = Depends(get_rls_db_connection)
):
    """
    Quitação antecipada integral com 100% de desconto nos juros vincendos (Cláusula 8.6).
    """
    require_tenant_access(tenant_id, session)

    raise HTTPException(status_code=503, detail="Quitação indisponível até conciliação bancária.")

    loan = await conn.fetchrow("""
        SELECT * FROM loans WHERE id = $1 AND tenant_id = $2 FOR UPDATE;
    """, uuid.UUID(loan_id), uuid.UUID(tenant_id))

    if not loan or loan["status"] in ("QUITADO", "SOLICITADO"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empréstimo não está ativo para liquidação antecipada.")

    insts = await conn.fetch("""
        SELECT * FROM loan_installments
        WHERE loan_id = $1 AND tenant_id = $2 AND status != 'QUITADA'
        ORDER BY installment_number ASC;
    """, uuid.UUID(loan_id), uuid.UUID(tenant_id))

    today = date.today()
    open_principal = Decimal("0.00")
    overdue_interest = Decimal("0.00")
    overdue_mora = Decimal("0.00")
    overdue_fine = Decimal("0.00")
    future_interest_waived = Decimal("0.00")

    for i in insts:
        unpaid_p = Decimal(str(i["principal_due"])) - Decimal(str(i["paid_principal"]))
        open_principal += unpaid_p
        due_d = i["due_date"]

        if due_d < today:
            days_over = (today - due_d).days
            overdue_interest += (Decimal(str(i["interest_due"])) - Decimal(str(i["paid_interest"])))
            overdue_fine += Decimal("10.00")
            overdue_mora += (unpaid_p * (Decimal("0.20") / Decimal("30")) * Decimal(str(days_over))).quantize(CENTS, rounding=ROUND_HALF_UP)
        else:
            future_interest_waived += Decimal(str(i["interest_due"]))

    total_settlement = to_cents(open_principal + overdue_interest + overdue_mora + overdue_fine)

    await conn.execute("""
        UPDATE loan_installments
        SET status = 'QUITADA', paid_principal = principal_due, paid_at = NOW()
        WHERE loan_id = $1;
    """, uuid.UUID(loan_id))

    await conn.execute("UPDATE loans SET status = 'QUITADO' WHERE id = $1;", uuid.UUID(loan_id))

    # Lançamento contábil atômico
    acc_caixa = await conn.fetchrow("SELECT id FROM ledger_accounts WHERE tenant_id = $1 AND account_code = '1.1.1';", uuid.UUID(tenant_id))
    acc_credito = await conn.fetchrow("SELECT id FROM ledger_accounts WHERE tenant_id = $1 AND account_code = '1.2.1';", uuid.UUID(tenant_id))
    acc_receita = await conn.fetchrow("SELECT id FROM ledger_accounts WHERE tenant_id = $1 AND account_code = '4.1.1';", uuid.UUID(tenant_id))

    if not acc_caixa or not acc_credito or not acc_receita:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro contábil crítico: contas do razão canônico (1.1.1, 1.2.1, 4.1.1) não configuradas. Quitação abortada."
        )

    tx_id = uuid.uuid4()
    tot_cents = int((total_settlement * Decimal("100")).quantize(Decimal("1")))
    princ_cents = int((open_principal * Decimal("100")).quantize(Decimal("1")))
    rec_cents = int(((overdue_interest + overdue_mora + overdue_fine) * Decimal("100")).quantize(Decimal("1")))

    if tot_cents != (princ_cents + rec_cents):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inconsistência contábil de partidas dobradas na quitação antecipada."
        )

    await conn.execute("""
        INSERT INTO ledger_transactions (id, tenant_id, transaction_date, description, reference_id)
        VALUES ($1, $2, NOW(), $3, $4);
    """, tx_id, uuid.UUID(tenant_id), f"Quitação antecipada total empréstimo {loan_id}", str(loan_id))

    await conn.execute("INSERT INTO ledger_entries VALUES ($1, $2, $3, $4, 'DR', $5);", uuid.uuid4(), uuid.UUID(tenant_id), tx_id, acc_caixa["id"], tot_cents)
    if princ_cents > 0:
        await conn.execute("INSERT INTO ledger_entries VALUES ($1, $2, $3, $4, 'CR', $5);", uuid.uuid4(), uuid.UUID(tenant_id), tx_id, acc_credito["id"], princ_cents)
        await conn.execute("UPDATE ledger_accounts SET balance_cents = balance_cents - $1 WHERE id = $2;", princ_cents, acc_credito["id"])
    if rec_cents > 0:
        await conn.execute("INSERT INTO ledger_entries VALUES ($1, $2, $3, $4, 'CR', $5);", uuid.uuid4(), uuid.UUID(tenant_id), tx_id, acc_receita["id"], rec_cents)
        await conn.execute("UPDATE ledger_accounts SET balance_cents = balance_cents + $1 WHERE id = $2;", rec_cents, acc_receita["id"])

    await conn.execute("UPDATE ledger_accounts SET balance_cents = balance_cents + $1 WHERE id = $2;", tot_cents, acc_caixa["id"])

    return LoanEarlySettlementResponse(
        loan_id=loan_id,
        open_principal=open_principal,
        overdue_interest=overdue_interest,
        overdue_mora=overdue_mora,
        overdue_fine=overdue_fine,
        total_overdue_charges=to_cents(overdue_interest + overdue_mora + overdue_fine),
        unaccrued_future_interest_waived=to_cents(future_interest_waived),
        total_settlement_amount=total_settlement,
        is_fully_settled=True,
        message="Quitação antecipada efetivada com 100% de desconto sobre juros vincendos."
    )
