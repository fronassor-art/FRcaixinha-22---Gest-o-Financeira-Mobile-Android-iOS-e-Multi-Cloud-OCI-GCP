-- Invariantes do razão para qualquer futura contabilização conciliada.
-- Nenhuma API financeira de escrita é habilitada por esta migration.
ALTER TABLE public.ledger_accounts ADD CONSTRAINT ledger_accounts_id_tenant_uq UNIQUE (id, tenant_id);
ALTER TABLE public.ledger_transactions ADD CONSTRAINT ledger_transactions_id_tenant_uq UNIQUE (id, tenant_id);
ALTER TABLE public.ledger_transactions ADD CONSTRAINT ledger_business_reference_uq UNIQUE (tenant_id, reference_id);
ALTER TABLE public.ledger_entries ADD CONSTRAINT ledger_entries_account_tenant_fk
  FOREIGN KEY (account_id, tenant_id) REFERENCES public.ledger_accounts(id, tenant_id);
ALTER TABLE public.ledger_entries ADD CONSTRAINT ledger_entries_transaction_tenant_fk
  FOREIGN KEY (transaction_id, tenant_id) REFERENCES public.ledger_transactions(id, tenant_id);

CREATE FUNCTION public.check_ledger_balance() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  tx_id uuid;
  entry_count integer;
  debit_total bigint;
  credit_total bigint;
BEGIN
  tx_id := COALESCE(NEW.transaction_id, OLD.transaction_id);
  IF NOT EXISTS (SELECT 1 FROM public.ledger_transactions WHERE id=tx_id) THEN
    RETURN NULL;
  END IF;
  SELECT count(*),
         COALESCE(sum(amount_cents) FILTER (WHERE entry_type='DR'),0),
         COALESCE(sum(amount_cents) FILTER (WHERE entry_type='CR'),0)
    INTO entry_count, debit_total, credit_total
    FROM public.ledger_entries WHERE transaction_id=tx_id;
  IF entry_count < 2 OR debit_total <> credit_total THEN
    RAISE EXCEPTION 'Lançamento contábil desbalanceado ou incompleto: %', tx_id;
  END IF;
  RETURN NULL;
END;
$$;

CREATE FUNCTION public.check_new_ledger_transaction() RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
  entry_count integer;
  debit_total bigint;
  credit_total bigint;
BEGIN
  SELECT count(*),
         COALESCE(sum(amount_cents) FILTER (WHERE entry_type='DR'),0),
         COALESCE(sum(amount_cents) FILTER (WHERE entry_type='CR'),0)
    INTO entry_count, debit_total, credit_total
    FROM public.ledger_entries WHERE transaction_id=NEW.id;
  IF entry_count < 2 OR debit_total <> credit_total THEN
    RAISE EXCEPTION 'Transação contábil incompleta: %', NEW.id;
  END IF;
  RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER ledger_entries_balance_guard
AFTER INSERT OR UPDATE OR DELETE ON public.ledger_entries
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.check_ledger_balance();

CREATE CONSTRAINT TRIGGER ledger_transaction_balance_guard
AFTER INSERT ON public.ledger_transactions
DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
EXECUTE FUNCTION public.check_new_ledger_transaction();
