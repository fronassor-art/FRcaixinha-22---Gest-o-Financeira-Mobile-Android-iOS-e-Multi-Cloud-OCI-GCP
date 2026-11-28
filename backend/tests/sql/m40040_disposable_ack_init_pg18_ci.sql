-- M40040: scoped synthetic acknowledgement catalog, CI PostgreSQL18 ONLY.
-- Uses RLS and policy NONE for financial grants. NOT a migration.
\ir m40040_disposable_guard.psql
BEGIN;
CREATE SCHEMA m40040_ci;
CREATE TABLE m40040_ci.receipt_ack(
 receipt_id uuid PRIMARY KEY REFERENCES m40010_ci.review_receipts(receipt_id),
 packet_id uuid NOT NULL,
 scope text NOT NULL CHECK(scope IN ('PLATFORM_MASTER','TENANT_ADMIN_OWN')),
 cashbox_key text NOT NULL,
 actor_db_role name NOT NULL,
 idempotency_key uuid NOT NULL,
 request_fingerprint char(64) NOT NULL CHECK(request_fingerprint ~ '^[0-9a-f]{64}$'),
 response_code text NOT NULL DEFAULT 'CI_DOCUMENTARY_RECEIPT_UNVERIFIED'
  CHECK(response_code='CI_DOCUMENTARY_RECEIPT_UNVERIFIED'),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 session_authenticated boolean NOT NULL DEFAULT false CHECK(session_authenticated=false),
 signed_human_consent boolean NOT NULL DEFAULT false CHECK(signed_human_consent=false),
 policy_approved boolean NOT NULL DEFAULT false CHECK(policy_approved=false),
 payout_enabled boolean NOT NULL DEFAULT false CHECK(payout_enabled=false),
 available_balance_cents bigint CHECK(available_balance_cents IS NULL),
 CONSTRAINT m40040_ack_unique_idem UNIQUE(scope,cashbox_key,idempotency_key)
);

CREATE FUNCTION m40040_ci.validate_ack_binding() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF NOT EXISTS(
   SELECT 1 FROM m40010_ci.review_receipts r
   WHERE r.receipt_id=NEW.receipt_id
     AND r.packet_id=NEW.packet_id
     AND r.scope=NEW.scope
     AND r.cashbox_key=NEW.cashbox_key
     AND r.actor_db_role=NEW.actor_db_role
     AND r.idempotency_key=NEW.idempotency_key
   FOR KEY SHARE
 ) THEN
   RAISE EXCEPTION USING ERRCODE='23503',
      MESSAGE='M40040_ACK_NOT_MATCHED_TO_COMMITTED_RECEIPT';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER m40040_ack_binding BEFORE INSERT
 ON m40040_ci.receipt_ack FOR EACH ROW
 EXECUTE FUNCTION m40040_ci.validate_ack_binding();

CREATE FUNCTION m40040_ci.reject_ack_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='M40040_APPEND_ONLY_ACK';
END;
$$;
CREATE TRIGGER m40040_ack_append_only BEFORE UPDATE OR DELETE
 ON m40040_ci.receipt_ack FOR EACH ROW
 EXECUTE FUNCTION m40040_ci.reject_ack_mutation();

ALTER TABLE m40040_ci.receipt_ack ENABLE ROW LEVEL SECURITY;
ALTER TABLE m40040_ci.receipt_ack FORCE ROW LEVEL SECURITY;
CREATE POLICY m40040_ack_select ON m40040_ci.receipt_ack
 FOR SELECT USING(actor_db_role=current_user);
CREATE POLICY m40040_ack_insert ON m40040_ci.receipt_ack
 FOR INSERT WITH CHECK(actor_db_role=current_user);

-- A read-only, invoker-rights status check, never an "approve" operation.
-- Role is determined by current_user in disposable DB, not a request field.
CREATE FUNCTION m40040_ci.inspect_uncertain_commit(
 requested_key uuid,
 requested_fingerprint text
) RETURNS text
LANGUAGE plpgsql SECURITY INVOKER SET search_path=pg_catalog,pg_temp AS $$
DECLARE existing_fingerprint char(64);
BEGIN
 IF requested_key IS NULL OR requested_key='00000000-0000-0000-0000-000000000000'::uuid
 OR requested_fingerprint IS NULL
 OR requested_fingerprint !~ '^[0-9a-f]{64}$' THEN
   RETURN 'INVALID_REQUEST_NO_EFFECT';
 END IF;
 SELECT a.request_fingerprint INTO existing_fingerprint
 FROM m40040_ci.receipt_ack a
 WHERE a.idempotency_key=requested_key AND a.actor_db_role=current_user;
 IF NOT FOUND THEN
   RETURN 'NOT_FOUND_OR_NOT_VISIBLE';
 END IF;
 IF existing_fingerprint=requested_fingerprint THEN
   RETURN 'EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE';
 END IF;
 RETURN 'CONFLICT_DIFFERENT_REQUEST_NO_NEW_WRITE';
END;
$$;
REVOKE ALL ON FUNCTION m40040_ci.inspect_uncertain_commit(uuid,text) FROM PUBLIC;

GRANT USAGE ON SCHEMA m40040_ci TO
 m40010_m_a,m40010_m_b,m40010_a_a,m40010_a_b,m40010_b_a,m40010_b_b;
GRANT SELECT ON m40040_ci.receipt_ack TO
 m40010_m_a,m40010_m_b,m40010_a_a,m40010_a_b,m40010_b_a,m40010_b_b;
GRANT INSERT(receipt_id,packet_id,scope,cashbox_key,actor_db_role,
 idempotency_key,request_fingerprint) ON m40040_ci.receipt_ack TO
 m40010_m_a,m40010_m_b,m40010_a_a,m40010_a_b,m40010_b_a,m40010_b_b;
GRANT EXECUTE ON FUNCTION m40040_ci.inspect_uncertain_commit(uuid,text) TO
 m40010_m_a,m40010_m_b,m40010_a_a,m40010_a_b,m40010_b_a,m40010_b_b;
COMMIT;
\echo M40040_DISPOSABLE_ACK_CATALOG=READY
