-- Separate connection: failed ACK must not leave an orphan receipt.
\ir m40040_disposable_guard.psql
DO $$
BEGIN
 IF (SELECT count(*) FROM m40010_ci.review_receipts
     WHERE packet_id='44444444-4444-4444-8444-444444444444')<>0 OR
    (SELECT count(*) FROM m40040_ci.receipt_ack)<>0 THEN
  RAISE EXCEPTION 'M40040_BROKEN_ACK_TRANSACTION_LEFT_ORPHAN_RECEIPT';
 END IF;
END;
$$;
\echo M40040_ATOMIC_RECEIPT_AND_ACK_ROLLBACK=PASS
