"""M401+ — 200+ casos de cancelamento de caixinha sem apagar obrigações."""
from uuid import UUID
import pytest
from app.tenant_exit_rules import TenantWindDown,review_tenant_wind_down

T=UUID(int=1)
A=UUID(int=2)
Q=UUID(int=3)

def make(*,principal=0,profit=0,admin=0,loans=0,
         disputed=0,reserve=0,unreconciled=0,pix=0,
         contract="2027-accepted-contract",audit="CI-REQUEST-EVIDENCE"):
    return TenantWindDown(
        T,A,Q,principal,profit,admin,loans,disputed,reserve,
        unreconciled,pix,contract,audit
    )


@pytest.mark.parametrize("principal",range(201))
def test_201_principal_values_prevent_premature_tenant_closure(principal):
    d=review_tenant_wind_down(make(principal=principal),
        legal_clearance=True,independent_authorization=True)
    assert d.outstanding_cents==principal
    assert d.status==(
        "PENDING_FINANCIAL_SETTLEMENT" if principal
        else "REVIEW_COMPLETE_NO_AUTOMATIC_CLOSE")
    assert not d.tenant_closed
    assert not d.member_data_deleted
    assert not d.pix_enabled
    assert not d.financial_closing_authorized


@pytest.mark.parametrize("key",[
    "principal","profit","admin","loans","disputed",
    "reserve","unreconciled","pix"
])
def test_eight_separate_liabilities_all_block_closure(key):
    d=review_tenant_wind_down(make(**{key:15000}),
        legal_clearance=True,independent_authorization=True)
    assert d.status=="PENDING_FINANCIAL_SETTLEMENT"
    assert d.outstanding_cents==15000


@pytest.mark.parametrize("clearance,approval",[
    (False,False),(False,True),(True,False)
])
def test_missing_gate_prevents_automatic_closure(clearance,approval):
    d=review_tenant_wind_down(make(),legal_clearance=clearance,
                              independent_authorization=approval)
    assert d.status=="PENDING_LEGAL_AND_INDEPENDENT_APPROVAL"
    assert not d.tenant_closed


def test_missing_contract_or_audit_evidence_retains_case():
    for d in (make(contract=None),make(audit=None)):
        result=review_tenant_wind_down(d,legal_clearance=True,
                                       independent_authorization=True)
        assert result.status=="PENDING_DOCUMENTS"


def test_saas_license_cancellation_cannot_release_member_capital():
    d=review_tenant_wind_down(make(principal=90000,loans=10000,
                                     reserve=5000),
        legal_clearance=True,independent_authorization=True)
    assert d.outstanding_cents==105000
    assert d.obligations_preserved
    assert not d.tenant_closed


@pytest.mark.parametrize("invalid",[-1,True,1.5])
def test_no_negative_or_float_balance_or_boolean_as_money(invalid):
    with pytest.raises(ValueError): make(principal=invalid)


def test_same_contract_does_not_erase_audited_history():
    d=review_tenant_wind_down(make(),legal_clearance=True,
                              independent_authorization=True)
    assert d.status=="REVIEW_COMPLETE_NO_AUTOMATIC_CLOSE"
    assert d.member_data_deleted is False
    assert d.financial_closing_authorized is False
