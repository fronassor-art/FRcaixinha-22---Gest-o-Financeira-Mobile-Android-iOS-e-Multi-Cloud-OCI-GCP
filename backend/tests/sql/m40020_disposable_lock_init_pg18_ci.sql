-- M40020: CI-only atomic reviewer receipt / proposed-revocation collision.
-- Ephemeral PG18 frcaixinha_ci: DO NOT RUN in Termux/Debian or on real DB.
\set ON_ERROR_STOP on
\ir m40010_disposable_guard.psql
\if :{?CI_M40020_DISPOSABLE}
\else
\echo M40020_BLOCKED_MISSING_DISPOSABLE_FLAG
\quit 2
\endif
SELECT CASE WHEN current_database()='frcaixinha_ci'
 AND inet_server_port()=5432 AND session_user='postgres'
 AND current_setting('frfinance.m40020_ci',true)='DISPOSABLE_ONLY'
 THEN 'true' ELSE 'false' END AS m40020_disposable_identity
\gset
\if :m40020_disposable_identity
\else
\echo M40020_BLOCKED_WRONG_CLUSTER
\quit 2
\endif

BEGIN;
CREATE SCHEMA m40020_ci;

CREATE TABLE m40020_ci.proposed_grant_state(
 packet_id uuid NOT NULL,
 actor_db_role name NOT NULL,
 reviewer_id uuid NOT NULL,
 slot integer NOT NULL CHECK(slot IN (1,2)),
 stopped_for_ci boolean NOT NULL DEFAULT false,
 stop_event_id uuid,
 stop_proposed_at timestamptz,
 state text NOT NULL DEFAULT 'CI_UNVERIFIED_PROPOSAL'
   CHECK(state='CI_UNVERIFIED_PROPOSAL'),
 reviewer_identity_authenticated boolean NOT NULL DEFAULT false
   CHECK(reviewer_identity_authenticated=false),
 mandate_ratified boolean NOT NULL DEFAULT false
   CHECK(mandate_ratified=false),
 effective_revocation_verified boolean NOT NULL DEFAULT false
   CHECK(effective_revocation_verified=false),
 CHECK (
   (stopped_for_ci=false AND stop_event_id IS NULL AND stop_proposed_at IS NULL)
    OR
   (stopped_for_ci=true AND stop_event_id IS NOT NULL AND stop_proposed_at IS NOT NULL)
 ),
 CONSTRAINT m40020_role_binding_fk FOREIGN KEY(
   packet_id,actor_db_role,reviewer_id,slot)
   REFERENCES m40010_ci.synthetic_role_bindings(
   packet_id,db_role,reviewer_id,slot),
 PRIMARY KEY(packet_id,actor_db_role),
 UNIQUE(packet_id,slot),
 UNIQUE(stop_event_id)
);

CREATE TABLE m40020_ci.proposed_stop_events(
 event_id uuid PRIMARY KEY,
 packet_id uuid NOT NULL,
 actor_db_role name NOT NULL,
 action text NOT NULL CHECK(action='REVOCATION_PROPOSED'),
 recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 state text NOT NULL DEFAULT 'PROPOSED_ONLY_NOT_EFFECTIVE'
   CHECK(state='PROPOSED_ONLY_NOT_EFFECTIVE'),
 signed_human_consent boolean NOT NULL DEFAULT false
   CHECK(signed_human_consent=false),
 authentic_revocation boolean NOT NULL DEFAULT false
   CHECK(authentic_revocation=false),
 approved boolean NOT NULL DEFAULT false
   CHECK(approved=false),
 payments_enabled boolean NOT NULL DEFAULT false
   CHECK(payments_enabled=false),
 FOREIGN KEY(packet_id,actor_db_role)
   REFERENCES m40020_ci.proposed_grant_state(packet_id,actor_db_role),
 UNIQUE(packet_id,actor_db_role)
);

-- SECURITY DEFINER here is limited to a synthetic-only schema. It can lock
-- a grant row; no source identity, legal grant or real revoked right is proven.
-- The original M40010 RLS WITH CHECK still uses current_user from SET ROLE.
CREATE FUNCTION m40020_ci.lock_proposed_grant() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE
 is_stopped boolean;
BEGIN
 SELECT stopped_for_ci INTO is_stopped
 FROM m40020_ci.proposed_grant_state
 WHERE packet_id=NEW.packet_id AND actor_db_role=NEW.actor_db_role
   AND reviewer_id=NEW.reviewer_id AND slot=NEW.slot
 FOR UPDATE;
 IF NOT FOUND THEN
   RAISE EXCEPTION USING ERRCODE='23503',
     MESSAGE='M40020_NO_SYNTHETIC_ROLE_BINDING';
 END IF;
 IF is_stopped THEN
   RAISE EXCEPTION USING ERRCODE='P0001',
     MESSAGE='M40020_PROPOSED_STOP_BLOCKS_FUTURE_CI_RECEIPT';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER m40020_lock_before_receipt
 BEFORE INSERT ON m40010_ci.review_receipts
 FOR EACH ROW EXECUTE FUNCTION m40020_ci.lock_proposed_grant();

CREATE FUNCTION m40020_ci.only_stop_once() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF OLD.stopped_for_ci OR NEW.stopped_for_ci IS DISTINCT FROM true OR
    OLD.packet_id<>NEW.packet_id OR
    OLD.actor_db_role<>NEW.actor_db_role OR
    OLD.reviewer_id<>NEW.reviewer_id OR
    OLD.slot<>NEW.slot OR
    NEW.stop_event_id IS NULL OR NEW.stop_proposed_at IS NULL OR
    NEW.reviewer_identity_authenticated OR NEW.mandate_ratified OR
    NEW.effective_revocation_verified THEN
   RAISE EXCEPTION USING ERRCODE='55000',
    MESSAGE='M40020_STOP_ONLY_ONCE_NO_REACTIVATION';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER m40020_grant_one_way
 BEFORE UPDATE ON m40020_ci.proposed_grant_state
 FOR EACH ROW EXECUTE FUNCTION m40020_ci.only_stop_once();

CREATE FUNCTION m40020_ci.reject_mutation() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 RAISE EXCEPTION USING ERRCODE='55000',MESSAGE='M40020_APPEND_ONLY_STOP_EVENTS';
END;
$$;
CREATE TRIGGER m40020_stop_events_immutable
 BEFORE UPDATE OR DELETE ON m40020_ci.proposed_stop_events
 FOR EACH ROW EXECUTE FUNCTION m40020_ci.reject_mutation();
CREATE TRIGGER m40020_grant_no_delete
 BEFORE DELETE ON m40020_ci.proposed_grant_state
 FOR EACH ROW EXECUTE FUNCTION m40020_ci.reject_mutation();

ALTER TABLE m40020_ci.proposed_grant_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE m40020_ci.proposed_grant_state FORCE ROW LEVEL SECURITY;
ALTER TABLE m40020_ci.proposed_stop_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE m40020_ci.proposed_stop_events FORCE ROW LEVEL SECURITY;
CREATE POLICY m40020_grant_read ON m40020_ci.proposed_grant_state
 FOR SELECT USING(actor_db_role=current_user);
CREATE POLICY m40020_stop_read ON m40020_ci.proposed_stop_events
 FOR SELECT USING(actor_db_role=current_user);
GRANT USAGE ON SCHEMA m40020_ci TO m40010_a_a,m40010_a_b;
GRANT SELECT ON m40020_ci.proposed_grant_state,m40020_ci.proposed_stop_events
 TO m40010_a_a,m40010_a_b;

-- Packet 4444 exists from M40010 init but has zero receipts.
INSERT INTO m40020_ci.proposed_grant_state(
 packet_id,actor_db_role,reviewer_id,slot) VALUES
 ('44444444-4444-4444-8444-444444444444','m40010_a_a',
  '43333333-3333-4333-8333-333333333333',1),
 ('44444444-4444-4444-8444-444444444444','m40010_a_b',
  '44444444-4444-4444-8444-444444444444',2);

COMMIT;
\echo M40020_CI_SCHEMA_AND_LOCK_TRIGGER=READY
