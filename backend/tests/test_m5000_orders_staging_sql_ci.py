"""M5000: staging SQL 038 is guarded, tenant-safe and never settles money.

Static regression tests are NOT permission to apply OCI migrations. Real
postgres testing in a controlled staging environment remains pending.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SQL=ROOT/"staging_migrations/038_orders_reservation_staging_only.sql"


def test_staging_only_never_termux_and_necessary_prerequisites():
    assert SQL.exists()
    assert not (ROOT/"migrations"/SQL.name).exists()
    s=SQL.read_text()
    for anchor in (
        "BEGIN;","COMMIT;",
        "current_database()<>'frcaixinha_staging'",
        "frcaixinha.orders_staging_authorized",
        "current_setting('is_superuser')<>'on'",
        "frcaixinha_mp_financial_worker",
        "NOT rolsuper AND NOT rolbypassrls",
        "mp_pix_collection_operations_staging",
        "mp_pix_settlement_evidence_staging",
        "mp_pix_receipts_staging",
        "mp_orders_provider_reads_staging",
        "mp_seller_connections_staging",
        "ALTER COLUMN provider_payment_id TYPE varchar(80)",
        "mp_pix_collection_tenant_operation_uq",
        "mp_pix_settlement_tenant_operation_fk",
        "mp_pix_receipts_tenant_operation_fk",
        "mp_orders_read_tenant_operation_fk",
        "FOREIGN KEY(tenant_id,operation_id)",
        "ON DELETE RESTRICT",
    ):
        assert anchor in s,anchor


def test_order_reservation_never_allow_cross_tenant_or_unverified_funds():
    s=SQL.read_text()
    scope=s.split("CREATE OR REPLACE FUNCTION public.mp_orders_staging_reserve",1)[1]
    scope=scope.split("CREATE OR REPLACE FUNCTION public.mp_orders_staging_save_checkout",1)[0]
    for anchor in (
        "session_user<>'frcaixinha_mp_financial_worker'",
        "p_environment='PRODUCAO'",
        "s.tenant_id=p_tenant AND s.seller_id=p_collector",
        "s.revoked_at IS NULL",
        "m.id=p_membership AND m.tenant_id=p_tenant",
        "c.id=p_cycle AND c.tenant_id=p_tenant",
        "c.id=p_obligation AND c.tenant_id=p_tenant",
        "c.amount_due-c.amount_paid",
        "l.borrower_membership_id=p_membership",
        "l.status IN('DESEMBOLSADO','INADIMPLENTE')",
        "pg_advisory_xact_lock",
        "FOR UPDATE",
        "current_row.idempotency_key<>p_key",
        "RETURN 'EXISTS'",
        "status NOT IN ('FALHOU','REVERTIDO')",
        "RETURN 'NEW'",
    ):
        assert anchor in scope,anchor
    assert "INSERT INTO public.mp_pix_collection_operations_staging" in scope
    assert "INSERT INTO ledger_entries" not in scope
    assert "UPDATE contributions SET" not in scope
    assert "UPDATE loan_installments SET" not in scope


def test_checkout_save_and_unknown_state_prohibit_double_money():
    s=SQL.read_text()
    for anchor in (
        "public.mp_orders_staging_save_checkout",
        "provider_order_id=p_order",
        "provider_payment_id=p_payment",
        "AND old_row.provider_payment_id=p_payment",
        "RETURN 'REPLAY'",
        "RAISE EXCEPTION 'M038 DENIED: conflicting provider checkout'",
        "public.mp_orders_staging_mark_uncertain",
        "status='PENDENTE_CONCILIACAO'",
        "status='PENDENTE' AND provider_order_id IS NULL",
        "public.mp_orders_staging_get_checkout",
        "REVOKE ALL ON FUNCTION",
        "GRANT EXECUTE ON FUNCTION",
        "TO frcaixinha_mp_financial_worker",
    ):
        assert anchor in s,anchor
    assert "CREATE TRIGGER" not in s
    assert "GRANT INSERT ON TABLE" not in s
    assert "UPDATE ledger_transactions" not in s
    assert "financial_closing_authorized" not in s
