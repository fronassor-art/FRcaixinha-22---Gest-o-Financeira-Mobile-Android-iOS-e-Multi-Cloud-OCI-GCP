"""Laboratório financeiro integrado: PostgreSQL real DESCARTÁVEL, pessoas fictícias.

Proibido no Termux operacional (5433), Oracle, produção e bancos persistentes.
Só roda no GitHub Actions frcaixinha_ci, PostgreSQL 5432, usuários sintéticos.
Os lançamentos 'quitados' são CENÁRIOS HIPOTÉTICOS, nunca confirmação Pix.
"""
import os
import uuid
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from urllib.parse import urlparse

import asyncpg
import pytest
from fastapi import HTTPException

from app.dependencies import AuthenticatedSession
from app.models import LoanSimulateRequest
from app.routers.contributions import (
    list_tenant_quotas, list_tenant_contributions,
    get_member_annual_preview, get_admin_annual_preview,
)
from app.routers.ledger import (
    get_ledger_integrity_preview, list_ledger_account_entries_keyset,
)
from app.routers.loans import (
    compute_price_schedule, simulate_loan_price, list_tenant_loans,
)

pytestmark = pytest.mark.skipif(
    os.getenv("FRCAIXINHA_CI_ISOLATED") != "1" or os.getenv("GITHUB_ACTIONS") != "true",
    reason="Somente no PostgreSQL descartável do GitHub Actions",
)


def ci_dsn(key, owner=False):
    parsed = urlparse(os.environ[key])
    if (parsed.scheme not in ("postgresql", "postgres")
            or parsed.hostname not in ("localhost", "127.0.0.1")
            or parsed.port != 5432
            or parsed.path != "/frcaixinha_ci"
            or (owner and parsed.username != "postgres")
            or (not owner and parsed.username == "postgres")):
        raise RuntimeError("BLOQUEADO: banco não é o laboratório PostgreSQL 5432")
    return os.environ[key]


@pytest.mark.asyncio
async def test_integrated_real_sql_with_fictional_people_and_exact_money():
    """2 admins; 2 caixas; 8 usuários, 10 vínculos, 8 cotas,
    96 contribuições, 2 propostas de crédito, 26 lançamentos balanceados.
    """
    # A verificação dos dois DSNs ocorre antes de QUALQUER conexão.
    admin_dsn = ci_dsn("CI_ADMIN_DATABASE_URL", owner=True)
    app_dsn = ci_dsn("DATABASE_URL")
    ids = {name: uuid.uuid4() for name in (
        "master", "admin_a", "admin_b", "member_a", "member_a2",
        "member_b", "member_b2", "shared", "tenant_a", "tenant_b",
        "cycle_a", "cycle_b", "policy_a", "policy_b", "loan_a", "loan_b",
    )}
    memberships = {name: uuid.uuid4() for name in (
        "admin_a_admin", "admin_a_member", "member_a", "member_a2", "shared_a",
        "admin_b_admin", "admin_b_member", "member_b", "member_b2", "shared_b",
    )}
    a, b = ids["tenant_a"], ids["tenant_b"]
    people = ("master","admin_a","admin_b","member_a","member_a2",
              "member_b","member_b2","shared")
    groups = {
        "a": ("admin_a_member","member_a","member_a2","shared_a"),
        "b": ("admin_b_member","member_b","member_b2","shared_b"),
    }
    tenant_specs = {
        "a": (a, ids["cycle_a"], ids["policy_a"], Decimal("150.00"), Decimal("0.2000")),
        "b": (b, ids["cycle_b"], ids["policy_b"], Decimal("175.00"), Decimal("0.1500")),
    }
    memberships_info = [
        ("admin_a_admin","a","admin_a","TENANT_ADMIN"),
        ("admin_a_member","a","admin_a","TENANT_MEMBER"),
        ("member_a","a","member_a","TENANT_MEMBER"),
        ("member_a2","a","member_a2","TENANT_MEMBER"),
        ("shared_a","a","shared","TENANT_MEMBER"),
        ("admin_b_admin","b","admin_b","TENANT_ADMIN"),
        ("admin_b_member","b","admin_b","TENANT_MEMBER"),
        ("member_b","b","member_b","TENANT_MEMBER"),
        ("member_b2","b","member_b2","TENANT_MEMBER"),
        ("shared_b","b","shared","TENANT_MEMBER"),
    ]
    admin = await asyncpg.connect(admin_dsn)
    app = None
    initialized = False
    try:
        app = await asyncpg.connect(app_dsn)
        role = await app.fetchrow(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        assert role and not role["rolsuper"] and not role["rolbypassrls"]
        # Esse SELECT deve acontecer contra um banco efêmero recém-migrado.
        assert await admin.fetchval("SELECT current_database()") == "frcaixinha_ci"
        async with admin.transaction():
            for name in people:
                await admin.execute(
                    "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master) "
                    "VALUES($1,$2,$3,$4,'00000000000',$5)",
                    ids[name], f"{ids[name]}@example.invalid",
                    "PESSOA FICTICIA CI "+name, ids[name].hex[:14], name=="master",
                )
            for side, admin_name in (("a","admin_a"),("b","admin_b")):
                tenant = tenant_specs[side][0]
                await admin.execute(
                    "INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id) "
                    "VALUES($1,$2,$3,$4)",
                    tenant, "CAIXINHA FICTICIA CI "+side, str(uuid.uuid4()), ids[admin_name],
                )
            for link, side, user, role_name in memberships_info:
                await admin.execute(
                    "INSERT INTO public.memberships(id,tenant_id,user_id,role) "
                    "VALUES($1,$2,$3,$4)",
                    memberships[link], tenant_specs[side][0], ids[user], role_name,
                )
            for side, (tenant, cycle, policy, quota_value, interest_rate) in tenant_specs.items():
                await admin.execute(
                    "INSERT INTO public.cycles(id,tenant_id,year,start_date,end_date,settlement_date) "
                    "VALUES($1,$2,2027,$3,$4,$5)",
                    cycle, tenant, date(2027,1,1),date(2027,12,31),date(2028,1,10),
                )
                await admin.execute(
                    "INSERT INTO public.policies(id,tenant_id,cycle_id,monthly_interest_rate,"
                    "max_installments,contribution_per_quota,admin_pct,member_pct) "
                    "VALUES($1,$2,$3,$4,6,$5,15,85)",
                    policy, tenant, cycle, interest_rate, quota_value,
                )
                for number, link in enumerate(groups[side], start=1):
                    await admin.execute(
                        "INSERT INTO public.quotas(tenant_id,membership_id,quota_number,value_brl) "
                        "VALUES($1,$2,$3,$4)",
                        tenant, memberships[link], number, quota_value,
                    )
            # 12 competências x 4 vínculos de membro por caixinha; 100% sintético.
            receipts = []
            for side, (tenant, cycle, _, quota_value, _) in tenant_specs.items():
                sequence = 0
                for link in groups[side]:
                    for month in range(1,13):
                        sequence += 1
                        value = (quota_value if side=="a" and sequence<=25 else
                                 quota_value / 2 if side=="a" and sequence==26 else
                                 Decimal("0.00"))
                        status = ("QUITADA" if value==quota_value else
                                  "PARCIAL" if value>0 else "PENDENTE")
                        contribution_id = uuid.uuid4()
                        await admin.execute(
                            "INSERT INTO public.contributions "
                            "(id,tenant_id,cycle_id,membership_id,competence,due_date,"
                            "amount_due,amount_paid,payment_status,due_status,paid_at) "
                            "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)",
                            contribution_id, tenant, cycle, memberships[link], f"2027-{month:02d}",
                            date(2027,month,10),quota_value,value,status,
                            "REGULARIZADA" if status=="QUITADA" else "NO_PRAZO",
                            datetime(2027,month,10,12,tzinfo=timezone.utc) if value>0 else None,
                        )
                        if value>0:
                            receipts.append((tenant, contribution_id, value))
            assert len(receipts)==26 and all(t==a for t,_,_ in receipts)
            cash = await admin.fetchval(
                "SELECT id FROM public.ledger_accounts "
                "WHERE tenant_id=$1 AND account_code='1.1.1'",a)
            equity = await admin.fetchval(
                "SELECT id FROM public.ledger_accounts "
                "WHERE tenant_id=$1 AND account_code='2.1.1'",a)
            assert cash and equity
            for index, (tenant, contribution_id, value) in enumerate(receipts):
                tx = uuid.uuid4()
                cents = int(value * 100)
                await admin.execute(
                    "INSERT INTO public.ledger_transactions(id,tenant_id,transaction_date,"
                    "description,reference_id) VALUES($1,$2,$3,$4,$5)",
                    tx,tenant,datetime(2027,2,1,tzinfo=timezone.utc)
                    +timedelta(seconds=index),
                    "CI PAGAMENTO FICTICIO SEM BANCO",str(contribution_id),
                )
                for account, kind in ((cash,"DR"),(equity,"CR")):
                    await admin.execute(
                        "INSERT INTO public.ledger_entries "
                        "(tenant_id,transaction_id,account_id,entry_type,amount_cents) "
                        "VALUES($1,$2,$3,$4,$5)",tenant,tx,account,kind,cents,
                    )
            # Propostas e cronogramas fictícios: nenhuma liberação real.
            for side, loan_id, borrower, months, expected in (
                ("a",ids["loan_a"],memberships["member_a"],5,Decimal("835.96")),
                ("b",ids["loan_b"],memberships["member_b"],3,Decimal("656.96")),
            ):
                tenant, cycle, policy, _, rate = tenant_specs[side]
                schedule = compute_price_schedule(
                    Decimal("500.00"),months,rate,
                    cycle_start_date=date(2027,1,1),cycle_end_date=date(2027,12,31),
                )
                assert schedule.total_payable==expected
                assert schedule.schedule[-1].closing_balance==Decimal("0.00")
                await admin.execute(
                    "INSERT INTO public.loans(id,tenant_id,cycle_id,borrower_membership_id,"
                    "policy_id,principal,monthly_rate,term_months,monthly_payment,"
                    "last_payment,total_interest,status) "
                    "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,'SOLICITADO')",
                    loan_id,tenant,cycle,borrower,policy,Decimal("500.00"),rate,months,
                    schedule.uniform_payment,schedule.last_payment,schedule.total_interest,
                )
                for item in schedule.schedule:
                    await admin.execute(
                        "INSERT INTO public.loan_installments(tenant_id,loan_id,"
                        "installment_number,due_date,principal_due,interest_due,total_due) "
                        "VALUES($1,$2,$3,$4,$5,$6,$7)",
                        tenant,loan_id,item.installment_number,
                        date.fromisoformat(item.due_date),item.amortization_portion,
                        item.interest_portion,item.monthly_payment,
                    )
        initialized = True
        # Oráculo independente em centavos; não usar somente valores da API.
        assert await admin.fetchval(
            "SELECT count(*) FROM public.contributions WHERE tenant_id=ANY($1::uuid[])",
            [a,b])==96
        for side, total_due, total_paid in (
            ("a",Decimal("7200.00"),Decimal("3825.00")),
            ("b",Decimal("8400.00"),Decimal("0.00")),
        ):
            tenant = tenant_specs[side][0]
            summary = await admin.fetchrow(
                "SELECT count(*) AS n,sum(amount_due) AS due,sum(amount_paid) AS paid,"
                "count(*) FILTER (WHERE payment_status='QUITADA') AS complete,"
                "count(*) FILTER (WHERE payment_status='PARCIAL') AS partial "
                "FROM public.contributions WHERE tenant_id=$1",tenant)
            assert (summary["n"],summary["due"],summary["paid"]) == (48,total_due,total_paid)
            assert (summary["complete"],summary["partial"]) == ((25,1) if side=="a" else (0,0))
            memberships_summary = await admin.fetchrow(
                "SELECT count(*) AS links,count(DISTINCT user_id) AS persons,"
                "count(*) FILTER (WHERE role='TENANT_MEMBER') AS members "
                "FROM public.memberships WHERE tenant_id=$1",tenant)
            assert (memberships_summary["links"],memberships_summary["persons"],
                    memberships_summary["members"])==(5,4,4)
        totals = await admin.fetchrow(
            "SELECT count(DISTINCT t.id) AS transactions,"
            "sum(e.amount_cents) FILTER (WHERE e.entry_type='DR') AS debit,"
            "sum(e.amount_cents) FILTER (WHERE e.entry_type='CR') AS credit "
            "FROM public.ledger_transactions t JOIN public.ledger_entries e "
            "ON e.transaction_id=t.id AND e.tenant_id=t.tenant_id "
            "WHERE t.tenant_id=$1",a)
        assert (totals["transactions"],totals["debit"],totals["credit"])==(
            26,382500,382500)
        # Cada lançamento fictício se conecta a UMA contribuição específica;
        # nenhum lançamento sem origem, nenhum centavo divergente.
        links=await admin.fetch("""
            SELECT c.id,c.amount_paid, t.id AS transaction_id,
              sum(e.amount_cents) FILTER (WHERE e.entry_type='DR') AS debit_cents,
              sum(e.amount_cents) FILTER (WHERE e.entry_type='CR') AS credit_cents
            FROM public.contributions c
            JOIN public.ledger_transactions t
              ON t.tenant_id=c.tenant_id AND t.reference_id=c.id::text
            JOIN public.ledger_entries e
              ON e.tenant_id=t.tenant_id AND e.transaction_id=t.id
            WHERE c.tenant_id=$1 AND c.amount_paid>0
            GROUP BY c.id,c.amount_paid,t.id
        """,a)
        assert len(links)==26
        assert sum(x["amount_paid"] for x in links)==Decimal("3825.00")
        assert all(x["debit_cents"]==x["credit_cents"]==int(x["amount_paid"]*100)
                   for x in links)
        assert await admin.fetchval("""
            SELECT count(*) FROM public.ledger_transactions t
            LEFT JOIN public.contributions c
              ON c.tenant_id=t.tenant_id AND c.id::text=t.reference_id
            WHERE t.tenant_id=$1 AND c.id IS NULL
        """,a)==0
        assert await admin.fetchval(
            "SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=$1",b)==0

        async def as_actor(name,side,role,fn):
            tenant=tenant_specs[side][0] if side else None
            s=AuthenticatedSession(str(ids[name]),role,
                str(tenant) if tenant else None,
                "fictional@example.invalid","PESSOA FICTICIA",role=="MASTER")
            async with app.transaction():
                await app.execute("SELECT set_config('app.current_user_id',$1,true)",str(ids[name]))
                await app.execute("SELECT set_config('app.current_role',$1,true)",role)
                await app.execute("SELECT set_config('app.current_tenant_id',$1,true)",
                                  str(tenant) if tenant else "")
                return await fn(s,app)
        # Contribuições e cotas consultadas pela aplicação usando RLS real.
        quotas_a,contrib_a=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c: read_quota_contrib(a,s,c))
        assert len(quotas_a)==4 and len(contrib_a)==48
        assert sum(x.amount_paid for x in contrib_a)==Decimal("3825.00")
        quotas_b,contrib_b=await as_actor("admin_b","b","TENANT_ADMIN",
            lambda s,c: read_quota_contrib(b,s,c))
        assert len(quotas_b)==4 and len(contrib_b)==48
        assert sum(x.amount_paid for x in contrib_b)==Decimal("0.00")
        for side,name,amount in (
            ("a","admin_a",Decimal("1800.00")),
            ("a","member_a",Decimal("1800.00")),
            ("a","member_a2",Decimal("225.00")),
            ("a","shared",Decimal("0.00")),
            ("b","admin_b",Decimal("0.00")),
            ("b","member_b",Decimal("0.00")),
            ("b","member_b2",Decimal("0.00")),
            ("b","shared",Decimal("0.00")),
        ):
            tenant=tenant_specs[side][0]
            quotas,contrib=await as_actor(name,side,"TENANT_MEMBER",
                lambda s,c: read_quota_contrib(tenant,s,c))
            assert len(quotas)==1 and len(contrib)==12
            assert sum(x.amount_paid for x in contrib)==amount
        annual_a=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c:get_admin_annual_preview(str(a),2027,s,c))
        assert (annual_a.contribution_count,annual_a.pending_count,
                annual_a.total_due,annual_a.amount_paid_recorded,
                annual_a.remaining_due)==(48,23,Decimal("7200.00"),
                    Decimal("3825.00"),Decimal("3375.00"))
        assert annual_a.profit_amount is None
        annual_member=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda s,c:get_member_annual_preview(str(a),2027,s,c))
        assert (annual_member.contribution_count,annual_member.pending_count,
                annual_member.total_due,annual_member.amount_paid_recorded)==(
                    12,11,Decimal("1800.00"),Decimal("225.00"))
        preview_a=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c:get_ledger_integrity_preview(str(a),s,c))
        preview_b=await as_actor("admin_b","b","TENANT_ADMIN",
            lambda s,c:get_ledger_integrity_preview(str(b),s,c))
        assert (preview_a.status,preview_a.checked_transactions,
                preview_a.balanced_transactions)==("BALANCED",26,26)
        assert not preview_a.bank_reconciled and not preview_a.financial_closing_authorized
        assert preview_b.status=="NO_TRANSACTIONS" and preview_b.checked_transactions==0
        first=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c:list_ledger_account_entries_keyset(str(a),str(cash),None,25,s,c))
        assert len(first.entries)==25 and first.has_more and first.next_cursor
        second=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c:list_ledger_account_entries_keyset(
                str(a),str(cash),first.next_cursor,25,s,c))
        assert len(second.entries)==1 and not second.has_more
        assert {row.id for row in first.entries}.isdisjoint({row.id for row in second.entries})
        assert sum(row.amount_cents for row in first.entries+second.entries)==382500
        assert not first.bank_reconciled and not first.financial_closing_authorized

        for side,name,months,total in (
            ("a","member_a",5,Decimal("835.96")),
            ("b","member_b",3,Decimal("656.96")),
        ):
            tenant=tenant_specs[side][0]
            result=await as_actor(name,side,"TENANT_MEMBER",
                lambda s,c:simulate_loan_price(
                    str(tenant),LoanSimulateRequest(principal=Decimal("500.00"),
                    term_months=months),s,c))
            assert result.total_payable==total
            assert result.schedule[-1].closing_balance==Decimal("0.00")
            loans=await as_actor(name,side,"TENANT_MEMBER",
                lambda s,c:list_tenant_loans(str(tenant),s,c))
            assert len(loans)==1 and loans[0].status=="SOLICITADO"
            assert loans[0].disbursed_at is None and len(loans[0].installments)==months
            assert sum(row.principal_due for row in loans[0].installments)==Decimal("500.00")
            assert sum(row.interest_due for row in loans[0].installments)==total-Decimal("500.00")
        # O administrador não recebe poder de Master para outros tenants.
        with pytest.raises(HTTPException) as blocked:
            await as_actor("admin_a","a","TENANT_ADMIN",
                lambda s,c:list_tenant_contributions(str(b),s,c))
        assert blocked.value.status_code==403
        for name,side,role in (
            ("member_a","a","TENANT_MEMBER"),
            ("shared","a","TENANT_MEMBER"),
            ("master",None,"MASTER"),
        ):
            with pytest.raises(HTTPException) as blocked:
                await as_actor(name,side,role,
                    lambda s,c:get_ledger_integrity_preview(str(a),s,c))
            assert blocked.value.status_code==403
        # Nenhum provedor real, dinheiro, fechamento ou operação produtiva envolvida.
        for table in ("pix_payment_intents","cycle_closings","cycle_profit_distributions"):
            assert await admin.fetchval(
                "SELECT count(*) FROM public."+table+" WHERE tenant_id=ANY($1::uuid[])",
                [a,b])==0
        assert await admin.fetchval(
            "SELECT count(*) FROM public.loans "
            "WHERE tenant_id=ANY($1::uuid[]) AND status='DESEMBOLSADO'",
            [a,b])==0
        print("LAB_CI_VALORES_EXATOS=PASS; A_DEVIDO=7200.00; A_PAGO=3825.00; "
              "A_ABERTO=3375.00; B_DEVIDO=8400.00; B_PAGO=0.00; "
              "B_ABERTO=8400.00; LIVRO_DR=382500_CENTAVOS; "
              "LIVRO_CR=382500_CENTAVOS; PRICE_A=835.96; PRICE_B=656.96")
        print("LAB_INTEGRADO_SQL_SINTETICO=PASS; USERS=8; TENANTS=2; ADMINS=2; "
              "MEMBERSHIPS=10; QUOTAS=8; CONTRIBUTIONS=96; "
              "LEDGER_TX=26; LEDGER_PAGES=2; LOANS_REQUESTED=2; "
              "PIX_REAL=0; DESEMBOLSO_REAL=0; CLOSING=0")
    finally:
        if app is not None:
            await app.close()
        try:
            # Todas as entidades têm prefixo/UUID de laboratório e pertencem
            # a tenants criados aqui. Limpeza mesmo quando um assert falha.
            async with admin.transaction():
                await admin.execute(
                    "DELETE FROM public.tenants WHERE id=ANY($1::uuid[])",[a,b])
                await admin.execute(
                    "DELETE FROM public.users WHERE id=ANY($1::uuid[])",
                    [ids[name] for name in people])
        finally:
            await admin.close()


async def read_quota_contrib(tenant, session, conn):
    quotas=await list_tenant_quotas(str(tenant),session,conn)
    contrib=await list_tenant_contributions(str(tenant),session,conn)
    return quotas,contrib
