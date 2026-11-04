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
from app.routers.member_cycle_previews import (
    get_my_cycle_risk_preview, get_admin_member_cycle_risk_preview,
)
from app.routers.financial_integrity_previews import (
    get_tenant_financial_integrity_preview,
)
from app.routers.member_lifecycle_sandbox import (
    LifecycleSandboxRequest,
    request_voluntary_exit_sandbox,request_delinquency_review_sandbox,
    my_member_lifecycle_requests,administrative_member_lifecycle_queue,
    member_lifecycle_capabilities,
    member_lifecycle_closing_gates,
)


from app.routers.member_lifecycle_reviews import (
    ReviewEventPayload, lifecycle_review_capabilities,
    list_member_review_events, submit_member_review_event_sandbox,
)

from app.member_cycle_rules import (
    MonthlyDueProof, CapitalMovement, ExitRequest, review_member_cycle,
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
async def test_integrated_real_sql_with_fictional_people_and_exact_money(monkeypatch):
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
        # M401: usar linhas reais do PostgreSQL efêmero, não somente objetos
        # artificiais de teste, para verificar os direitos e o bloqueio por ciclo.
        async def proof_from_db(tenant, membership):
            rows=await admin.fetch(
                "SELECT id,competence,due_date,amount_due,amount_paid,"
                "payment_status,paid_at FROM public.contributions "
                "WHERE tenant_id=$1 AND membership_id=$2 ORDER BY competence",
                tenant,membership,
            )
            proofs=[]
            capital_events=[]
            for item in rows:
                due_amount=int(item["amount_due"]*100)
                received=int(item["amount_paid"]*100)
                settled=(item["paid_at"].date() if
                         item["payment_status"]=="QUITADA" else None)
                proofs.append(MonthlyDueProof(
                    tenant,membership,item["competence"],item["due_date"],
                    due_amount,received,settled,f"CI-DB-{item['id']}"
                ))
                if received:
                    capital_events.append(CapitalMovement(
                        tenant,membership,item["paid_at"],received,item["id"]
                    ))
            return tuple(proofs),tuple(capital_events)
        seen_a=memberships["member_a2"]
        hist,flows=await proof_from_db(a,seen_a)
        assert len(hist)==12 and len(flows)==2
        legal_pending=review_member_cycle(
            a,seen_a,as_of=date(2027,12,31),dues=hist,movements=flows,
            cycle_start=date(2027,1,1),cycle_end_exclusive=date(2028,1,1),
            owner_box=True,legal_gate_approved=False,history_attested=True,
        )
        assert legal_pending.historic_three_unpaid_on==date(2027,4,11)
        assert legal_pending.profit_eligible is None
        assert legal_pending.principal_preserved_cents==22500
        approved_synthetic=review_member_cycle(
            a,seen_a,as_of=date(2027,12,31),dues=hist,movements=flows,
            cycle_start=date(2027,1,1),cycle_end_exclusive=date(2028,1,1),
            owner_box=True,legal_gate_approved=True,history_attested=True,
        )
        assert approved_synthetic.profit_eligible is False
        assert approved_synthetic.capital_days_weight==Decimal(0)
        assert approved_synthetic.principal_preserved_cents==22500
        valid_member=memberships["member_a"]
        clean_hist,clean_flows=await proof_from_db(a,valid_member)
        voluntary=ExitRequest(a,valid_member,date(2027,12,31),uuid.uuid4())
        pending_exit=review_member_cycle(
            a,valid_member,as_of=date(2027,12,31),dues=clean_hist,
            movements=clean_flows,cycle_start=date(2027,1,1),
            cycle_end_exclusive=date(2028,1,1),owner_box=True,
            legal_gate_approved=True,history_attested=True,
            exit_request=voluntary,
        )
        assert pending_exit.exit_status=="REQUESTED_AWAITING_REVIEW"
        assert pending_exit.profit_eligible is None
        assert pending_exit.principal_preserved_cents==180000
        other_hist,other_flows=await proof_from_db(
            b,memberships["member_b"])
        other=review_member_cycle(
            b,memberships["member_b"],as_of=date(2027,12,31),
            dues=other_hist,movements=other_flows,
            cycle_start=date(2027,1,1),cycle_end_exclusive=date(2028,1,1),
            owner_box=False,legal_gate_approved=True,history_attested=True,
        )
        assert other.status=="TENANT_POLICY_REVIEW_REQUIRED"
        assert other.profit_eligible is None
        assert other.principal_preserved_cents==0
        print("LAB_MEMBER_CYCLE_CONTRACT=PASS; OWNER_THREE_MONTHS=OBSERVED; "
              "OWNER_LEGAL_GATE=BLOCKED; OWNER_PRINCIPAL_CENTS=22500; "
              "VOLUNTARY_EXIT=PENDING_REVIEW; "
              "TENANT_CROSS_POLICY=BLOCKED; REAL_PAYOUT=0")
        # M531: endpoints reais de consulta pela sessão + RLS do PostgreSQL.
        own_risk=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda s,c: get_my_cycle_risk_preview(
                a,2027,date(2027,12,31),s,c))
        assert own_risk.registered_contributions_count==12
        assert own_risk.registered_due_cents==180000
        assert own_risk.registered_paid_cents==22500
        assert own_risk.potential_three_unpaid_trigger_date==date(2027,4,11)
        assert own_risk.membership_profit_eligible is None
        assert own_risk.capital_days_weight is None
        assert not own_risk.contractual_effect_applied
        admin_risk=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c: get_admin_member_cycle_risk_preview(
                a,2027,memberships["member_a2"],date(2027,12,31),s,c))
        assert admin_risk.registered_open_cents==157500
        assert admin_risk.membership_id==str(memberships["member_a2"])
        other_risk=await as_actor("member_b","b","TENANT_MEMBER",
            lambda s,c: get_my_cycle_risk_preview(
                b,2027,date(2027,12,31),s,c))
        assert other_risk.registered_paid_cents==0
        assert other_risk.registered_due_cents==210000
        assert other_risk.membership_profit_eligible is None
        for name, side, role, target, target_mid in (
            ("admin_a","a","TENANT_ADMIN",b,memberships["member_b"]),
            ("member_a2","a","TENANT_MEMBER",a,memberships["member_a"]),
            ("master",None,"MASTER",a,memberships["member_a2"]),
        ):
            with pytest.raises(HTTPException) as denied:
                await as_actor(name,side,role,
                    lambda s,c:get_admin_member_cycle_risk_preview(
                        target,2027,target_mid,date(2027,12,31),s,c))
            assert denied.value.status_code==403
        print("M531_RISK_API_PG_RLS=PASS; ADMIN_AND_MEMBER=PASS; "
              "MASTER_AND_CROSS_TENANT=DENIED; "
              "CONTRACTUAL_SANCTION=NOT_APPLIED; BANK_RECONCILED=FALSE")
        # M601 — auditoria cruzada real: contribuições × contas ×
        # políticas × pessoa/vínculo × 26 lançamentos com RLS do banco.
        audit_a=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c:get_tenant_financial_integrity_preview(a,2027,s,c))
        assert audit_a.status=="REGISTERED_INTEGRITY_ONLY"
        assert audit_a.findings==()
        assert (audit_a.members_links,audit_a.members_distinct,
                audit_a.member_role_links,audit_a.admin_role_links)==(5,4,4,1)
        assert (audit_a.registered_contributions,audit_a.registered_due_cents,
                audit_a.registered_paid_cents,audit_a.registered_open_cents)==(
                    48,720000,382500,337500)
        assert (audit_a.complete_count,audit_a.partial_count,
                audit_a.pending_count)==(25,1,22)
        assert audit_a.ledger_transactions==26
        assert audit_a.balanced_transactions==26
        assert audit_a.ledger_dr_cents==audit_a.ledger_cr_cents==382500
        assert audit_a.linked_contributions==26
        assert audit_a.linked_payment_cents==382500
        assert audit_a.missing_ledger_count==0
        assert audit_a.incorrect_link_count==0
        assert audit_a.quota_value_cents==15000
        assert audit_a.admin_percent=="15.00" and audit_a.member_percent=="85.00"
        assert audit_a.cash_available_cents is None
        assert audit_a.master_saas_revenue_cents is None
        assert not audit_a.bank_reconciled and not audit_a.closing_authorized
        audit_b=await as_actor("admin_b","b","TENANT_ADMIN",
            lambda s,c:get_tenant_financial_integrity_preview(b,2027,s,c))
        assert audit_b.findings==()
        assert audit_b.quota_value_cents==17500
        assert (audit_b.registered_contributions,audit_b.registered_due_cents,
                audit_b.registered_paid_cents,audit_b.registered_open_cents)==(
                    48,840000,0,840000)
        assert audit_b.ledger_transactions==0
        assert audit_b.balanced_transactions==0
        assert audit_b.members_distinct==4
        for name,side,role,target in (
            ("admin_a","a","TENANT_ADMIN",b),
            ("member_a","a","TENANT_MEMBER",a),
            ("master",None,"MASTER",a),
        ):
            with pytest.raises(HTTPException) as denied:
                await as_actor(name,side,role,
                    lambda s,c:get_tenant_financial_integrity_preview(
                        target,2027,s,c))
            assert denied.value.status_code==403
        print("M601_FINANCIAL_AUDIT_REAL_PG=PASS; "
              "TWO_TENANTS_ISOLATED=PASS; REGISTERED_A_CENTS=382500; "
              "LEDGER_A_CENTS=382500; CONTRIB_LEDGER_DIFF=0; "
              "MASTER_SAAS_CROSSOVER=0; BANK_PROOF=NOT_ATTESTED")
        # M761: fluxo de pedido e fila, com RLS e PostgreSQL real descartável.
        monkeypatch.setenv("FRCAIXINHA_LIFECYCLE_SANDBOX","1")
        monkeypatch.setenv("ENVIRONMENT","development")
        member_cap=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda sess,conn: member_lifecycle_capabilities(a,2027,sess,conn))
        admin_cap=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda sess,conn: member_lifecycle_capabilities(a,2027,sess,conn))
        assert member_cap.schema_ready and admin_cap.schema_ready
        assert member_cap.can_submit_voluntary_exit
        assert not member_cap.can_submit_delinquency_review
        assert admin_cap.can_submit_delinquency_review
        assert not admin_cap.can_submit_voluntary_exit
        assert not member_cap.financial_effects_enabled
        assert not admin_cap.production_payments_enabled
        monkeypatch.setenv("ENVIRONMENT","production")
        blocked_cap=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda sess,conn: member_lifecycle_capabilities(a,2027,sess,conn))
        assert blocked_cap.schema_ready
        assert not blocked_cap.can_submit_delinquency_review
        monkeypatch.setenv("ENVIRONMENT","development")
        print("M921_SANDBOX_CAPABILITIES_PG=PASS; MEMBER_AND_ADMIN=SCOPED; "
              "PRODUCTION=DENIED; NO_BANK_OR_MONEY=PASS")
        request_key=uuid.uuid4()
        member_exit=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda s,c:request_voluntary_exit_sandbox(
                a,2027,LifecycleSandboxRequest(
                    idempotency_key=request_key,
                    policy_reference="CI-POLICY-2027-ACCEPTED",
                ),s,c))
        assert member_exit.request_kind=="VOLUNTARY_EXIT"
        assert member_exit.status=="PENDING_REVIEW"
        assert not member_exit.financial_effect_applied
        assert not member_exit.member_status_changed
        assert not member_exit.payment_authorized
        repeated=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda s,c:request_voluntary_exit_sandbox(
                a,2027,LifecycleSandboxRequest(
                    idempotency_key=request_key,
                    policy_reference="CI-POLICY-2027-ACCEPTED",
                ),s,c))
        assert repeated.id==member_exit.id
        different_key=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda s,c:request_voluntary_exit_sandbox(
                a,2027,LifecycleSandboxRequest(
                    idempotency_key=uuid.uuid4(),
                    policy_reference="CI-POLICY-2027-ACCEPTED",
                ),s,c))
        assert different_key.id==member_exit.id
        admin_review=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c:request_delinquency_review_sandbox(
                a,2027,memberships["member_a2"],
                LifecycleSandboxRequest(
                    idempotency_key=uuid.uuid4(),
                    policy_reference="CI-POLICY-2027-ACCEPTED",
                ),s,c))
        assert admin_review.request_kind=="DELINQUENCY_REVIEW"
        assert admin_review.id!=member_exit.id
        mine=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda s,c:my_member_lifecycle_requests(a,2027,s,c))
        assert len(mine.items)==2
        assert {item.id for item in mine.items}=={member_exit.id,admin_review.id}
        assert {item.request_kind for item in mine.items}=={
            "VOLUNTARY_EXIT","DELINQUENCY_REVIEW"
        }
        queue=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda s,c:administrative_member_lifecycle_queue(a,2027,s,c))
        assert len(queue.items)==2
        assert {item.request_kind for item in queue.items}=={
            "VOLUNTARY_EXIT","DELINQUENCY_REVIEW",
        }
        other=await as_actor("admin_b","b","TENANT_ADMIN",
            lambda s,c:administrative_member_lifecycle_queue(b,2027,s,c))
        assert other.items==[]
        for name,side,role,target in (
            ("member_a2","a","TENANT_MEMBER",b),
            ("admin_a","a","TENANT_ADMIN",b),
            ("master",None,"MASTER",a),
        ):
            with pytest.raises(HTTPException) as forbidden:
                await as_actor(name,side,role,
                    lambda s,c:administrative_member_lifecycle_queue(
                        target,2027,s,c))
            assert forbidden.value.status_code==403
        # App role não possui mutações diretas, só função controlada.
        async def illegal_update(session,conn):
            await conn.execute(
                "UPDATE public.member_lifecycle_requests "
                "SET status='PENDING_REVIEW' WHERE tenant_id=$1",a)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await as_actor("admin_a","a","TENANT_ADMIN",illegal_update)
        assert await admin.fetchval(
            "SELECT count(*) FROM public.member_lifecycle_requests WHERE tenant_id=$1",
            a,
        )==2
        assert await admin.fetchval(
            "SELECT count(*) FROM public.member_lifecycle_requests "
            "WHERE tenant_id=$1 AND financial_effect_applied=false "
            "AND bank_reconciled=false",a,
        )==2
        assert await admin.fetchval(
            "SELECT count(*) FROM public.memberships "
            "WHERE tenant_id=$1 AND status<>'ATIVA'",a,
        )==0
        assert await admin.fetchval(
            "SELECT count(*) FROM public.cycle_closings "
            "WHERE tenant_id=ANY($1::uuid[])",[a,b],
        )==0
        gates_a=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda sess,conn:member_lifecycle_closing_gates(a,2027,sess,conn))
        assert (gates_a.pending_voluntary_exits,
                gates_a.pending_delinquency_reviews,
                gates_a.registered_unsettled_contributions,
                gates_a.unclosed_loans)==(1,1,23,1)
        assert not gates_a.bank_reconciled
        assert not gates_a.can_close_cycle
        assert not gates_a.can_distribute_profit
        gates_b=await as_actor("admin_b","b","TENANT_ADMIN",
            lambda sess,conn:member_lifecycle_closing_gates(b,2027,sess,conn))
        assert (gates_b.pending_voluntary_exits,
                gates_b.pending_delinquency_reviews,
                gates_b.registered_unsettled_contributions,
                gates_b.unclosed_loans)==(0,0,48,1)
        assert not gates_b.real_payout_enabled
        for name,side,role,target in (
            ("member_a2","a","TENANT_MEMBER",a),
            ("admin_a","a","TENANT_ADMIN",b),
            ("master",None,"MASTER",a),
        ):
            with pytest.raises(HTTPException) as denied:
                await as_actor(name,side,role,
                    lambda sess,conn:member_lifecycle_closing_gates(
                        target,2027,sess,conn))
            assert denied.value.status_code==403
        print("M921_CLOSING_GATES_REAL_PG=PASS; TENANTS=2; "
              "A_PENDING_EXIT=1; A_PENDING_REVIEW=1; "
              "A_REGISTERED_UNSETTLED=23; B_REGISTERED_UNSETTLED=48; "
              "EXTERNAL_BANK_PROOF=FALSE; REAL_DISTRIBUTION=OFF")
        print("M761_LIFECYCLE_SANDBOX_PG=PASS; IDEMPOTENCY=PASS; "
              "ADMIN_REVIEW=PASS; OWN_HISTORY=PASS; TENANTS_ISOLATED=PASS; "
              "PRODUCTION_MONEY=OFF; NO_STATUS_OR_CLOSING_CHANGE=PASS")
        # M1081: decisões de documentos e contestações em PostgreSQL real
        # descartável. A base 028 permanece imutável; 029 guarda eventos.
        await admin.execute(
            "INSERT INTO public.memberships(id,tenant_id,user_id,role) "
            "VALUES($1,$2,$3,'TENANT_ADMIN')",
            uuid.uuid4(),a,ids["shared"],
        )
        review_cap=await as_actor("shared","a","TENANT_ADMIN",
            lambda sess,conn:lifecycle_review_capabilities(a,2027,sess,conn))
        assert review_cap.schema_ready
        assert review_cap.can_review_independently
        member_cap=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda sess,conn:lifecycle_review_capabilities(a,2027,sess,conn))
        assert member_cap.can_submit_contestation
        # A própria revisão de inadimplência aberta pelo admin precisa aparecer
        # para o membro afetado, mesmo sem ter sido aberta por ele.
        visible=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda sess,conn:my_member_lifecycle_requests(a,2027,sess,conn))
        assert len(visible.items)==2
        assert {x.request_kind for x in visible.items}=={
            "VOLUNTARY_EXIT","DELINQUENCY_REVIEW"}
        acceptance=ReviewEventPayload(
            idempotency_key=uuid.uuid4(),
            event_kind="ADMIN_REVIEW_ACCEPTED_SANDBOX",
            evidence_reference="CI-TECHNICAL-EXIT-ACCEPTED",
        )
        accepted=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda sess,conn:submit_member_review_event_sandbox(
                a,2027,uuid.UUID(member_exit.id),acceptance,sess,conn))
        assert accepted.event_kind=="ADMIN_REVIEW_ACCEPTED_SANDBOX"
        same=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda sess,conn:submit_member_review_event_sandbox(
                a,2027,uuid.UUID(member_exit.id),acceptance,sess,conn))
        assert same.event_id==accepted.event_id
        accepted_history=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda sess,conn:list_member_review_events(
                a,2027,uuid.UUID(member_exit.id),sess,conn))
        assert not accepted_history.pending_technical_review
        assert accepted_history.latest_event_kind=="ADMIN_REVIEW_ACCEPTED_SANDBOX"
        assert not accepted_history.financial_effect_applied
        assert not accepted_history.payout_authorized
        # Administrador que criou a revisão não pode decidir o próprio caso.
        with pytest.raises(HTTPException) as forbidden:
            await as_actor("admin_a","a","TENANT_ADMIN",
                lambda sess,conn:submit_member_review_event_sandbox(
                    a,2027,uuid.UUID(admin_review.id),
                    ReviewEventPayload(
                        idempotency_key=uuid.uuid4(),
                        event_kind="ADMIN_REVIEW_REJECTED_SANDBOX",
                        evidence_reference="CI-SELF-APPROVAL-DENIED",
                    ),sess,conn))
        assert forbidden.value.status_code==409
        # Membro tem direito de contestar a revisão iniciada pelo admin.
        contest=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda sess,conn:submit_member_review_event_sandbox(
                a,2027,uuid.UUID(admin_review.id),
                ReviewEventPayload(
                    idempotency_key=uuid.uuid4(),event_kind="MEMBER_CONTESTED",
                    evidence_reference="CI-CONTESTATION-2027-FIRST",
                ),sess,conn))
        assert contest.event_kind=="MEMBER_CONTESTED"
        # Revisão por outro administrador do mesmo tenant; o Master nunca
        # ganha acesso nem pode substituir essa separação de papéis.
        rejected=await as_actor("shared","a","TENANT_ADMIN",
            lambda sess,conn:submit_member_review_event_sandbox(
                a,2027,uuid.UUID(admin_review.id),
                ReviewEventPayload(
                    idempotency_key=uuid.uuid4(),
                    event_kind="ADMIN_REVIEW_REJECTED_SANDBOX",
                    evidence_reference="CI-REVIEW-REJECTED-2027",
                ),sess,conn))
        assert rejected.event_kind=="ADMIN_REVIEW_REJECTED_SANDBOX"
        recontested=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda sess,conn:submit_member_review_event_sandbox(
                a,2027,uuid.UUID(admin_review.id),
                ReviewEventPayload(
                    idempotency_key=uuid.uuid4(),event_kind="MEMBER_CONTESTED",
                    evidence_reference="CI-CONTESTATION-2027-SECOND",
                ),sess,conn))
        assert recontested.event_seq>rejected.event_seq
        final=await as_actor("shared","a","TENANT_ADMIN",
            lambda sess,conn:submit_member_review_event_sandbox(
                a,2027,uuid.UUID(admin_review.id),
                ReviewEventPayload(
                    idempotency_key=uuid.uuid4(),
                    event_kind="ADMIN_REVIEW_ACCEPTED_SANDBOX",
                    evidence_reference="CI-REVIEW-COMPLETED-2027",
                ),sess,conn))
        assert final.event_seq>recontested.event_seq
        case_history=await as_actor("member_a2","a","TENANT_MEMBER",
            lambda sess,conn:list_member_review_events(
                a,2027,uuid.UUID(admin_review.id),sess,conn))
        assert len(case_history.items)==4
        assert not case_history.pending_technical_review
        assert case_history.latest_event_kind=="ADMIN_REVIEW_ACCEPTED_SANDBOX"
        assert not case_history.closing_authorized
        after=await as_actor("admin_a","a","TENANT_ADMIN",
            lambda sess,conn:member_lifecycle_closing_gates(a,2027,sess,conn))
        assert after.pending_voluntary_exits==0
        assert after.pending_delinquency_reviews==0
        assert after.registered_unsettled_contributions==23
        assert after.unclosed_loans==1
        assert not after.bank_reconciled
        assert not after.can_close_cycle
        assert not after.can_distribute_profit
        assert await admin.fetchval(
            "SELECT count(*) FROM public.member_lifecycle_review_events "
            "WHERE tenant_id=$1 AND financial_effect_applied=false "
            "AND bank_reconciled=false",a)==5
        async def illegal_review_update(sess,conn):
            await conn.execute(
                "UPDATE public.member_lifecycle_review_events "
                "SET financial_effect_applied=true WHERE tenant_id=$1",a)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await as_actor("admin_a","a","TENANT_ADMIN",illegal_review_update)
        with pytest.raises(HTTPException) as denied:
            await as_actor("admin_b","b","TENANT_ADMIN",
                lambda sess,conn:list_member_review_events(
                    a,2027,uuid.UUID(admin_review.id),sess,conn))
        assert denied.value.status_code==403
        assert await admin.fetchval(
            "SELECT count(*) FROM public.cycle_closings "
            "WHERE tenant_id=ANY($1::uuid[])",[a,b])==0
        assert await admin.fetchval(
            "SELECT count(*) FROM public.memberships "
            "WHERE tenant_id=$1 AND status<>'ATIVA'",a)==0
        # Vínculo de revisor extra era apenas cenário temporário.
        await admin.execute(
            "DELETE FROM public.memberships WHERE tenant_id=$1 "
            "AND user_id=$2 AND role='TENANT_ADMIN'",a,ids["shared"])
        print("M1081_REVIEW_EVENTS_PG=PASS; MEMBER_CONTESTATION=PASS; "
              "SECOND_ADMIN_INDEPENDENT=PASS; REVIEW_APPEAL=PASS; "
              "EVENTS=5; PENDING_TECHNICAL_REVIEW=0; "
              "BANK_RECONCILED=FALSE; REAL_PAYOUT=0")
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
                    "DELETE FROM public.member_lifecycle_review_events "
                    "WHERE tenant_id=ANY($1::uuid[])",[a,b])
                await admin.execute(
                    "DELETE FROM public.member_lifecycle_requests "
                    "WHERE tenant_id=ANY($1::uuid[])",[a,b])
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
