"""FR Caixinha AI Studio — M601: auditoria cruzada sem operações financeiras.

Compara direitos cadastrados, membros, políticas e partidas dobradas reais
do PostgreSQL. NUNCA identifica extrato bancário, webhook, lucro disponível
ou autorização de fechamento. Nenhum INSERT/UPDATE/DELETE nem Pix.
"""
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

CODES = frozenset(("1.1.1", "1.2.1", "2.1.1", "2.2.1", "4.1.1"))
MAX_RECORDS = 500
MAX_CENTS = 999_999_999_999

def positive_int(value, *, allow_zero=True):
    if type(value) is not int or not (0 if allow_zero else 1) <= value <= MAX_CENTS:
        raise ValueError("Centavos fora do intervalo auditável")
    return value

def money_cents(value):
    if type(value) is not Decimal or not value.is_finite():
        raise ValueError("Valor monetário não decimal")
    cents = value * 100
    if cents != cents.to_integral_value() or cents < 0 or cents > MAX_CENTS:
        raise ValueError("Precisão monetária não auditável")
    return int(cents)

@dataclass(frozen=True)
class MemberFact:
    id: UUID
    tenant_id: UUID
    user_id: UUID
    role: str
    status: str

@dataclass(frozen=True)
class ContributionFact:
    id: UUID
    tenant_id: UUID
    cycle_id: UUID
    membership_id: UUID
    competence: str
    due_cents: int
    paid_cents: int
    payment_status: str

@dataclass(frozen=True)
class LedgerFact:
    id: UUID
    tenant_id: UUID
    reference: str
    entry_count: int
    dr_entries: int
    cr_entries: int
    dr_cents: int
    cr_cents: int
    cash_dr_cents: int
    capital_cr_cents: int
    invalid_entries: int

@dataclass(frozen=True)
class CyclePolicyFact:
    id: UUID
    tenant_id: UUID
    cycle_id: UUID
    version: int
    admin_pct: Decimal
    member_pct: Decimal
    per_quota_cents: int
    status: str

@dataclass(frozen=True)
class AuditResult:
    tenant_id: UUID
    cycle_id: UUID
    year: int
    status: str
    findings: tuple[str, ...]
    members_links: int
    members_distinct: int
    member_role_links: int
    admin_role_links: int
    quota_value_cents: int | None
    admin_percent: str | None
    member_percent: str | None
    registered_contributions: int
    registered_due_cents: int
    registered_paid_cents: int
    registered_open_cents: int
    complete_count: int
    partial_count: int
    pending_count: int
    ledger_transactions: int
    balanced_transactions: int
    ledger_dr_cents: int
    ledger_cr_cents: int
    linked_contributions: int
    linked_payment_cents: int
    missing_ledger_count: int
    incorrect_link_count: int
    no_bank_evidence: bool = True
    bank_reconciled: bool = False
    cash_available_cents: None = None
    member_profit_share_cents: None = None
    master_saas_revenue_cents: None = None
    closing_authorized: bool = False
    transfer_authorized: bool = False


def analyze_financial_integrity(
    *, tenant_id: UUID, cycle_id: UUID, year: int, cycle_status: str,
    members: tuple[MemberFact, ...],
    contributions: tuple[ContributionFact, ...],
    ledger: tuple[LedgerFact, ...],
    policies: tuple[CyclePolicyFact, ...],
    account_codes: tuple[str, ...],
) -> AuditResult:
    """Fail-closed: divergências resultam em REVIEW_REQUIRED, não em crédito."""
    if (type(tenant_id) is not UUID or type(cycle_id) is not UUID or
        type(year) is not int or not 2020 <= year <= 2100 or
        cycle_status not in ("ABERTO","CONGELADO","EM_APURACAO","LIQUIDADO")):
        raise ValueError("Ciclo inválido")
    for records in (members,contributions,ledger,policies,account_codes):
        if type(records) is not tuple or len(records)>MAX_RECORDS:
            raise ValueError("Relatório excede limite, não pode ser truncado")
    if len(set(account_codes))!=len(account_codes) or any(
        not isinstance(code,str) or len(code)>24 for code in account_codes
    ):
        raise ValueError("Contas canônicas inconsistentes")
    issues=set()
    if not CODES.issubset(account_codes):
        issues.add("CANONICAL_ACCOUNTS_MISSING")
    if cycle_status=="LIQUIDADO":
        issues.add("ALREADY_LIQUIDATED_REQUIRES_EXTERNAL_PROOF")

    seen_members=set()
    seen_user_roles=set()
    user_ids=set()
    member_role_ids=set()
    admins=0
    for m in members:
        if (not isinstance(m,MemberFact) or m.tenant_id!=tenant_id or
            type(m.id) is not UUID or type(m.user_id) is not UUID or
            m.role not in ("TENANT_ADMIN","TENANT_MEMBER") or
            m.status not in ("ATIVA","SUSPENSA","DESLIGADA")):
            raise ValueError("Vínculo fora do tenant ou malformado")
        if m.id in seen_members or (m.user_id,m.role) in seen_user_roles:
            raise ValueError("Vínculo duplicado")
        seen_members.add(m.id)
        seen_user_roles.add((m.user_id,m.role))
        user_ids.add(m.user_id)
        if m.role=="TENANT_MEMBER":member_role_ids.add(m.id)
        else:admins+=1
    if not member_role_ids:
        issues.add("NO_MEMBER_ROLES")

    policy=None
    active=[p for p in policies if isinstance(p,CyclePolicyFact) and p.status=="ACTIVE"]
    for p in policies:
        if (not isinstance(p,CyclePolicyFact) or p.tenant_id!=tenant_id or
            p.cycle_id!=cycle_id or type(p.id) is not UUID or
            type(p.version) is not int or p.version<1 or
            p.status not in ("ACTIVE","SUPERSEDED")):
            raise ValueError("Política de outro ciclo ou não íntegra")
    if len(active)!=1:
        issues.add("ACTIVE_POLICY_NOT_UNIQUE")
    else:
        policy=active[0]
        try:
            if (type(policy.admin_pct) is not Decimal or
                type(policy.member_pct) is not Decimal or
                not policy.admin_pct.is_finite() or
                not policy.member_pct.is_finite() or
                policy.admin_pct+policy.member_pct!=Decimal("100.00") or
                not 0<=policy.admin_pct<=100 or
                not 0<=policy.member_pct<=100 or
                (policy.admin_pct*100)!=((policy.admin_pct*100).to_integral_value()) or
                (policy.member_pct*100)!=((policy.member_pct*100).to_integral_value())):
                issues.add("POLICY_SPLIT_INVALID")
            positive_int(policy.per_quota_cents, allow_zero=False)
        except ValueError:
            issues.add("POLICY_SPLIT_INVALID")

    counts={"QUITADA":0,"PARCIAL":0,"PENDENTE":0}
    dues=paid=0
    seen_contrib=set()
    competence_keys=set()
    paid_by_id={}
    for c in contributions:
        if (not isinstance(c,ContributionFact) or c.tenant_id!=tenant_id or
            c.cycle_id!=cycle_id or c.membership_id not in member_role_ids or
            type(c.id) is not UUID or
            not isinstance(c.competence,str) or len(c.competence)!=7 or
            c.competence[:5]!=f"{year}-" or
            not c.competence[5:].isdigit() or not 1<=int(c.competence[5:])<=12):
            raise ValueError("Contribuição sem vínculo de membro, ciclo ou competência válida")
        if c.id in seen_contrib or (c.membership_id,c.competence) in competence_keys:
            raise ValueError("Obrigação duplicada")
        seen_contrib.add(c.id)
        competence_keys.add((c.membership_id,c.competence))
        positive_int(c.due_cents, allow_zero=False)
        positive_int(c.paid_cents)
        if c.paid_cents>c.due_cents:
            raise ValueError("Contribuição paga acima do devido; bloqueada para revisão")
        expected=("QUITADA" if c.paid_cents==c.due_cents else
                  "PARCIAL" if c.paid_cents>0 else "PENDENTE")
        if c.payment_status not in counts or c.payment_status!=expected:
            issues.add("CONTRIBUTION_STATUS_INCONSISTENT")
        else:counts[c.payment_status]+=1
        dues+=c.due_cents
        paid+=c.paid_cents
        paid_by_id[str(c.id)]=c.paid_cents
    if dues>MAX_CENTS or paid>MAX_CENTS:
        raise ValueError("Total não cabe em limite auditável")
    if paid>dues:
        issues.add("OVERPAID_CONTRIBUTIONS")
    if not contributions:
        issues.add("NO_CONTRIBUTIONS_REGISTERED")

    tx_ids=set()
    refs=set()
    linked_ids=set()
    linked_cents=0
    mismatched=0
    balanced=0
    dr_total=cr_total=0
    for t in ledger:
        if (not isinstance(t,LedgerFact) or t.tenant_id!=tenant_id or
            type(t.id) is not UUID or not isinstance(t.reference,str) or
            not 1<=len(t.reference)<=100):
            raise ValueError("Lançamento fora do tenant")
        if t.id in tx_ids or t.reference in refs:
            raise ValueError("Referência contábil duplicada")
        tx_ids.add(t.id)
        refs.add(t.reference)
        for number in (t.entry_count,t.dr_entries,t.cr_entries,t.dr_cents,
                       t.cr_cents,t.cash_dr_cents,t.capital_cr_cents,t.invalid_entries):
            positive_int(number)
        good=(t.entry_count>=2 and t.dr_entries>0 and t.cr_entries>0 and
              t.entry_count==t.dr_entries+t.cr_entries and
              t.dr_cents==t.cr_cents and t.dr_cents>0 and
              t.invalid_entries==0)
        if good:balanced+=1
        else:issues.add("UNBALANCED_LEDGER_TRANSACTION")
        dr_total+=t.dr_cents
        cr_total+=t.cr_cents
        if t.reference in paid_by_id:
            linked_ids.add(t.reference)
            linked_cents+=t.cash_dr_cents
            if (not good or t.cash_dr_cents!=paid_by_id[t.reference] or
                t.capital_cr_cents!=paid_by_id[t.reference]):
                mismatched+=1
    if dr_total!=cr_total:
        issues.add("LEDGER_TOTALS_DIFFER")
    missing=sum(1 for ref,cents in paid_by_id.items() if cents>0 and ref not in linked_ids)
    if missing:
        issues.add("REGISTERED_PAYMENTS_WITHOUT_LEDGER")
    if mismatched:
        issues.add("CONTRIBUTION_LEDGER_DISAGREEMENT")
    if not ledger and paid>0:
        issues.add("NO_LEDGER_FOR_RECORDED_PAYMENTS")
    # Nunca tratar um lançamento isolado como confirmação bancária.
    return AuditResult(
        tenant_id=tenant_id,cycle_id=cycle_id,year=year,
        status="REVIEW_REQUIRED" if issues else "REGISTERED_INTEGRITY_ONLY",
        findings=tuple(sorted(issues)),
        members_links=len(members),members_distinct=len(user_ids),
        member_role_links=len(member_role_ids),admin_role_links=admins,
        quota_value_cents=policy.per_quota_cents if policy else None,
        admin_percent=str(policy.admin_pct) if policy else None,
        member_percent=str(policy.member_pct) if policy else None,
        registered_contributions=len(contributions),
        registered_due_cents=dues,registered_paid_cents=paid,
        registered_open_cents=max(dues-paid,0),
        complete_count=counts["QUITADA"],partial_count=counts["PARCIAL"],
        pending_count=counts["PENDENTE"],
        ledger_transactions=len(ledger),balanced_transactions=balanced,
        ledger_dr_cents=dr_total,ledger_cr_cents=cr_total,
        linked_contributions=len(linked_ids),
        linked_payment_cents=linked_cents,
        missing_ledger_count=missing,incorrect_link_count=mismatched,
    )
