"""M5300 recovery must never resend or settle ambiguous Pix."""
from dataclasses import replace
from uuid import UUID
import pytest
from app.mp_orders_recovery import (
    CONTRACT,OrdersRecoveryState,RecoveryAction,decide_orders_recovery,
)

T=UUID("00000000-0000-4000-8000-0000000000a1")
ORD="ORD01HRYFWNYRE1MR1E60MW3X0T2P"


def state(**kw):
    d=dict(tenant_id=T,merchant_account_id="2002",
        operation_id="P_"+"a"*32,
        status="PENDENTE_CONCILIACAO",
        order_id=ORD,receipt_exists=False,
        provider_get_processed=False,
        bank_settlement_confirmed=False,
        merchant_binding_valid=True,tenant_context_valid=True,
        signed_webhook_seen=False)
    d.update(kw)
    return OrdersRecoveryState(**d)


@pytest.mark.parametrize("status",(
    "PENDENTE","AGUARDANDO_PROVEDOR","PENDENTE_CONCILIACAO",
))
def test_existing_order_can_only_be_read_not_recreated(status):
    decision=decide_orders_recovery(state(status=status))
    assert decision.action==RecoveryAction.READ_ORDER_ONLY
    assert not decision.can_repost_to_provider
    assert not decision.can_mark_paid
    assert not decision.can_write_ledger


@pytest.mark.parametrize("status",(
    "PENDENTE","AGUARDANDO_PROVEDOR","PENDENTE_CONCILIACAO",
))
def test_unknown_order_timeout_must_be_manual_support(status):
    decision=decide_orders_recovery(state(status=status,order_id=None))
    assert decision.action==RecoveryAction.PROVIDER_SUPPORT_REVIEW
    assert decision.requires_human_review
    assert not decision.can_repost_to_provider


@pytest.mark.parametrize("status",(
    "LIQUIDADO_CONCILIADO","REVERTIDO","FALHOU",
))
def test_final_states_never_replayed(status):
    d=decide_orders_recovery(state(status=status))
    assert d.action==RecoveryAction.NO_ACTION
    assert not d.can_write_ledger


def test_processed_get_and_webhook_still_wait_for_bank():
    d=decide_orders_recovery(state(
        provider_get_processed=True,signed_webhook_seen=True))
    assert d.action==RecoveryAction.CHECK_BANK_ONLY
    assert not d.can_mark_paid
    d=decide_orders_recovery(state(
        provider_get_processed=True,signed_webhook_seen=True,
        bank_settlement_confirmed=True))
    assert d.action==RecoveryAction.CHECK_BANK_ONLY
    assert not d.can_write_ledger


@pytest.mark.parametrize("flag",(
    "merchant_binding_valid","tenant_context_valid",
))
def test_revoked_account_or_wrong_tenant_blocks_poll(flag):
    d=decide_orders_recovery(state(**{flag:False}))
    assert d.action==RecoveryAction.BLOCKED
    assert d.requires_human_review


def test_existing_receipt_is_not_written_again():
    d=decide_orders_recovery(state(receipt_exists=True))
    assert d.action==RecoveryAction.PROVIDER_SUPPORT_REVIEW
    assert not d.can_repost_to_provider
    assert not d.can_write_ledger


@pytest.mark.parametrize("bad",[
    {"merchant_account_id":"invalid-merchant"},
    {"operation_id":"WRONG"},
    {"order_id":"PAY12345"},
    {"status":"UNKNOWN"},
    {"receipt_exists":1},
])
def test_invalid_record_must_raise(bad):
    with pytest.raises(ValueError):
        decide_orders_recovery(state(**bad))


def test_no_side_effects_with_any_recovery_action():
    for fields in (
        {},{"order_id":None},{"provider_get_processed":True},
        {"status":"REVERTIDO"},{"merchant_binding_valid":False},
    ):
        d=decide_orders_recovery(state(**fields))
        assert not d.can_repost_to_provider
        assert not d.can_mark_paid
        assert not d.can_write_ledger
        assert not d.can_issue_payout
    assert CONTRACT=="AI_STUDIO_M5300_ORDERS_RECOVERY_REPLAY_V1"
