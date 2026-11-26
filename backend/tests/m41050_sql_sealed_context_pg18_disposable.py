#!/usr/bin/env python3
"""M41050: bind consumed M40700 tickets to a disposable RLS capability."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import os
from pathlib import Path
import secrets
import sys
from threading import Barrier, Event
from time import monotonic, sleep
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "backend" / "tests"
sys.path.insert(0, str(ROOT / "backend" / "app"))
sys.path.insert(0, str(TESTS))
from m40700_request_proof_disposable import (
    SCOPE,
    WRITE_SCOPE,
    bootstrap as bootstrap_m40700,
)
from m41050_session_context_seal_prototype import install_session_capability

DATABASE = "fr_m40700_disposable_ci"
PORT = 55439
DATABASE_PASSWORD = "only_m41050_disposable_ci"
AUTH_PASSWORD = "m40680-fixture-auth-only-not-real"
APP_PASSWORD = "synthetic-only-m40650-ci-not-a-real-credential"


def require_disposable() -> str:
    expected = {
        "GITHUB_ACTIONS": "true",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "CI_M41050_DISPOSABLE": "1",
        "CI_M41060_DISPOSABLE": "1",
        "CI_M41080_DISPOSABLE": "1",
        "CI_M41090_DISPOSABLE": "1",
        "CI_M41100_DISPOSABLE": "1",
        "CI_M41140_DISPOSABLE": "1",
        "CI_M40700_DISPOSABLE": "1",
        "CI_M40680_DISPOSABLE": "1",
        "CI_M40560_DISPOSABLE": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("M41050_DISPOSABLE_ONLY")
    dsn = os.environ.get("CI_M41050_DATABASE_URL", "")
    try:
        parsed = urlsplit(dsn)
        valid = (
            parsed.scheme == "postgresql"
            and parsed.hostname == "127.0.0.1"
            and parsed.port == PORT
            and parsed.path == "/" + DATABASE
            and parsed.username == "postgres"
            and parsed.password == DATABASE_PASSWORD
            and not parsed.query
            and not parsed.fragment
            and os.environ.get("CI_M40700_DATABASE_URL") == dsn
            and os.environ.get("CI_M41080_DATABASE_URL") == dsn
            and os.environ.get("CI_M41090_DATABASE_URL") == dsn
            and os.environ.get("CI_M41100_DATABASE_URL") == dsn
            and os.environ.get("CI_M41140_DATABASE_URL") == dsn
        )
    except (ValueError, AttributeError, TypeError):
        valid = False
    if not valid:
        raise RuntimeError("M41050_DISPOSABLE_DATABASE_IDENTITY_DENIED")
    return dsn


def connect(dsn: str, *, user: str = "postgres", password: str = DATABASE_PASSWORD,
            autocommit: bool = True):
    import psycopg
    parsed = urlsplit(dsn)
    return psycopg.connect(
        host=parsed.hostname, port=parsed.port, dbname=parsed.path[1:],
        user=user, password=password, autocommit=autocommit, connect_timeout=5,
    )


def build_ticket_context(owner) -> None:
    owner.execute("""
        ALTER TABLE m40650.sessions ADD COLUMN context_generation bigint
        NOT NULL DEFAULT 0 CHECK(context_generation>=0)
    """)
    owner.execute("""
        CREATE FUNCTION m40700.bump_context_generation()
        RETURNS trigger LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp
        AS $body$
        BEGIN
          IF OLD.user_id IS DISTINCT FROM NEW.user_id
             OR OLD.active_role IS DISTINCT FROM NEW.active_role
             OR OLD.active_tenant_id IS DISTINCT FROM NEW.active_tenant_id
             OR OLD.revoked_at IS DISTINCT FROM NEW.revoked_at
             OR OLD.context_generation IS DISTINCT FROM NEW.context_generation
          THEN NEW.context_generation:=OLD.context_generation+1;
          ELSE NEW.context_generation:=OLD.context_generation;
          END IF;
          RETURN NEW;
        END
        $body$
    """)
    owner.execute("ALTER FUNCTION m40700.bump_context_generation() OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON FUNCTION m40700.bump_context_generation() FROM PUBLIC")
    owner.execute("""
        CREATE TRIGGER m41120_context_generation BEFORE UPDATE ON m40650.sessions
        FOR EACH ROW EXECUTE FUNCTION m40700.bump_context_generation()
    """)
    owner.execute("""
        CREATE TABLE m40700.ticket_context(
          ticket_digest text PRIMARY KEY REFERENCES m40700.ticket_scopes(ticket_digest),
          bound_user_id uuid NOT NULL,
          bound_role text NOT NULL CHECK(bound_role IN ('TENANT_MEMBER','TENANT_ADMIN')),
          context_generation bigint NOT NULL CHECK(context_generation>=0)
        )
    """)
    owner.execute("ALTER TABLE m40700.ticket_context OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON m40700.ticket_context FROM PUBLIC,m40680_auth,m40650_app")
    owner.execute("""
        CREATE FUNCTION m40700.issue_bound_v2(
          p_digest text,p_tenant uuid,p_nonce uuid,p_expiry bigint,p_scope text,
          p_user uuid,p_role text,p_generation bigint,p_proof text
        ) RETURNS text LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $body$
        DECLARE
          v_secret bytea;
          v_payload text;
          v_expected text;
          v_legacy_proof text;
          v_ticket text;
          v_ticket_digest text;
          v_session_expiry timestamptz;
        BEGIN
          IF p_digest IS NULL OR p_digest !~ '^[0-9a-f]{64}$'
             OR p_tenant IS NULL OR p_nonce IS NULL OR p_expiry IS NULL
             OR p_user IS NULL OR p_generation IS NULL OR p_generation<0
             OR p_role IS NULL OR p_role NOT IN ('TENANT_MEMBER','TENANT_ADMIN')
             OR p_scope IS NULL OR p_scope NOT IN ('READ_ENTRIES','WRITE_TEST_ENTRY')
             OR p_proof IS NULL OR p_proof !~ '^[0-9a-f]{64}$'
          THEN RETURN NULL; END IF;
          SELECT key INTO v_secret FROM m40700.verifier_secret WHERE singleton=true;
          IF NOT FOUND THEN RETURN NULL; END IF;
          v_payload:='FRF-M41120|v2|'||p_digest||'|'||p_tenant::text||'|'||
                     p_nonce::text||'|'||p_expiry::text||'|'||p_scope||'|'||
                     p_user::text||'|'||p_role||'|'||p_generation::text;
          v_expected:=pg_catalog.encode(
              m40700.hmac(pg_catalog.convert_to(v_payload,'UTF8'),v_secret,'sha256'),'hex');
          IF p_proof<>v_expected THEN RETURN NULL; END IF;
          SELECT s.expires_at INTO v_session_expiry FROM m40650.sessions AS s
           WHERE s.token_digest=p_digest AND s.user_id=p_user
             AND s.active_role=p_role AND s.active_tenant_id=p_tenant
             AND s.context_generation=p_generation AND s.revoked_at IS NULL
             AND s.expires_at>pg_catalog.clock_timestamp()
           FOR SHARE OF s;
          IF NOT FOUND THEN RETURN NULL; END IF;
          -- Reuse the existing issuer's nonce, time, account and membership checks.
          -- Only this owner-controlled wrapper can invoke the old issuer here.
          v_legacy_proof:=pg_catalog.encode(m40700.hmac(pg_catalog.convert_to(
              'FRF-M40700|v1|'||p_digest||'|'||p_tenant::text||'|'||
              p_nonce::text||'|'||p_expiry::text||'|'||p_scope,'UTF8'),
              v_secret,'sha256'),'hex');
          v_ticket:=m40700.issue_bound(p_digest,p_tenant,p_nonce,p_expiry,p_scope,v_legacy_proof);
          IF v_ticket IS NULL THEN RETURN NULL; END IF;
          v_ticket_digest:=pg_catalog.encode(pg_catalog.sha256(pg_catalog.convert_to(v_ticket,'UTF8')),'hex');
          UPDATE m40650.m40680_tickets SET expires_at=LEAST(expires_at,v_session_expiry,
              pg_catalog.to_timestamp(p_expiry)) WHERE digest=v_ticket_digest;
          INSERT INTO m40700.ticket_context(ticket_digest,bound_user_id,bound_role,context_generation)
          VALUES(v_ticket_digest,p_user,p_role,p_generation);
          RETURN v_ticket;
        END
        $body$
    """)
    signature="m40700.issue_bound_v2(text,uuid,uuid,bigint,text,uuid,text,bigint,text)"
    owner.execute("ALTER FUNCTION "+signature+" OWNER TO m40650_owner")
    owner.execute("REVOKE ALL ON FUNCTION "+signature+" FROM PUBLIC,m40650_app")
    owner.execute("GRANT EXECUTE ON FUNCTION "+signature+" TO m40680_auth")
    owner.execute("REVOKE EXECUTE ON FUNCTION m40700.issue_bound(text,uuid,uuid,bigint,text,text) FROM m40680_auth")
    owner.execute("REVOKE EXECUTE ON FUNCTION m40650.m40680_consume(text,uuid) FROM m40650_app")


def build_context_schema(owner) -> None:
    build_ticket_context(owner)
    owner.execute("CREATE SCHEMA m41050 AUTHORIZATION m40650_owner")
    owner.execute("REVOKE ALL ON SCHEMA m41050 FROM PUBLIC")
    owner.execute("GRANT USAGE ON SCHEMA m41050 TO m40650_app")
    owner.execute("""
        CREATE TABLE m41050.session_caps (
          token_hash bytea PRIMARY KEY
            CHECK (pg_catalog.octet_length(token_hash)=32),
          session_digest text NOT NULL,
          bound_user_id uuid NOT NULL,
          bound_role text NOT NULL CHECK (bound_role IN ('TENANT_ADMIN','TENANT_MEMBER')),
          context_generation bigint NOT NULL,
          tenant_id uuid NOT NULL,
          expires_at timestamptz NOT NULL,
          scope_name text NOT NULL
            CHECK(scope_name IN ('READ_ENTRIES','WRITE_TEST_ENTRY')),
          revoked_at timestamptz
        )
    """)
    owner.execute("""
        CREATE TABLE m41050.protected_entries (
          entry_id uuid PRIMARY KEY,
          tenant_id uuid NOT NULL,
          member_id uuid NOT NULL,
          amount_cents integer NOT NULL CHECK (amount_cents>0),
          idempotency_key text NOT NULL
            CHECK(pg_catalog.length(idempotency_key) BETWEEN 8 AND 128),
          UNIQUE(tenant_id,idempotency_key)
        )
    """)
    owner.execute("""
        CREATE FUNCTION m41050.bind_ticket(p_ticket text,p_tenant uuid)
        RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE
          v_result jsonb;
          v_bound_user uuid;
          v_bound_role text;
          v_generation bigint;
          v_ticket_digest text;
          v_session_digest text;
          v_user_id uuid;
          v_role text;
          v_tenant uuid;
          v_expiry timestamptz;
          v_scope text;
          v_capability text;
        BEGIN
          IF p_ticket IS NULL OR p_ticket !~ '^[0-9a-f]{64}$'
             OR p_tenant IS NULL
          THEN RETURN NULL; END IF;

          -- M40680 atomically consumes the one-use ticket and rechecks the
          -- active account, session and membership inside this transaction.
          v_result := m40650.m40680_consume(p_ticket,p_tenant);
          IF COALESCE((v_result->>'authorized')::boolean,false) IS NOT TRUE
          THEN RETURN NULL; END IF;

          v_ticket_digest := pg_catalog.encode(
            pg_catalog.sha256(pg_catalog.convert_to(p_ticket,'UTF8')),'hex'
          );
          SELECT t.session_digest,t.expires_at,x.scope_name,c.bound_user_id,c.bound_role,c.context_generation
            INTO v_session_digest,v_expiry,v_scope,v_bound_user,v_bound_role,v_generation
            FROM m40650.m40680_tickets AS t
            JOIN m40700.ticket_scopes AS x
              ON x.ticket_digest=t.digest
            JOIN m40700.ticket_context AS c ON c.ticket_digest=t.digest
           WHERE t.digest=v_ticket_digest
             AND t.tenant_id=p_tenant
             AND t.used_at IS NOT NULL;
          IF NOT FOUND THEN RETURN NULL; END IF;

          SELECT s.user_id,s.active_role,s.active_tenant_id,
                 LEAST(
                   v_expiry,s.expires_at,
                   pg_catalog.statement_timestamp()+interval '20 seconds'
                 )
            INTO v_user_id,v_role,v_tenant,v_expiry
            FROM m40650.sessions AS s
            JOIN m40650.users AS u
              ON u.id=s.user_id AND u.status='ACTIVE'
            JOIN m40650.memberships AS m
              ON m.user_id=s.user_id
             AND m.tenant_id=s.active_tenant_id
             AND m.role=s.active_role
             AND m.status='ATIVA'
           WHERE s.token_digest=v_session_digest
             AND s.user_id=v_bound_user AND s.active_role=v_bound_role
             AND s.context_generation=v_generation
             AND s.revoked_at IS NULL
             AND s.expires_at>pg_catalog.statement_timestamp()
             AND s.active_role IN ('TENANT_ADMIN','TENANT_MEMBER')
             AND s.active_tenant_id=p_tenant
           FOR SHARE OF s;
          IF NOT FOUND OR v_expiry<=pg_catalog.statement_timestamp()
          THEN RETURN NULL; END IF;

          v_capability :=
            pg_catalog.replace(pg_catalog.gen_random_uuid()::text,'-','')
            || pg_catalog.replace(pg_catalog.gen_random_uuid()::text,'-','');
          INSERT INTO m41050.session_caps(
            token_hash,session_digest,bound_user_id,bound_role,
            context_generation,tenant_id,expires_at,scope_name
          )
          VALUES(
            pg_catalog.sha256(
              pg_catalog.convert_to(v_capability,'UTF8')
            ),
            v_session_digest,v_user_id,v_role,v_generation,v_tenant,v_expiry,v_scope
          );
          RETURN v_capability;
        END
        $body$
    """)
    owner.execute("""
        CREATE FUNCTION m41050.current_claims()
        RETURNS TABLE(user_id uuid,role_name text,tenant_id uuid,scope_name text)
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE v_capability text;
        BEGIN
          v_capability := pg_catalog.current_setting(
            'app.session_capability',true
          );
          IF v_capability IS NULL OR v_capability !~ '^[0-9a-f]{64}$'
          THEN RETURN; END IF;

          RETURN QUERY
          SELECT s.user_id,s.active_role,s.active_tenant_id,c.scope_name
            FROM m41050.session_caps AS c
            JOIN m40650.sessions AS s
              ON s.token_digest=c.session_digest
            JOIN m40650.users AS u
              ON u.id=s.user_id AND u.status='ACTIVE'
            JOIN m40650.memberships AS m
              ON m.user_id=s.user_id
             AND m.tenant_id=s.active_tenant_id
             AND m.role=s.active_role
             AND m.status='ATIVA'
           WHERE c.token_hash=pg_catalog.sha256(
                   pg_catalog.convert_to(v_capability,'UTF8')
                 )
             AND c.revoked_at IS NULL
             AND c.expires_at>pg_catalog.statement_timestamp()
             AND s.user_id=c.bound_user_id
             AND s.active_role=c.bound_role
             AND s.context_generation=c.context_generation
             AND s.active_tenant_id=c.tenant_id
             AND s.active_role IN ('TENANT_ADMIN','TENANT_MEMBER')
             AND s.revoked_at IS NULL
             AND s.expires_at>pg_catalog.statement_timestamp();
        END
        $body$
    """)
    owner.execute(
        "ALTER TABLE m41050.session_caps OWNER TO m40650_owner"
    )
    owner.execute(
        "ALTER TABLE m41050.protected_entries OWNER TO m40650_owner"
    )
    owner.execute("""
        ALTER FUNCTION m41050.bind_ticket(text,uuid) OWNER TO m40650_owner
    """)
    owner.execute("""
        ALTER FUNCTION m41050.current_claims() OWNER TO m40650_owner
    """)
    owner.execute("""
        ALTER TABLE m41050.protected_entries ENABLE ROW LEVEL SECURITY
    """)
    owner.execute("""
        ALTER TABLE m41050.protected_entries FORCE ROW LEVEL SECURITY
    """)
    owner.execute("""
        CREATE POLICY tenant_read ON m41050.protected_entries
        FOR SELECT TO m40650_app
        USING (
          EXISTS (
            SELECT 1 FROM m41050.current_claims() AS c
             WHERE c.scope_name='READ_ENTRIES'
               AND c.tenant_id=protected_entries.tenant_id
               AND (
                 (c.role_name='TENANT_ADMIN')
                 OR (c.role_name='TENANT_MEMBER'
                     AND c.user_id=protected_entries.member_id)
               )
          )
        )
    """)
    owner.execute("""
        CREATE FUNCTION m41050.can_write_entry(p_tenant uuid,p_member uuid)
        RETURNS boolean LANGUAGE plpgsql VOLATILE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE
          v_capability text;
          v_token_hash bytea;
          v_session_digest text;
          v_actor uuid;
          v_role text;
          v_tenant uuid;
          v_scope text;
          v_generation bigint;
          v_cap_expiry timestamptz;
          v_initial_cap_revoked timestamptz;
          v_locked_digest text;
          v_locked_actor uuid;
          v_locked_role text;
          v_locked_tenant uuid;
          v_locked_scope text;
          v_locked_generation bigint;
          v_locked_expiry timestamptz;
          v_locked_revoked timestamptz;
          v_session_user uuid;
          v_session_role text;
          v_session_tenant uuid;
          v_session_generation bigint;
          v_session_expiry timestamptz;
          v_session_revoked timestamptz;
          v_actor_status text;
          v_member_status text;
          v_admin_membership_status text;
          v_member_membership_status text;
        BEGIN
          IF p_tenant IS NULL OR p_member IS NULL THEN RETURN false; END IF;
          v_capability:=pg_catalog.current_setting(
            'app.session_capability',true
          );
          IF v_capability IS NULL OR v_capability !~ '^[0-9a-f]{64}$'
          THEN RETURN false; END IF;
          v_token_hash:=pg_catalog.sha256(
            pg_catalog.convert_to(v_capability,'UTF8')
          );

          -- Read protected context only to acquire locks in stable order.
          SELECT c.session_digest,c.bound_user_id,c.bound_role,c.tenant_id,
                 c.scope_name,c.context_generation,c.expires_at,c.revoked_at
            INTO v_session_digest,v_actor,v_role,v_tenant,v_scope,
                 v_generation,v_cap_expiry,v_initial_cap_revoked
            FROM m41050.session_caps AS c
           WHERE c.token_hash=v_token_hash;
          IF NOT FOUND THEN RETURN false; END IF;
          IF v_actor IS NULL OR v_role<>'TENANT_ADMIN'
             OR v_tenant IS DISTINCT FROM p_tenant
             OR v_scope<>'WRITE_TEST_ENTRY'
          THEN RETURN false; END IF;

          -- Lifecycle revocation locks its user or membership before rotating
          -- the session and capability. Use the same deterministic lock order.
          PERFORM u.id
            FROM m40650.users AS u
           WHERE u.id=v_actor OR u.id=p_member
           ORDER BY u.id
           FOR SHARE;
          PERFORM m.user_id
            FROM m40650.memberships AS m
           WHERE m.tenant_id=p_tenant
             AND ((m.user_id=v_actor AND m.role='TENANT_ADMIN')
               OR (m.user_id=p_member AND m.role='TENANT_MEMBER'))
           ORDER BY m.user_id,m.tenant_id,m.role
           FOR SHARE;

          SELECT u.status INTO v_actor_status
            FROM m40650.users AS u WHERE u.id=v_actor;
          IF NOT FOUND THEN RETURN false; END IF;
          SELECT u.status INTO v_member_status
            FROM m40650.users AS u WHERE u.id=p_member;
          IF NOT FOUND THEN RETURN false; END IF;
          SELECT m.status INTO v_admin_membership_status
            FROM m40650.memberships AS m
           WHERE m.user_id=v_actor AND m.tenant_id=p_tenant
             AND m.role='TENANT_ADMIN';
          IF NOT FOUND THEN RETURN false; END IF;
          SELECT m.status INTO v_member_membership_status
            FROM m40650.memberships AS m
           WHERE m.user_id=p_member AND m.tenant_id=p_tenant
             AND m.role='TENANT_MEMBER';
          IF NOT FOUND THEN RETURN false; END IF;

          SELECT s.user_id,s.active_role,s.active_tenant_id,
                 s.context_generation,s.expires_at,s.revoked_at
            INTO v_session_user,v_session_role,v_session_tenant,
                 v_session_generation,v_session_expiry,v_session_revoked
            FROM m40650.sessions AS s
           WHERE s.token_digest=v_session_digest
           FOR SHARE;
          IF NOT FOUND THEN RETURN false; END IF;

          SELECT c.session_digest,c.bound_user_id,c.bound_role,c.tenant_id,
                 c.scope_name,c.context_generation,c.expires_at,c.revoked_at
            INTO v_locked_digest,v_locked_actor,v_locked_role,v_locked_tenant,
                 v_locked_scope,v_locked_generation,v_locked_expiry,v_locked_revoked
            FROM m41050.session_caps AS c
           WHERE c.token_hash=v_token_hash
           FOR SHARE;
          IF NOT FOUND THEN RETURN false; END IF;

          RETURN v_locked_digest IS NOT DISTINCT FROM v_session_digest
             AND v_locked_actor IS NOT DISTINCT FROM v_actor
             AND v_locked_role IS NOT DISTINCT FROM v_role
             AND v_locked_tenant IS NOT DISTINCT FROM v_tenant
             AND v_locked_scope IS NOT DISTINCT FROM v_scope
             AND v_locked_generation IS NOT DISTINCT FROM v_generation
             AND v_locked_expiry IS NOT DISTINCT FROM v_cap_expiry
             AND v_locked_revoked IS NULL
             AND v_locked_expiry>pg_catalog.clock_timestamp()
             AND v_initial_cap_revoked IS NULL
             AND v_cap_expiry>pg_catalog.clock_timestamp()
             AND v_session_user=v_actor
             AND v_session_role=v_role
             AND v_session_tenant=p_tenant
             AND v_session_generation=v_generation
             AND v_session_revoked IS NULL
             AND v_session_expiry>pg_catalog.clock_timestamp()
             AND v_actor_status='ACTIVE'
             AND v_member_status='ACTIVE'
             AND v_admin_membership_status='ATIVA'
             AND v_member_membership_status='ATIVA';
        END
        $body$
    """)
    owner.execute("""
        ALTER FUNCTION m41050.can_write_entry(uuid,uuid)
        OWNER TO m40650_owner
    """)
    owner.execute("""
        CREATE POLICY tenant_write ON m41050.protected_entries
        FOR INSERT TO m40650_app
        WITH CHECK (
          m41050.can_write_entry(tenant_id,member_id)
        )
    """)
    # Fixture-only permanent invalidation: a switch back must not resurrect
    # a previously issued capability. Binding locks the session row first.
    owner.execute("""
        CREATE FUNCTION m41050.invalidate_changed_session_caps()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        BEGIN
          IF OLD.user_id IS DISTINCT FROM NEW.user_id
             OR OLD.active_role IS DISTINCT FROM NEW.active_role
             OR OLD.active_tenant_id IS DISTINCT FROM NEW.active_tenant_id
             OR OLD.revoked_at IS DISTINCT FROM NEW.revoked_at
             OR OLD.context_generation IS DISTINCT FROM NEW.context_generation
          THEN
            UPDATE m41050.session_caps
               SET revoked_at=pg_catalog.clock_timestamp()
             WHERE session_digest=OLD.token_digest AND revoked_at IS NULL;
          END IF;
          RETURN NEW;
        END
        $body$
    """)
    owner.execute("""
        ALTER FUNCTION m41050.invalidate_changed_session_caps()
        OWNER TO m40650_owner
    """)
    owner.execute("""
        CREATE TRIGGER m41110_invalidate_changed_session_caps
        AFTER UPDATE
        ON m40650.sessions FOR EACH ROW
        EXECUTE FUNCTION m41050.invalidate_changed_session_caps()
    """)
    # A privileged lifecycle change rotates the existing session generation.
    # The old proof/ticket/capability cannot become valid again on reactivation.
    owner.execute("""
        CREATE FUNCTION m41050.rotate_account_context()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $body$
        BEGIN
          IF TG_OP='UPDATE' THEN
            IF OLD.status IS NOT DISTINCT FROM NEW.status
               AND OLD.id IS NOT DISTINCT FROM NEW.id
               AND OLD.is_master IS NOT DISTINCT FROM NEW.is_master
            THEN RETURN NEW; END IF;
          END IF;
          UPDATE m40650.sessions SET context_generation=context_generation+1
           WHERE user_id=OLD.id;
          IF TG_OP='DELETE' THEN RETURN OLD; END IF;
          IF OLD.id IS DISTINCT FROM NEW.id THEN
            UPDATE m40650.sessions SET context_generation=context_generation+1
             WHERE user_id=NEW.id;
          END IF;
          RETURN NEW;
        END
        $body$
    """)
    owner.execute("""
        CREATE FUNCTION m41050.rotate_membership_context()
        RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp AS $body$
        BEGIN
          IF TG_OP='UPDATE' THEN
            IF OLD.status IS NOT DISTINCT FROM NEW.status
               AND ROW(OLD.user_id,OLD.tenant_id,OLD.role) IS NOT DISTINCT FROM
                   ROW(NEW.user_id,NEW.tenant_id,NEW.role)
            THEN RETURN NEW; END IF;
          END IF;
          IF TG_OP<>'INSERT' THEN
            UPDATE m40650.sessions SET context_generation=context_generation+1
             WHERE user_id=OLD.user_id AND active_tenant_id=OLD.tenant_id
               AND active_role=OLD.role;
          END IF;
          IF TG_OP='DELETE' THEN RETURN OLD; END IF;
          IF TG_OP='INSERT' THEN
            UPDATE m40650.sessions SET context_generation=context_generation+1
             WHERE user_id=NEW.user_id AND active_tenant_id=NEW.tenant_id
               AND active_role=NEW.role;
          ELSIF ROW(OLD.user_id,OLD.tenant_id,OLD.role) IS DISTINCT FROM
                ROW(NEW.user_id,NEW.tenant_id,NEW.role) THEN
            UPDATE m40650.sessions SET context_generation=context_generation+1
             WHERE user_id=NEW.user_id AND active_tenant_id=NEW.tenant_id
               AND active_role=NEW.role;
          END IF;
          RETURN NEW;
        END
        $body$
    """)
    for function in ("rotate_account_context", "rotate_membership_context"):
        owner.execute(f"ALTER FUNCTION m41050.{function}() OWNER TO m40650_owner")
        owner.execute(f"REVOKE ALL ON FUNCTION m41050.{function}() FROM PUBLIC,m40650_app,m40680_auth")
    owner.execute("""
        CREATE TRIGGER m41130_account_context
        AFTER UPDATE OR DELETE ON m40650.users FOR EACH ROW
        EXECUTE FUNCTION m41050.rotate_account_context()
    """)
    owner.execute("""
        CREATE TRIGGER m41130_membership_context
        AFTER INSERT OR UPDATE OR DELETE ON m40650.memberships FOR EACH ROW
        EXECUTE FUNCTION m41050.rotate_membership_context()
    """)
    owner.execute("REVOKE ALL ON ALL TABLES IN SCHEMA m41050 FROM PUBLIC")
    owner.execute(
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA m41050 FROM PUBLIC"
    )
    owner.execute(
        "GRANT SELECT ON m41050.protected_entries TO m40650_app"
    )
    owner.execute("""
        GRANT EXECUTE ON FUNCTION m41050.bind_ticket(text,uuid)
        TO m40650_app
    """)
    owner.execute("""
        GRANT EXECUTE ON FUNCTION m41050.current_claims()
        TO m40650_app
    """)
    owner.execute("""
        GRANT EXECUTE ON FUNCTION m41050.can_write_entry(uuid,uuid)
        TO m40650_app
    """)
    owner.execute("""
        GRANT INSERT ON m41050.protected_entries TO m40650_app
    """)


def insert_subject(owner, *, user_id, is_master=False) -> None:
    owner.execute(
        "INSERT INTO m40650.users(id,status,is_master) VALUES (%s,'ACTIVE',%s)",
        (user_id,is_master),
    )


def add_membership(owner, user_id, tenant_id, role) -> None:
    owner.execute(
        "INSERT INTO m40650.memberships(user_id,tenant_id,role,status) "
        "VALUES (%s,%s,%s,'ATIVA')",
        (user_id,tenant_id,role),
    )


def create_session(owner, user_id, role, tenant_id, *, expires_at=None):
    raw = secrets.token_urlsafe(40)
    digest = sha256(raw.encode("utf-8")).hexdigest()
    expiry = expires_at or datetime.now(timezone.utc)+timedelta(hours=1)
    owner.execute(
        "INSERT INTO m40650.sessions "
        "(token_digest,user_id,active_role,active_tenant_id,expires_at,revoked_at) "
        "VALUES (%s,%s,%s,%s,%s,NULL)",
        (digest,user_id,role,tenant_id,expiry),
    )
    return raw,digest


def connection_dsns(dsn: str) -> tuple[str,str]:
    from psycopg.conninfo import make_conninfo
    return (
        make_conninfo(
            dsn,user="m40680_auth_login",password=AUTH_PASSWORD
        ),
        make_conninfo(
            dsn,user="m40650_ci_login",password=APP_PASSWORD
        ),
    )


def fixture_context(owner, digest):
    # Trusted synthetic fixture lookup, not a production identity source.
    return owner.execute(
        "SELECT user_id,active_role,context_generation FROM m40650.sessions WHERE token_digest=%s",
        (digest,)
    ).fetchone()


def sign_context(key, digest, tenant, nonce, expiry, scope, context):
    user, role, generation = context
    message = (f"FRF-M41120|v2|{digest}|{tenant}|{nonce}|{expiry}|{scope}|"
               f"{user}|{role}|{generation}").encode("utf-8")
    return hmac.new(key, message, sha256).hexdigest()


def issue_ticket(owner, auth_dsn: str, key: bytes, session_digest: str,
                 tenant_id, *, nonce=None, expiry=None, scope: str = SCOPE,
                 context=None, proof=None) -> str | None:
    import psycopg
    nonce = nonce or uuid4()
    expiry = expiry if expiry is not None else int(datetime.now(timezone.utc).timestamp())+15
    context = context if context is not None else fixture_context(owner, session_digest)
    if context is None:
        return None
    user, role, generation = context
    proof = proof if proof is not None else sign_context(
        key,session_digest,tenant_id,nonce,expiry,scope,context
    )
    with psycopg.connect(auth_dsn,autocommit=True) as auth:
        auth.execute("SET ROLE m40680_auth")
        return auth.execute(
            "SELECT m40700.issue_bound_v2(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (session_digest,tenant_id,nonce,expiry,scope,user,role,generation,proof),
        ).fetchone()[0]


def bind_ticket(app_dsn: str, ticket: str, tenant_id) -> str | None:
    import psycopg
    with psycopg.connect(app_dsn,autocommit=True) as app:
        app.execute("SET ROLE m40650_app")
        return app.execute(
            "SELECT m41050.bind_ticket(%s,%s)",(ticket,tenant_id)
        ).fetchone()[0]


def insert_entry(app_dsn: str, capability: str, tenant_id, member_id,
                 amount_cents: int, idempotency_key: str,
                 *, forged: tuple[str,str,str] | None = None,
                 verify_authorized: bool = False) -> int:
    import psycopg
    with psycopg.connect(app_dsn,autocommit=False) as app:
        app.execute("SET ROLE m40650_app")
        app.execute(
            "SELECT pg_catalog.set_config('app.session_capability',%s,true)",
            (capability,),
        )
        if forged is not None:
            role,user_id,claimed_tenant=forged
            for key,value in (
                ("app.current_role",role),
                ("app.current_user_id",user_id),
                ("app.current_tenant_id",claimed_tenant),
            ):
                app.execute(
                    "SELECT pg_catalog.set_config(%s,%s,true)",(key,value)
                )
        if verify_authorized:
            allowed=app.execute(
                "SELECT m41050.can_write_entry(%s,%s)",
                (tenant_id,member_id),
            ).fetchone()[0]
            assert allowed is True
            print("M41060_SAME_CONNECTION_WRITE_SCOPE=PASS")
        app.execute("SAVEPOINT idempotency_attempt")
        try:
            result=app.execute(
                "INSERT INTO m41050.protected_entries "
                "(entry_id,tenant_id,member_id,amount_cents,idempotency_key) "
                "VALUES (%s,%s,%s,%s,%s)",
                (uuid4(),tenant_id,member_id,amount_cents,idempotency_key),
            )
        except psycopg.errors.UniqueViolation:
            app.execute("ROLLBACK TO SAVEPOINT idempotency_attempt")
            app.execute("RELEASE SAVEPOINT idempotency_attempt")
            app.commit()
            return 0
        app.execute("RELEASE SAVEPOINT idempotency_attempt")
        row_count=result.rowcount
        app.commit()
        return row_count



def _m41080_validate_disposable_dsn(dsn: str):
    expected = {
        "GITHUB_ACTIONS": "true",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "CI_M41080_DISPOSABLE": "1",
        "CI_M41090_DISPOSABLE": "1",
        "CI_M41100_DISPOSABLE": "1",
        "CI_M41140_DISPOSABLE": "1",
        "CI_M41050_DISPOSABLE": "1",
        "CI_M41060_DISPOSABLE": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("M41080_DISPOSABLE_ONLY")
    try:
        parsed = urlsplit(dsn)
        valid = (
            parsed.scheme == "postgresql"
            and parsed.hostname == "127.0.0.1"
            and parsed.port == PORT
            and parsed.path == "/" + DATABASE
            and parsed.username == "postgres"
            and parsed.password == DATABASE_PASSWORD
            and not parsed.query
            and not parsed.fragment
            and os.environ.get("CI_M41050_DATABASE_URL") == dsn
            and os.environ.get("CI_M41080_DATABASE_URL") == dsn
            and os.environ.get("CI_M41090_DATABASE_URL") == dsn
            and os.environ.get("CI_M41100_DATABASE_URL") == dsn
            and os.environ.get("CI_M41140_DATABASE_URL") == dsn
        )
    except (ValueError, AttributeError, TypeError):
        valid = False
    if not valid:
        raise RuntimeError("M41080_DISPOSABLE_DATABASE_IDENTITY_DENIED")
    return parsed


async def _m41080_asyncpg_connect(dsn: str):
    parsed = _m41080_validate_disposable_dsn(dsn)
    import asyncpg
    return await asyncpg.connect(
        host=parsed.hostname,
        port=parsed.port,
        database=DATABASE,
        user="m40650_ci_login",
        password=APP_PASSWORD,
        timeout=5,
        command_timeout=5,
    )


async def _m41080_set_forged_gucs(connection, forged) -> None:
    role, user_id, tenant_id = forged
    for key, value in (
        ("app.current_role", role),
        ("app.current_user_id", user_id),
        ("app.current_tenant_id", tenant_id),
    ):
        await connection.fetchval(
            "SELECT pg_catalog.set_config($1, $2, true)", key, value
        )


async def _m41080_asyncpg_visible_entries(
    dsn: str, capability: str, *, forged=None
) -> list[tuple]:
    connection = await _m41080_asyncpg_connect(dsn)
    try:
        async with connection.transaction():
            await connection.execute("SET LOCAL ROLE m40650_app")
            await install_session_capability(connection, capability)
            if forged is not None:
                await _m41080_set_forged_gucs(connection, forged)
            context = await connection.fetchrow(
                "SELECT current_user::text AS effective_role, "
                "session_user::text AS login_role, "
                "count(*)::int AS claim_count, "
                "min(role_name) AS claim_role, min(scope_name) AS claim_scope "
                "FROM m41050.current_claims()"
            )
            print(
                "M41080_ASYNCPG_CONTEXT="
                + ":".join(
                    str(context[key] or "-")
                    for key in (
                        "effective_role", "login_role", "claim_count",
                        "claim_role", "claim_scope",
                    )
                )
            )
            rows = await connection.fetch(
                "SELECT tenant_id, member_id, amount_cents "
                "FROM m41050.protected_entries "
                "ORDER BY tenant_id, member_id, amount_cents, entry_id"
            )
            visible = [
                (row["tenant_id"], row["member_id"], row["amount_cents"])
                for row in rows
            ]
        reset_value = await connection.fetchval(
            "SELECT pg_catalog.current_setting("
            "'app.session_capability', true)"
        )
        reset_ok = reset_value in (None, "")
        print("M41080_ASYNCPG_TRANSACTION_LOCAL_RESET="+("PASS" if reset_ok else "FAIL"))
        assert reset_ok, "M41080_ASYNCPG_TRANSACTION_LOCAL_RESET"
        print("M41080_ASYNCPG_VISIBLE_ROWS="+str(len(visible)))
        return visible
    finally:
        await connection.close()


async def _m41080_asyncpg_insert_entry(
    dsn: str,
    capability: str,
    tenant_id,
    member_id,
    amount_cents: int,
    idempotency_key: str,
    *,
    forged=None,
) -> str:
    connection = await _m41080_asyncpg_connect(dsn)
    import asyncpg
    try:
        try:
            async with connection.transaction():
                await connection.execute("SET LOCAL ROLE m40650_app")
                await install_session_capability(connection, capability)
                if forged is not None:
                    await _m41080_set_forged_gucs(connection, forged)
                status = await connection.execute(
                    "INSERT INTO m41050.protected_entries "
                    "(entry_id, tenant_id, member_id, amount_cents, idempotency_key) "
                    "VALUES ($1, $2, $3, $4, $5)",
                    uuid4(), tenant_id, member_id, amount_cents, idempotency_key,
                )
                assert status == "INSERT 0 1", "M41080_ASYNCPG_INSERT_STATUS"
        except asyncpg.PostgresError as exc:
            if exc.sqlstate == "42501":
                return "DENIED"
            if exc.sqlstate == "23505":
                return "DUPLICATE"
            raise
        return "INSERTED"
    finally:
        await connection.close()


async def _m41090_create_asyncpg_pool(dsn: str):
    parsed = _m41080_validate_disposable_dsn(dsn)
    import asyncpg
    return await asyncpg.create_pool(
        host=parsed.hostname,
        port=parsed.port,
        database=DATABASE,
        user="m40650_ci_login",
        password=APP_PASSWORD,
        min_size=1,
        max_size=1,
        timeout=5,
        command_timeout=5,
    )


async def _m41090_assert_pool_clean(connection, expected_pid: int) -> None:
    state = await connection.fetchrow(
        "SELECT pg_backend_pid() AS backend_pid, "
        "current_user::text AS effective_role, "
        "session_user::text AS login_role, "
        "pg_catalog.current_setting('app.session_capability', true) AS capability, "
        "pg_catalog.current_setting('app.current_role', true) AS legacy_role, "
        "pg_catalog.current_setting('app.current_user_id', true) AS legacy_user, "
        "pg_catalog.current_setting('app.current_tenant_id', true) AS legacy_tenant"
    )
    assert state["backend_pid"] == expected_pid, "M41090_ASYNCPG_POOL_BACKEND_CHANGED"
    assert state["effective_role"] == "m40650_ci_login", "M41090_ASYNCPG_POOL_ROLE_LEAK"
    assert state["login_role"] == "m40650_ci_login", "M41090_ASYNCPG_POOL_LOGIN_CHANGED"
    assert all(
        state[key] in (None, "")
        for key in ("capability", "legacy_role", "legacy_user", "legacy_tenant")
    ), "M41090_ASYNCPG_POOL_CONTEXT_LEAK"

    async with connection.transaction():
        await connection.execute("SET LOCAL ROLE m40650_app")
        claim_count = await connection.fetchval(
            "SELECT count(*) FROM m41050.current_claims()"
        )
        rows = await connection.fetch(
            "SELECT tenant_id, member_id, amount_cents "
            "FROM m41050.protected_entries "
            "ORDER BY tenant_id, member_id, amount_cents, entry_id"
        )
    assert claim_count == 0, "M41090_ASYNCPG_POOL_STALE_CLAIMS"
    assert rows == [], "M41090_ASYNCPG_POOL_STALE_RLS_ROWS"


async def _m41090_exercise_asyncpg_pool(
    dsn: str,
    capability: str,
    expected_rows: list[tuple],
    forged: tuple[str, str, str],
) -> None:
    pool = await _m41090_create_asyncpg_pool(dsn)
    backend_pid = None

    class _ExpectedRollback(Exception):
        pass

    try:
        async with pool.acquire() as connection:
            backend_pid = await connection.fetchval("SELECT pg_backend_pid()")
            async with connection.transaction():
                await connection.execute("SET LOCAL ROLE m40650_app")
                await install_session_capability(connection, capability)
                await _m41080_set_forged_gucs(connection, forged)
                rows = await connection.fetch(
                    "SELECT tenant_id, member_id, amount_cents "
                    "FROM m41050.protected_entries "
                    "ORDER BY tenant_id, member_id, amount_cents, entry_id"
                )
                visible = [
                    (row["tenant_id"], row["member_id"], row["amount_cents"])
                    for row in rows
                ]
                assert visible == expected_rows, "M41090_ASYNCPG_POOL_VALID_SCOPE"
            await _m41090_assert_pool_clean(connection, backend_pid)
            print("M41090_ASYNCPG_POOL_COMMIT_TRANSACTION_RESET=PASS")

        async with pool.acquire() as connection:
            await _m41090_assert_pool_clean(connection, backend_pid)
            print("M41090_ASYNCPG_POOL_COMMIT_REACQUIRE_RESET=PASS")

        async with pool.acquire() as connection:
            assert await connection.fetchval("SELECT pg_backend_pid()") == backend_pid
            try:
                async with connection.transaction():
                    await connection.execute("SET LOCAL ROLE m40650_app")
                    await install_session_capability(connection, capability)
                    await _m41080_set_forged_gucs(connection, forged)
                    rows = await connection.fetch(
                        "SELECT tenant_id, member_id, amount_cents "
                        "FROM m41050.protected_entries "
                        "ORDER BY tenant_id, member_id, amount_cents, entry_id"
                    )
                    visible = [
                        (row["tenant_id"], row["member_id"], row["amount_cents"])
                        for row in rows
                    ]
                    assert visible == expected_rows, "M41090_ASYNCPG_POOL_ROLLBACK_SCOPE"
                    raise _ExpectedRollback()
            except _ExpectedRollback:
                pass
            await _m41090_assert_pool_clean(connection, backend_pid)
            print("M41090_ASYNCPG_POOL_ROLLBACK_TRANSACTION_RESET=PASS")

        async with pool.acquire() as connection:
            await _m41090_assert_pool_clean(connection, backend_pid)
            print("M41090_ASYNCPG_POOL_ROLLBACK_REACQUIRE_RESET=PASS")
        print("M41090_ASYNCPG_POOL_REUSED_SAME_BACKEND=PASS")
    finally:
        await pool.close()



async def _m41100_exercise_revoke_between_pool_borrows(
    dsn: str,
    capability: str,
    token_digest: str,
    tenant_id,
    member_id,
    forged: tuple[str, str, str],
) -> None:
    pool = await _m41090_create_asyncpg_pool(dsn)
    backend_pid = None
    try:
        async with pool.acquire() as connection:
            backend_pid = await connection.fetchval("SELECT pg_backend_pid()")
            async with connection.transaction():
                await connection.execute("SET LOCAL ROLE m40650_app")
                await install_session_capability(connection, capability)
                await _m41080_set_forged_gucs(connection, forged)
                claims = await connection.fetch(
                    "SELECT user_id, role_name, tenant_id, scope_name "
                    "FROM m41050.current_claims()"
                )
                claim_values = [
                    (row["user_id"], row["role_name"], row["tenant_id"], row["scope_name"])
                    for row in claims
                ]
                assert claim_values == [
                    (member_id, "TENANT_MEMBER", tenant_id, "READ_ENTRIES")
                ], "M41100_ASYNCPG_ACTIVE_SESSION_CLAIM"
                rows = await connection.fetch(
                    "SELECT tenant_id, member_id, amount_cents "
                    "FROM m41050.protected_entries "
                    "ORDER BY tenant_id, member_id, amount_cents, entry_id"
                )
                visible = [
                    (row["tenant_id"], row["member_id"], row["amount_cents"])
                    for row in rows
                ]
                assert visible == [(tenant_id, member_id, 300000)], (
                    "M41100_ASYNCPG_ACTIVE_SESSION_RLS"
                )
            await _m41090_assert_pool_clean(connection, backend_pid)
            print("M41100_ASYNCPG_ACTIVE_BEFORE_REVOKE=PASS")

        with connect(dsn, autocommit=True) as owner:
            updated = owner.execute(
                "UPDATE m40650.sessions "
                "SET revoked_at=pg_catalog.clock_timestamp() "
                "WHERE token_digest=%s AND revoked_at IS NULL",
                (token_digest,),
            )
            assert updated.rowcount == 1, "M41100_ASYNCPG_FIXTURE_REVOKE"
        print("M41100_ASYNCPG_FIXTURE_SESSION_REVOKED=PASS")

        async with pool.acquire() as connection:
            assert await connection.fetchval("SELECT pg_backend_pid()") == backend_pid, (
                "M41100_ASYNCPG_REBORROW_CHANGED_BACKEND"
            )
            async with connection.transaction():
                await connection.execute("SET LOCAL ROLE m40650_app")
                await install_session_capability(connection, capability)
                await _m41080_set_forged_gucs(connection, forged)
                claim_count = await connection.fetchval(
                    "SELECT count(*) FROM m41050.current_claims()"
                )
                rows = await connection.fetch(
                    "SELECT tenant_id, member_id, amount_cents "
                    "FROM m41050.protected_entries "
                    "ORDER BY tenant_id, member_id, amount_cents, entry_id"
                )
            assert claim_count == 0, "M41100_ASYNCPG_REVOKED_CLAIMS_REMAIN"
            assert rows == [], "M41100_ASYNCPG_REVOKED_RLS_ROWS_REMAIN"
            await _m41090_assert_pool_clean(connection, backend_pid)
            print("M41100_ASYNCPG_REVOKED_REBORROW=DENIED")
        print("M41100_ASYNCPG_REVOKED_SAME_BACKEND=PASS")
    finally:
        await pool.close()



async def _m41110_switch_role_with_open_transaction(
    dsn: str, capability: str, digest: str, tenant_id, user_id
) -> None:
    # READ COMMITTED: each statement sees the committed role change.
    pool = await _m41090_create_asyncpg_pool(dsn)
    try:
        async with pool.acquire() as connection:
            pid = await connection.fetchval("SELECT pg_backend_pid()")
            async with connection.transaction(isolation="read_committed"):
                await connection.execute("SET LOCAL ROLE m40650_app")
                await install_session_capability(connection, capability)
                claims = await connection.fetch(
                    "SELECT user_id,role_name,tenant_id,scope_name "
                    "FROM m41050.current_claims()"
                )
                assert [tuple(row) for row in claims] == [
                    (user_id, "TENANT_MEMBER", tenant_id, SCOPE)
                ], "M41110_ASYNCPG_INITIAL_CLAIM"
                before = await connection.fetch(
                    "SELECT member_id FROM m41050.protected_entries"
                )
                assert before and all(row["member_id"] == user_id for row in before)
                with connect(dsn, autocommit=True) as owner:
                    changed = owner.execute(
                        "UPDATE m40650.sessions SET active_role='TENANT_ADMIN' "
                        "WHERE token_digest=%s AND active_role='TENANT_MEMBER'",
                        (digest,),
                    )
                    assert changed.rowcount == 1
                assert await connection.fetchval(
                    "SELECT count(*) FROM m41050.current_claims()"
                ) == 0, "M41110_ASYNCPG_ROLE_DRIFT_CLAIMS"
                assert await connection.fetch(
                    "SELECT member_id FROM m41050.protected_entries"
                ) == [], "M41110_ASYNCPG_ROLE_DRIFT_ROWS"
                print("M41110_ASYNCPG_ROLE_SWITCH_OPEN_TRANSACTION=DENIED")
            await _m41090_assert_pool_clean(connection, pid)
        async with pool.acquire() as connection:
            await _m41090_assert_pool_clean(connection, pid)
            async with connection.transaction():
                await connection.execute("SET LOCAL ROLE m40650_app")
                await install_session_capability(connection, capability)
                assert await connection.fetchval(
                    "SELECT count(*) FROM m41050.current_claims()"
                ) == 0, "M41110_ASYNCPG_ROLE_DRIFT_REBORROW"
            print("M41110_ASYNCPG_ROLE_SWITCH_REBORROW=DENIED")
    finally:
        await pool.close()


def _m41110_exercise_role_binding(owner, dsn, auth_dsn, app_dsn, key,
                                 tenant_id, member_id, other_member_id):
    # A legitimately dual-role identity, not an app-supplied GUC.
    add_membership(owner, member_id, tenant_id, "TENANT_ADMIN")
    _, digest = create_session(owner, member_id, "TENANT_MEMBER", tenant_id)

    def new_cap(scope=SCOPE):
        ticket = issue_ticket(owner, auth_dsn, key, digest, tenant_id, scope=scope)
        assert ticket is not None
        cap = bind_ticket(app_dsn, ticket, tenant_id)
        assert cap is not None
        return cap

    def assert_revoked(cap):
        row = owner.execute(
            "SELECT revoked_at IS NOT NULL FROM m41050.session_caps "
            "WHERE token_hash=pg_catalog.sha256(pg_catalog.convert_to(%s,'UTF8'))",
            (cap,),
        ).fetchone()
        assert row == (True,), "M41110_CAPABILITY_NOT_PERSISTENTLY_REVOKED"

    member_read = new_cap()
    member_write = new_cap(WRITE_SCOPE)
    asyncio.run(_m41110_switch_role_with_open_transaction(
        dsn, member_read, digest, tenant_id, member_id
    ))
    assert_revoked(member_read)
    assert_revoked(member_write)
    expect_insert_denied(
        app_dsn, member_write, tenant_id, other_member_id, 15000,
        "m41110:member-old:" + uuid4().hex,
    )
    print("M41110_MEMBER_OLD_WRITE_AFTER_PROMOTION=DENIED")

    admin_read = new_cap()
    admin_write = new_cap(WRITE_SCOPE)
    assert any(row[1] == other_member_id for row in visible_entries(
        app_dsn, capability=admin_read
    )), "M41110_FRESH_ADMIN_READ"
    assert insert_entry(
        app_dsn, admin_write, tenant_id, other_member_id, 15000,
        "m41110:admin-fresh:" + uuid4().hex, verify_authorized=True,
    ) == 1
    print("M41110_FRESH_ADMIN_SCOPES=PASS")

    changed = owner.execute(
        "UPDATE m40650.sessions SET active_role='TENANT_MEMBER' "
        "WHERE token_digest=%s AND active_role='TENANT_ADMIN'", (digest,),
    )
    assert changed.rowcount == 1
    assert_revoked(admin_read)
    assert_revoked(admin_write)
    assert visible_entries(app_dsn, capability=member_read) == []
    assert visible_entries(app_dsn, capability=admin_read) == []
    fresh_member = new_cap()
    own = visible_entries(app_dsn, capability=fresh_member)
    assert own and all(row[1] == member_id for row in own)
    print("M41110_RETURN_TO_MEMBER_OLD_CAPS=DENIED")
    print("M41110_FRESH_MEMBER_SCOPE=PASS")

    changed = owner.execute(
        "UPDATE m40650.sessions SET active_role='TENANT_ADMIN' "
        "WHERE token_digest=%s AND active_role='TENANT_MEMBER'", (digest,),
    )
    assert changed.rowcount == 1
    assert_revoked(fresh_member)
    expect_insert_denied(
        app_dsn, admin_write, tenant_id, other_member_id, 15000,
        "m41110:admin-old:" + uuid4().hex,
    )
    assert visible_entries(app_dsn, capability=admin_read) == []
    print("M41110_RETURN_TO_ADMIN_OLD_CAPS=DENIED")


def _m41120_exercise_ticket_context(owner, auth_dsn, app_dsn, key,
                                   tenant_id, member_id, other_member):
    _, digest = create_session(owner, member_id, "TENANT_MEMBER", tenant_id)
    original = fixture_context(owner,digest)
    nonce = uuid4()
    expiry = int(datetime.now(timezone.utc).timestamp())+15
    proof = sign_context(key,digest,tenant_id,nonce,expiry,SCOPE,original)
    for context,scope in (
        ((original[0],"TENANT_ADMIN",original[2]),SCOPE),
        ((other_member,original[1],original[2]),SCOPE),
        (original,WRITE_SCOPE),
        ((original[0],original[1],original[2]+1),SCOPE),
    ):
        assert issue_ticket(owner,auth_dsn,key,digest,tenant_id,nonce=nonce,
                            expiry=expiry,context=context,proof=proof,scope=scope) is None
    valid = issue_ticket(owner,auth_dsn,key,digest,tenant_id,nonce=nonce,
                         expiry=expiry,context=original,proof=proof)
    assert valid
    assert issue_ticket(owner,auth_dsn,key,digest,tenant_id,nonce=nonce,
                        expiry=expiry,context=original,proof=proof) is None
    cap = bind_ticket(app_dsn,valid,tenant_id)
    assert cap and visible_entries(app_dsn,capability=cap)
    print("M41120_SIGNED_CONTEXT_TAMPER_AND_NONCE=PASS")
    old_read = issue_ticket(owner,auth_dsn,key,digest,tenant_id)
    old_write = issue_ticket(owner,auth_dsn,key,digest,tenant_id,scope=WRITE_SCOPE)
    assert old_read and old_write
    stale_nonce = uuid4()
    stale_proof = sign_context(key,digest,tenant_id,stale_nonce,expiry,SCOPE,original)

    def switch(role):
        assert owner.execute(
            "UPDATE m40650.sessions SET active_role=%s WHERE token_digest=%s",
            (role,digest)
        ).rowcount == 1

    switch("TENANT_ADMIN")
    assert fixture_context(owner,digest)[2] == original[2]+1
    assert bind_ticket(app_dsn,old_read,tenant_id) is None
    assert issue_ticket(owner,auth_dsn,key,digest,tenant_id,nonce=stale_nonce,
                        expiry=expiry,context=original,proof=stale_proof) is None
    admin_ticket = issue_ticket(owner,auth_dsn,key,digest,tenant_id)
    assert admin_ticket
    admin_cap = bind_ticket(app_dsn,admin_ticket,tenant_id)
    assert admin_cap and any(row[1]==other_member for row in visible_entries(app_dsn,capability=admin_cap))
    print("M41120_ISSUED_MEMBER_TICKET_AFTER_SWITCH=DENIED")
    switch("TENANT_MEMBER")
    assert fixture_context(owner,digest)[2]==original[2]+2
    assert bind_ticket(app_dsn,old_write,tenant_id) is None
    assert issue_ticket(owner,auth_dsn,key,digest,tenant_id,nonce=stale_nonce,
                        expiry=expiry,context=original,proof=stale_proof) is None
    assert visible_entries(app_dsn,capability=admin_cap)==[]
    fresh = issue_ticket(owner,auth_dsn,key,digest,tenant_id)
    assert fresh
    fresh_cap = bind_ticket(app_dsn,fresh,tenant_id)
    assert fresh_cap
    rows = visible_entries(app_dsn,capability=fresh_cap)
    assert rows and all(row[1]==member_id for row in rows)
    print("M41120_RETURN_TO_ORIGINAL_ROLE_OLD_TICKET=DENIED")
    print("M41120_FRESH_CONTEXT=PASS")


def _m41130_exercise_lifecycle(owner, auth_dsn, app_dsn, key,
                              tenant_a, tenant_b, member, admin, other_member):
    _, digest_a = create_session(owner,member,"TENANT_MEMBER",tenant_a)
    _, digest_b = create_session(owner,member,"TENANT_MEMBER",tenant_b)
    _, digest_admin = create_session(owner,admin,"TENANT_ADMIN",tenant_a)

    def generation(digest):
        return fixture_context(owner,digest)[2]

    def issue(digest,tenant,scope=SCOPE):
        ticket=issue_ticket(owner,auth_dsn,key,digest,tenant,scope=scope)
        assert ticket is not None, "M41130_FRESH_TICKET"
        return ticket

    def capability(digest,tenant,scope=SCOPE):
        cap=bind_ticket(app_dsn,issue(digest,tenant,scope),tenant)
        assert cap is not None, "M41130_FRESH_CAPABILITY"
        return cap

    def membership(status):
        assert owner.execute(
            "UPDATE m40650.memberships SET status=%s "
            "WHERE user_id=%s AND tenant_id=%s AND role='TENANT_MEMBER'",
            (status,member,tenant_a),
        ).rowcount==1

    a0,b0=generation(digest_a),generation(digest_b)
    cap_a=capability(digest_a,tenant_a)
    cap_b=capability(digest_b,tenant_b)
    ticket_a=issue(digest_a,tenant_a)
    original=fixture_context(owner,digest_a)
    membership("ATIVA")
    assert generation(digest_a)==a0, "M41130_NOOP_GENERATION"
    # Rollback must restore both lifecycle and authorization state atomically.
    class ExpectedRollback(Exception):
        pass
    try:
        with owner.transaction():
            membership("DESLIGADA")
            assert generation(digest_a)==a0+1
            raise ExpectedRollback()
    except ExpectedRollback:
        pass
    assert generation(digest_a)==a0
    assert visible_entries(app_dsn,capability=cap_a)
    print("M41130_LIFECYCLE_ROLLBACK=PASS")
    membership("DESLIGADA")
    assert generation(digest_a)==a0+1 and generation(digest_b)==b0
    assert visible_entries(app_dsn,capability=cap_a)==[]
    assert bind_ticket(app_dsn,ticket_a,tenant_a) is None
    assert issue_ticket(owner,auth_dsn,key,digest_a,tenant_a) is None
    # Verify the unaffected tenant using claims, even if it has no own entries.
    assert write_authorization_state(
        app_dsn,cap_b,tenant_b,member
    )[0]==[(member,"TENANT_MEMBER",tenant_b,SCOPE)]
    print("M41130_MEMBERSHIP_SUSPENSION_ISOLATED=PASS")
    membership("ATIVA")
    assert generation(digest_a)==a0+2
    assert visible_entries(app_dsn,capability=cap_a)==[]
    assert issue_ticket(owner,auth_dsn,key,digest_a,tenant_a,context=original) is None
    assert visible_entries(app_dsn,capability=capability(digest_a,tenant_a))
    print("M41130_MEMBERSHIP_REACTIVATION_OLD_CAP=DENIED")

    old_ticket=issue(digest_a,tenant_a)
    old_cap=capability(digest_a,tenant_a)
    assert owner.execute(
        "DELETE FROM m40650.memberships WHERE user_id=%s AND tenant_id=%s "
        "AND role='TENANT_MEMBER'",(member,tenant_a),
    ).rowcount==1
    add_membership(owner,member,tenant_a,"TENANT_MEMBER")
    assert bind_ticket(app_dsn,old_ticket,tenant_a) is None
    assert visible_entries(app_dsn,capability=old_cap)==[]
    print("M41130_MEMBERSHIP_RECREATE_OLD_PROOFS=DENIED")

    cap_a=capability(digest_a,tenant_a)
    cap_b=capability(digest_b,tenant_b)
    ticket_b=issue(digest_b,tenant_b)
    a0,b0=generation(digest_a),generation(digest_b)
    assert owner.execute("UPDATE m40650.users SET status='SUSPENDED' WHERE id=%s",
                         (member,)).rowcount==1
    assert generation(digest_a)==a0+1 and generation(digest_b)==b0+1
    assert visible_entries(app_dsn,capability=cap_a)==[]
    assert write_authorization_state(app_dsn,cap_b,tenant_b,member)[0]==[]
    assert issue_ticket(owner,auth_dsn,key,digest_b,tenant_b) is None
    assert owner.execute("UPDATE m40650.users SET status='ACTIVE' WHERE id=%s",
                         (member,)).rowcount==1
    assert bind_ticket(app_dsn,ticket_b,tenant_b) is None
    assert visible_entries(app_dsn,capability=cap_a)==[]
    assert write_authorization_state(app_dsn,cap_b,tenant_b,member)[0]==[]
    assert visible_entries(app_dsn,capability=capability(digest_a,tenant_a))
    print("M41130_ACCOUNT_REACTIVATION_OLD_PROOFS=DENIED")

    old_write=capability(digest_admin,tenant_a,WRITE_SCOPE)
    old_ticket=issue(digest_admin,tenant_a,WRITE_SCOPE)
    assert owner.execute("UPDATE m40650.users SET status='SUSPENDED' WHERE id=%s",
                         (admin,)).rowcount==1
    expect_insert_denied(app_dsn,old_write,tenant_a,other_member,15000,
                         "m41130:suspended:"+uuid4().hex)
    assert owner.execute("UPDATE m40650.users SET status='ACTIVE' WHERE id=%s",
                         (admin,)).rowcount==1
    assert bind_ticket(app_dsn,old_ticket,tenant_a) is None
    expect_insert_denied(app_dsn,old_write,tenant_a,other_member,15000,
                         "m41130:old:"+uuid4().hex)
    new_write=capability(digest_admin,tenant_a,WRITE_SCOPE)
    assert insert_entry(app_dsn,new_write,tenant_a,other_member,15000,
                        "m41130:fresh:"+uuid4().hex,verify_authorized=True)==1
    print("M41130_ADMIN_OLD_WRITE_DENIED_FRESH_WRITE=PASS")


def expect_insert_denied(app_dsn: str, *args, **kwargs) -> None:
    import psycopg
    try:
        insert_entry(app_dsn,*args,**kwargs)
    except psycopg.errors.InsufficientPrivilege:
        return
    except psycopg.Error as exc:
        if exc.sqlstate!="42501":
            raise
        return
    raise AssertionError("M41060_EXPECTED_RLS_WRITE_DENIAL")


def write_authorization_state(app_dsn: str, capability: str,
                            tenant_id, member_id,
                            *, forged: tuple[str,str,str] | None = None
                            ) -> tuple[list[tuple], bool]:
    import psycopg
    with psycopg.connect(app_dsn,autocommit=False) as app:
        app.execute("SET ROLE m40650_app")
        app.execute(
            "SELECT pg_catalog.set_config('app.session_capability',%s,true)",
            (capability,),
        )
        if forged is not None:
            role,user_id,claimed_tenant=forged
            for key,value in (
                ("app.current_role",role),
                ("app.current_user_id",user_id),
                ("app.current_tenant_id",claimed_tenant),
            ):
                app.execute(
                    "SELECT pg_catalog.set_config(%s,%s,true)",(key,value)
                )
        claims=app.execute(
            "SELECT user_id,role_name,tenant_id,scope_name "
            "FROM m41050.current_claims()"
        ).fetchall()
        allowed=app.execute(
            "SELECT m41050.can_write_entry(%s,%s)",(tenant_id,member_id)
        ).fetchone()[0]
        app.commit()
        return claims,allowed


def visible_entries(app_dsn: str, *, capability: str | None = None,
                    forged: tuple[str,str,str] | None = None) -> list[tuple]:
    import psycopg
    with psycopg.connect(app_dsn,autocommit=False) as app:
        app.execute("SET ROLE m40650_app")
        if capability is not None:
            app.execute(
                "SELECT pg_catalog.set_config('app.session_capability',%s,true)",
                (capability,),
            )
        if forged is not None:
            role,user_id,tenant_id=forged
            for key,value in (
                ("app.current_role",role),
                ("app.current_user_id",user_id),
                ("app.current_tenant_id",tenant_id),
            ):
                app.execute(
                    "SELECT pg_catalog.set_config(%s,%s,true)",(key,value)
                )
        return app.execute(
            "SELECT tenant_id,member_id,amount_cents "
            "FROM m41050.protected_entries ORDER BY tenant_id,member_id"
        ).fetchall()


def assert_acl(owner) -> None:
    app_role="m40650_app"
    assert not owner.execute(
        "SELECT has_table_privilege(%s,'m41050.session_caps','SELECT')",
        (app_role,),
    ).fetchone()[0]
    assert owner.execute(
        "SELECT has_function_privilege(%s,'m41050.bind_ticket(text,uuid)','EXECUTE')",
        (app_role,),
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_schema_privilege(%s,'m40700','USAGE')",(app_role,)
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_function_privilege("
        "'m40650_app',p.oid,'EXECUTE') "
        "FROM pg_catalog.pg_proc p "
        "JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace "
        "WHERE n.nspname='m40700' AND p.proname='issue_bound'"
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_table_privilege('m40650_app',c.oid,'SELECT') "
        "FROM pg_catalog.pg_class c "
        "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='m41050' AND c.relname='session_caps'"
    ).fetchone()[0]
    rls=owner.execute(
        "SELECT relrowsecurity,relforcerowsecurity "
        "FROM pg_catalog.pg_class WHERE oid='m41050.protected_entries'::regclass"
    ).fetchone()
    assert rls==(True,True)
    assert owner.execute(
        "SELECT has_table_privilege(%s,'m41050.protected_entries','SELECT')",
        (app_role,),
    ).fetchone()[0]
    assert owner.execute(
        "SELECT has_table_privilege(%s,'m41050.protected_entries','INSERT')",
        (app_role,),
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_table_privilege(%s,'m41050.protected_entries','UPDATE')",
        (app_role,),
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_table_privilege(%s,'m41050.protected_entries','DELETE')",
        (app_role,),
    ).fetchone()[0]
    policy_commands={
        row[0] for row in owner.execute(
            "SELECT cmd FROM pg_catalog.pg_policies "
            "WHERE schemaname='m41050' AND tablename='protected_entries'"
        ).fetchall()
    }
    assert policy_commands=={"SELECT","INSERT"}
    assert owner.execute(
        "SELECT has_function_privilege(%s,'m41050.can_write_entry(uuid,uuid)','EXECUTE')",
        (app_role,),
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_table_privilege(%s,'m40700.ticket_scopes','SELECT')",
        (app_role,),
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_function_privilege(%s,"
        "'m41050.invalidate_changed_session_caps()','EXECUTE')",
        (app_role,),
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_table_privilege(%s,'m41050.session_caps','UPDATE')",
        (app_role,),
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_function_privilege('m40680_auth','m40700.issue_bound(text,uuid,uuid,bigint,text,text)','EXECUTE')"
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_function_privilege('m40650_app','m40650.m40680_consume(text,uuid)','EXECUTE')"
    ).fetchone()[0]
    assert owner.execute(
        "SELECT has_function_privilege('m40680_auth','m40700.issue_bound_v2(text,uuid,uuid,bigint,text,uuid,text,bigint,text)','EXECUTE')"
    ).fetchone()[0]
    for role in ("m40650_app","m40680_auth"):
        for privilege in ("SELECT","INSERT","UPDATE","DELETE"):
            assert not owner.execute(
                "SELECT has_table_privilege(%s,'m40700.ticket_context',%s)",
                (role,privilege),
            ).fetchone()[0]
    for role in ("m40650_app","m40680_auth"):
        for function in ("rotate_account_context","rotate_membership_context"):
            assert not owner.execute(
                "SELECT has_function_privilege(%s,%s,'EXECUTE')",
                (role,"m41050."+function+"()"),
            ).fetchone()[0]
        for table in ("sessions","users","memberships"):
            for privilege in ("INSERT","UPDATE","DELETE"):
                assert not owner.execute(
                    "SELECT has_table_privilege(%s,%s,%s)",
                    (role,"m40650."+table,privilege),
                ).fetchone()[0]
    print("M41130_LIFECYCLE_ACL=PASS")
    print("M41120_LEGACY_PATH_AND_CONTEXT_ACL=PASS")
    print("M41110_INVALIDATION_ACL=PASS")
    print("M41050_APP_CANNOT_READ_CAPABILITY_STORE_OR_ISSUER=PASS")
    print("M41050_RLS_FORCE_AND_SCOPED_EXECUTE=PASS")
    print("M41060_APPEND_ONLY_SELECT_INSERT_ACL=PASS")
    print("M41060_WRITE_RLS_POLICY_PRESENT=PASS")


def _m41140_change_lifecycle(connection, kind, suspended, user_id, tenant_id):
    if kind == "account":
        result=connection.execute(
            "UPDATE m40650.users SET status=%s WHERE id=%s",
            ("SUSPENDED" if suspended else "ACTIVE",user_id),
        )
    elif kind == "admin_membership":
        result=connection.execute(
            "UPDATE m40650.memberships SET status=%s "
            "WHERE user_id=%s AND tenant_id=%s AND role='TENANT_ADMIN'",
            ("DESLIGADA" if suspended else "ATIVA",user_id,tenant_id),
        )
    elif kind == "member_membership":
        result=connection.execute(
            "UPDATE m40650.memberships SET status=%s "
            "WHERE user_id=%s AND tenant_id=%s AND role='TENANT_MEMBER'",
            ("DESLIGADA" if suspended else "ATIVA",user_id,tenant_id),
        )
    else:
        raise AssertionError("M41140_UNKNOWN_REVOCATION_KIND")
    assert result.rowcount==1, "M41140_LIFECYCLE_ROW"
    return result.rowcount


def _m41140_attempt_insert(app_dsn, capability, tenant_id, member_id,
                           idempotency_key, started, outcome, decision, state):
    import psycopg
    app=None
    try:
        app=psycopg.connect(app_dsn,autocommit=False)
        app.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        app.execute("SET LOCAL lock_timeout='15s'")
        app.execute("SET LOCAL ROLE m40650_app")
        app.execute(
            "SELECT pg_catalog.set_config('app.session_capability',%s,true)",
            (capability,),
        )
        state["pid"]=app.execute(
            "SELECT pg_catalog.pg_backend_pid()"
        ).fetchone()[0]
        started.set()
        try:
            result=app.execute(
                "INSERT INTO m41050.protected_entries "
                "(entry_id,tenant_id,member_id,amount_cents,idempotency_key) "
                "VALUES (%s,%s,%s,%s,%s)",
                (uuid4(),tenant_id,member_id,16000,idempotency_key),
            )
        except psycopg.Error as exc:
            state["sqlstate"]=exc.sqlstate
            outcome.set()
            app.rollback()
            return
        state["rowcount"]=result.rowcount
        state["sqlstate"]=None
        outcome.set()
        if not decision.wait(20):
            state["decision_timeout"]=True
            app.rollback()
        elif state.get("decision")=="commit":
            app.commit()
        else:
            app.rollback()
    except Exception as exc:
        state["error_type"]=type(exc).__name__
        state["error"]=str(exc)
        outcome.set()
        if app is not None:
            app.rollback()
        raise
    finally:
        if app is not None:
            app.close()


def _m41140_revoke_in_worker(dsn, kind, user_id, tenant_id, started, state):
    import psycopg
    with psycopg.connect(dsn,autocommit=False) as revoker:
        revoker.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        revoker.execute("SET LOCAL lock_timeout='15s'")
        state["pid"]=revoker.execute(
            "SELECT pg_catalog.pg_backend_pid()"
        ).fetchone()[0]
        started.set()
        result=_m41140_change_lifecycle(
            revoker,kind,True,user_id,tenant_id
        )
        revoker.commit()
        state["rowcount"]=result


def _m41140_wait_for_blocker(dsn, waiting_pid, blocker_pid, timeout=6.0):
    deadline=monotonic()+timeout
    with connect(dsn,autocommit=True) as monitor:
        while monotonic()<deadline:
            blockers=monitor.execute(
                "SELECT pg_catalog.pg_blocking_pids(%s)",(waiting_pid,)
            ).fetchone()[0]
            if blocker_pid in blockers:
                return True
            sleep(0.05)
    return False


def _m41140_entry_count(dsn, tenant_id, idempotency_key):
    with connect(dsn,autocommit=True) as verify:
        return verify.execute(
            "SELECT count(*) FROM m41050.protected_entries "
            "WHERE tenant_id=%s AND idempotency_key=%s",
            (tenant_id,idempotency_key),
        ).fetchone()[0]


def _m41140_capability_revoked(dsn, capability):
    token_hash=sha256(capability.encode("utf-8")).digest()
    with connect(dsn,autocommit=True) as verify:
        row=verify.execute(
            "SELECT revoked_at FROM m41050.session_caps WHERE token_hash=%s",
            (token_hash,),
        ).fetchone()
    return row is not None and row[0] is not None


def _m41140_new_write_capability(owner, auth_dsn, app_dsn, key,
                                admin_digest, tenant_id):
    ticket=issue_ticket(
        owner,auth_dsn,key,admin_digest,tenant_id,scope=WRITE_SCOPE
    )
    assert ticket is not None, "M41140_FRESH_TICKET"
    capability=bind_ticket(app_dsn,ticket,tenant_id)
    assert capability is not None, "M41140_FRESH_CAPABILITY"
    return capability


def _m41140_revoke_first(dsn, auth_dsn, app_dsn, key, admin_digest,
                         tenant_id, member_id, admin_id, kind):
    capability=None
    idempotency_key="m41140:revoke-first:"+kind+":"+uuid4().hex
    try:
        with connect(dsn,autocommit=True) as owner:
            capability=_m41140_new_write_capability(
                owner,auth_dsn,app_dsn,key,admin_digest,tenant_id
            )
        revoker=connect(dsn,autocommit=False)
        started,outcome,decision=Event(),Event(),Event()
        state={}
        blocked=False
        try:
            revoker.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
            _m41140_change_lifecycle(
                revoker,kind,True,
                admin_id if kind!="member_membership" else member_id,
                tenant_id,
            )
            revoker_pid=revoker.execute(
                "SELECT pg_catalog.pg_backend_pid()"
            ).fetchone()[0]
            with ThreadPoolExecutor(max_workers=1) as pool:
                future=pool.submit(
                    _m41140_attempt_insert,app_dsn,capability,tenant_id,
                    member_id,idempotency_key,started,outcome,decision,state,
                )
                try:
                    assert started.wait(5), "M41140_WRITE_DID_NOT_START"
                    blocked=_m41140_wait_for_blocker(
                        dsn,state["pid"],revoker_pid
                    )
                    if blocked:
                        revoker.commit()
                    else:
                        revoker.rollback()
                    assert outcome.wait(18), "M41140_WRITE_OUTCOME_TIMEOUT"
                    if state.get("rowcount") is not None:
                        state["decision"]="rollback"
                        decision.set()
                    future.result(timeout=20)
                finally:
                    state["decision"]="rollback"
                    decision.set()
            assert blocked, "M41140_REVOKE_FIRST_NOT_SERIALIZED"
            assert state.get("sqlstate")=="42501", "M41140_REVOKE_FIRST_WRITE_NOT_DENIED"
            assert _m41140_entry_count(dsn,tenant_id,idempotency_key)==0
        finally:
            revoker.rollback()
            revoker.close()
        if kind in ("account","admin_membership"):
            assert _m41140_capability_revoked(dsn,capability), "M41140_REVOKE_FIRST_CAP_NOT_REVOKED"
        print("M41140_"+kind.upper()+"_REVOKE_FIRST=PASS")
    finally:
        with connect(dsn,autocommit=True) as owner:
            _m41140_change_lifecycle(
                owner,kind,False,
                admin_id if kind!="member_membership" else member_id,
                tenant_id,
            )


def _m41140_write_first(dsn, auth_dsn, app_dsn, key, admin_digest,
                        tenant_id, member_id, admin_id, kind):
    capability=None
    idempotency_key="m41140:write-first:"+kind+":"+uuid4().hex
    writer=None
    try:
        with connect(dsn,autocommit=True) as owner:
            capability=_m41140_new_write_capability(
                owner,auth_dsn,app_dsn,key,admin_digest,tenant_id
            )
        import psycopg
        writer=psycopg.connect(app_dsn,autocommit=False)
        writer.execute("SET TRANSACTION ISOLATION LEVEL READ COMMITTED")
        writer.execute("SET LOCAL lock_timeout='15s'")
        writer.execute("SET LOCAL ROLE m40650_app")
        writer.execute(
            "SELECT pg_catalog.set_config('app.session_capability',%s,true)",
            (capability,),
        )
        writer_pid=writer.execute(
            "SELECT pg_catalog.pg_backend_pid()"
        ).fetchone()[0]
        result=writer.execute(
            "INSERT INTO m41050.protected_entries "
            "(entry_id,tenant_id,member_id,amount_cents,idempotency_key) "
            "VALUES (%s,%s,%s,%s,%s)",
            (uuid4(),tenant_id,member_id,16000,idempotency_key),
        )
        assert result.rowcount==1, "M41140_WRITE_FIRST_INSERT"
        started=Event()
        state={}
        blocked=False
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(
                _m41140_revoke_in_worker,dsn,kind,
                admin_id if kind!="member_membership" else member_id,
                tenant_id,started,state,
            )
            assert started.wait(5), "M41140_REVOKER_DID_NOT_START"
            blocked=_m41140_wait_for_blocker(dsn,state["pid"],writer_pid)
            if blocked:
                writer.commit()
            else:
                writer.rollback()
            future.result(timeout=20)
        assert blocked, "M41140_WRITE_FIRST_REVOKE_NOT_SERIALIZED"
        assert state.get("rowcount")==1, "M41140_WRITE_FIRST_REVOCATION"
        assert _m41140_entry_count(dsn,tenant_id,idempotency_key)==1
        expect_insert_denied(
            app_dsn,capability,tenant_id,member_id,16000,
            "m41140:after-revoke:"+kind+":"+uuid4().hex,
        )
        if kind in ("account","admin_membership"):
            with connect(dsn,autocommit=True) as owner:
                _m41140_change_lifecycle(
                    owner,kind,False,admin_id,tenant_id
                )
                assert _m41140_capability_revoked(dsn,capability), "M41140_WRITE_FIRST_CAP_NOT_REVOKED"
                expect_insert_denied(
                    app_dsn,capability,tenant_id,member_id,16000,
                    "m41140:after-reactivation:"+kind+":"+uuid4().hex,
                )
                fresh=_m41140_new_write_capability(
                    owner,auth_dsn,app_dsn,key,admin_digest,tenant_id
                )
            assert insert_entry(
                app_dsn,fresh,tenant_id,member_id,16000,
                "m41140:fresh:"+kind+":"+uuid4().hex,verify_authorized=True,
            )==1
        else:
            with connect(dsn,autocommit=True) as owner:
                _m41140_change_lifecycle(
                    owner,kind,False,member_id,tenant_id
                )
                fresh=_m41140_new_write_capability(
                    owner,auth_dsn,app_dsn,key,admin_digest,tenant_id
                )
            assert insert_entry(
                app_dsn,fresh,tenant_id,member_id,16000,
                "m41140:reactivated:"+uuid4().hex,verify_authorized=True,
            )==1
        print("M41140_"+kind.upper()+"_WRITE_FIRST=PASS")
    finally:
        if writer is not None:
            writer.rollback()
            writer.close()
        with connect(dsn,autocommit=True) as owner:
            _m41140_change_lifecycle(
                owner,kind,False,
                admin_id if kind!="member_membership" else member_id,
                tenant_id,
            )


def _m41140_exercise_revocation_write_races(owner, dsn, auth_dsn, app_dsn,
                                            key, tenant_id, member_id, admin_id):
    row=owner.execute(
        "SELECT token_digest FROM m40650.sessions "
        "WHERE user_id=%s AND active_role='TENANT_ADMIN' AND active_tenant_id=%s "
        "AND revoked_at IS NULL ORDER BY expires_at DESC LIMIT 1",
        (admin_id,tenant_id),
    ).fetchone()
    assert row is not None, "M41140_ADMIN_SESSION"
    admin_digest=row[0]
    for kind in ("account","admin_membership","member_membership"):
        _m41140_revoke_first(
            dsn,auth_dsn,app_dsn,key,admin_digest,tenant_id,member_id,admin_id,kind
        )
        _m41140_write_first(
            dsn,auth_dsn,app_dsn,key,admin_digest,tenant_id,member_id,admin_id,kind
        )
    print("M41140_STATUS=PASS_DISPOSABLE_REVOCATION_WRITE_RACES_ONLY")


def run(dsn: str) -> None:
    from m40700_request_proof_disposable import bootstrap as bootstrap_m40700

    key=secrets.token_bytes(32)
    tenant_a,tenant_b=uuid4(),uuid4()
    member_a,member_b,member_other,admin_a,master=[uuid4() for _ in range(5)]
    entry_a,entry_other,entry_b=[uuid4() for _ in range(3)]
    now=datetime.now(timezone.utc)
    auth_dsn,app_dsn=connection_dsns(dsn)

    with connect(dsn,autocommit=True) as owner:
        bootstrap_m40700(owner,key)
        build_context_schema(owner)
        for user,is_master in (
            (member_a,False),(member_b,False),(member_other,False),
            (admin_a,False),(master,True),
        ):
            insert_subject(owner,user_id=user,is_master=is_master)
        add_membership(owner,member_a,tenant_a,"TENANT_MEMBER")
        add_membership(owner,member_a,tenant_b,"TENANT_MEMBER")
        add_membership(owner,member_b,tenant_b,"TENANT_MEMBER")
        add_membership(owner,member_other,tenant_a,"TENANT_MEMBER")
        add_membership(owner,admin_a,tenant_a,"TENANT_ADMIN")
        # A Master account has a separate tenant-member membership, but the
        # active MASTER role is not accepted by the M40700 tenant signer.
        add_membership(owner,master,tenant_a,"TENANT_MEMBER")

        raw_a,digest_a=create_session(
            owner,member_a,"TENANT_MEMBER",tenant_a
        )
        raw_b,digest_b=create_session(
            owner,member_b,"TENANT_MEMBER",tenant_b
        )
        raw_other,digest_other=create_session(
            owner,member_other,"TENANT_MEMBER",tenant_a
        )
        raw_admin,digest_admin=create_session(
            owner,admin_a,"TENANT_ADMIN",tenant_a
        )
        raw_master,digest_master=create_session(
            owner,master,"MASTER",None
        )
        del raw_a,raw_b,raw_other,raw_admin,raw_master

        for entry,tenant,user,amount in (
            (entry_a,tenant_a,member_a,12500),
            (entry_other,tenant_a,member_other,9800),
            (entry_b,tenant_b,member_b,3000),
        ):
            owner.execute(
                "INSERT INTO m40650.entries(id,tenant_id,user_id,amount) "
                "VALUES (%s,%s,%s,%s)",
                (entry,tenant,user,amount),
            )
            owner.execute(
                "INSERT INTO m41050.protected_entries "
                "(entry_id,tenant_id,member_id,amount_cents,idempotency_key) "
                "VALUES (%s,%s,%s,%s,%s)",
                (entry,tenant,user,amount*100,"seed:"+str(entry)),
            )

        assert_acl(owner)

        forged_master=("MASTER",str(master),str(tenant_b))
        assert visible_entries(app_dsn,forged=forged_master)==[]
        assert issue_ticket(
            owner, auth_dsn,key,digest_master,tenant_a
        ) is None
        print("M41050_FORGED_GUCS_WITHOUT_CAPABILITY=DENIED")
        print("M41050_MASTER_SESSION_TICKET=DENIED")

        # Correct tenant-member ticket gives only its own rows, even when all
        # old GUCs claim Master and a different tenant.
        ticket_a=issue_ticket(owner, auth_dsn,key,digest_a,tenant_a)
        assert ticket_a is not None
        cap_a=bind_ticket(app_dsn,ticket_a,tenant_a)
        assert cap_a is not None and len(cap_a)==64
        member_rows=visible_entries(
            app_dsn,capability=cap_a,forged=forged_master
        )
        assert member_rows==[(tenant_a,member_a,1250000)]
        assert visible_entries(app_dsn,capability=cap_a,forged=(
            "TENANT_MEMBER",str(member_a),str(tenant_b)
        ))==[(tenant_a,member_a,1250000)]
        print("M41050_FORGED_MASTER_GUCS_WITH_MEMBER_CAPABILITY=DENIED")
        print("M41050_TENANT_CROSSING=DENIED")
        assert bind_ticket(app_dsn,ticket_a,tenant_a) is None
        print("M41050_BIND_TICKET_REPLAY=DENIED")

        # Tenant Admin authority is derived from its verified session, not
        # the app.current_role GUC, and remains inside tenant A.
        ticket_admin=issue_ticket(owner, auth_dsn,key,digest_admin,tenant_a)
        cap_admin=bind_ticket(app_dsn,ticket_admin,tenant_a)
        assert cap_admin is not None
        admin_rows=visible_entries(
            app_dsn,capability=cap_admin,
            forged=("TENANT_MEMBER",str(member_a),str(tenant_b)),
        )
        assert set(admin_rows)=={
            (tenant_a,member_other,980000),
            (tenant_a,member_a,1250000),
        }
        print("M41050_ADMIN_MEMBER_RLS_READ_BOUNDARY=PASS")

        # M41060 carries the signed action scope through ticket consumption.
        # Read-only claims cannot write. Write claims are append-only and
        # limited to active tenant admins and active members in that tenant.
        expect_insert_denied(
            app_dsn,cap_a,tenant_a,member_a,7777,
            "m41060:readonly:"+uuid4().hex,
        )
        print("M41060_READ_SCOPE_CANNOT_WRITE=DENIED")

        member_write_ticket=issue_ticket(
            owner, auth_dsn,key,digest_a,tenant_a,scope=WRITE_SCOPE
        )
        assert member_write_ticket is not None
        member_write_cap=bind_ticket(app_dsn,member_write_ticket,tenant_a)
        assert member_write_cap is not None
        expect_insert_denied(
            app_dsn,member_write_cap,tenant_a,member_a,8888,
            "m41060:member:"+uuid4().hex,
        )
        print("M41060_MEMBER_WRITE=DENIED")

        assert issue_ticket(
            owner, auth_dsn,key,digest_admin,tenant_a,scope="WRITE_ANYTHING"
        ) is None
        print("M41060_UNLISTED_SCOPE=DENIED")

        admin_write_ticket=issue_ticket(
            owner, auth_dsn,key,digest_admin,tenant_a,scope=WRITE_SCOPE
        )
        assert admin_write_ticket is not None
        admin_write_cap=bind_ticket(app_dsn,admin_write_ticket,tenant_a)
        assert admin_write_cap is not None
        assert visible_entries(app_dsn,capability=admin_write_cap)==[]
        print("M41060_WRITE_CAPABILITY_CANNOT_READ=DENIED")

        forged_write=("MASTER",str(master),str(tenant_b))
        admin_claims,admin_can_write=write_authorization_state(
            app_dsn,admin_write_cap,tenant_a,member_a,forged=forged_write
        )
        assert admin_claims==[
            (admin_a,"TENANT_ADMIN",tenant_a,WRITE_SCOPE)
        ]
        assert admin_can_write is True
        print("M41060_ADMIN_WRITE_SCOPE_RESOLVED=PASS")
        print("M41060_ADMIN_WRITE_SCOPE_RESISTS_LEGACY_GUCS=PASS")

        once_key="m41060:admin:"+uuid4().hex
        assert insert_entry(
            app_dsn,admin_write_cap,tenant_a,member_a,15000,once_key,
            verify_authorized=True,
        )==1
        assert insert_entry(
            app_dsn,admin_write_cap,tenant_a,member_a,15000,once_key,
        )==0
        expect_insert_denied(
            app_dsn,admin_write_cap,tenant_b,member_b,15000,
            "m41060:crosstenant:"+uuid4().hex,
            forged=("TENANT_ADMIN",str(admin_a),str(tenant_a)),
        )
        print("M41060_ADMIN_TENANT_WRITE_AND_CROSS_TENANT_DENIAL=PASS")

        # Six separate SQL sessions race the same tenant-scoped idempotency key.
        race_key="m41060:race:"+uuid4().hex
        workers=6
        barrier=Barrier(workers,timeout=20)
        def race_insert(_index):
            barrier.wait(timeout=20)
            return insert_entry(
                app_dsn,admin_write_cap,tenant_a,member_other,22000,race_key
            )
        with ThreadPoolExecutor(max_workers=workers) as pool:
            inserted=list(pool.map(race_insert,range(workers)))
        assert sum(inserted)==1
        with connect(dsn,autocommit=True) as verify:
            count=verify.execute(
                "SELECT count(*) FROM m41050.protected_entries "
                "WHERE tenant_id=%s AND idempotency_key=%s",
                (tenant_a,race_key),
            ).fetchone()[0]
        assert count==1
        print("M41060_CONCURRENT_IDEMPOTENCY_SINGLE_ROW=PASS")
        print("M41060_GATE=NO_GO_PENDING_REAL_STAGING_AND_INDEPENDENT_REVIEW")

        # Six app SQL connections race one valid ticket; atomic ticket consume
        # permits only one capability to be minted.
        race_ticket=issue_ticket(owner, auth_dsn,key,digest_other,tenant_a)
        assert race_ticket is not None
        workers=6
        barrier=Barrier(workers,timeout=20)
        def race(_index):
            barrier.wait(timeout=20)
            return bind_ticket(app_dsn,race_ticket,tenant_a)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            race_results=list(pool.map(race,range(workers)))
        minted=[value for value in race_results if value is not None]
        assert len(minted)==1
        print("M41050_CONCURRENT_TICKET_BIND_SINGLE_CAPABILITY=PASS")

        # A capability is rejected immediately after its backing session is
        # revoked, even if the capability GUC is still present.
        ticket_b=issue_ticket(owner, auth_dsn,key,digest_b,tenant_b)
        cap_b=bind_ticket(app_dsn,ticket_b,tenant_b)
        assert cap_b is not None
        owner.execute(
            "UPDATE m40650.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_digest=%s",(digest_b,),
        )
        assert visible_entries(
            app_dsn,capability=cap_b,
            forged=("TENANT_MEMBER",str(member_b),str(tenant_b)),
        )==[]
        print("M41050_REVOKED_SESSION_CAPABILITY=DENIED")

        # M41100 revokes a freshly validated synthetic member session
        # between two borrows of one asyncpg physical connection.
        raw_pool_member, digest_pool_member = create_session(
            owner, member_b, "TENANT_MEMBER", tenant_b
        )
        del raw_pool_member
        pool_ticket = issue_ticket(
            owner, auth_dsn, key, digest_pool_member, tenant_b
        )
        assert pool_ticket is not None
        pool_capability = bind_ticket(app_dsn, pool_ticket, tenant_b)
        assert pool_capability is not None
        asyncio.run(
            _m41100_exercise_revoke_between_pool_borrows(
                dsn, pool_capability, digest_pool_member, tenant_b, member_b,
                forged_master,
            )
        )

        # M41080 passes the SQL-issued capability through the real asyncpg
        # helper while each RLS query/write runs in the same transaction.
        async_read_ticket = issue_ticket(owner, auth_dsn, key, digest_a, tenant_a)
        assert async_read_ticket is not None
        async_read_cap = bind_ticket(app_dsn, async_read_ticket, tenant_a)
        assert async_read_cap is not None

        async_write_ticket = issue_ticket(
            owner, auth_dsn, key, digest_admin, tenant_a, scope=WRITE_SCOPE
        )
        assert async_write_ticket is not None
        async_write_cap = bind_ticket(app_dsn, async_write_ticket, tenant_a)
        assert async_write_cap is not None

        async_race_key = "m41080:asyncpg-race:" + uuid4().hex

        async def exercise_m41080_asyncpg():
            expected_member_rows = [
                (tenant_a, member_a, 15000),
                (tenant_a, member_a, 1250000),
            ]
            await _m41090_exercise_asyncpg_pool(
                dsn, async_read_cap, expected_member_rows, forged_master
            )
            own_rows = await _m41080_asyncpg_visible_entries(
                dsn, async_read_cap, forged=forged_master
            )
            # M41060 committed one prior admin append for member_a; a
            # member capability must see both own rows and no other member.
            assert own_rows == expected_member_rows, "M41080_ASYNCPG_MEMBER_RLS_MISMATCH"
            print("M41080_ASYNCPG_M41060_PRIOR_MEMBER_ROW_ACCOUNTED=PASS")
            print("M41080_ASYNCPG_MEMBER_RLS_FORGED_CONTEXT=PASS")

            read_write = await _m41080_asyncpg_insert_entry(
                dsn, async_read_cap, tenant_a, member_a, 15000,
                "m41080:read-denied:" + uuid4().hex,
                forged=forged_master,
            )
            assert read_write == "DENIED", "M41080_ASYNCPG_READ_SCOPE_WRITE_NOT_DENIED"
            print("M41080_ASYNCPG_READ_SCOPE_CANNOT_WRITE=DENIED")

            write_rows = await _m41080_asyncpg_visible_entries(
                dsn, async_write_cap
            )
            assert write_rows == [], "M41080_ASYNCPG_WRITE_SCOPE_READS_ROWS"
            print("M41080_ASYNCPG_WRITE_SCOPE_CANNOT_READ=DENIED")

            once_key = "m41080:admin-once:" + uuid4().hex
            first = await _m41080_asyncpg_insert_entry(
                dsn, async_write_cap, tenant_a, member_a, 15000, once_key
            )
            duplicate = await _m41080_asyncpg_insert_entry(
                dsn, async_write_cap, tenant_a, member_a, 15000, once_key
            )
            assert first == "INSERTED", "M41080_ASYNCPG_ADMIN_INSERT_NOT_ALLOWED"
            assert duplicate == "DUPLICATE", "M41080_ASYNCPG_DUPLICATE_NOT_DENIED"
            print("M41080_ASYNCPG_ADMIN_INSERT=PASS")

            cross_tenant = await _m41080_asyncpg_insert_entry(
                dsn, async_write_cap, tenant_b, member_b, 15000,
                "m41080:cross-tenant:" + uuid4().hex,
                forged=forged_master,
            )
            assert cross_tenant == "DENIED", "M41080_ASYNCPG_CROSS_TENANT_NOT_DENIED"
            print("M41080_ASYNCPG_CROSS_TENANT_INSERT=DENIED")

            ready = 0
            start = asyncio.Event()

            async def race_insert():
                nonlocal ready
                ready += 1
                if ready == 4:
                    start.set()
                await start.wait()
                return await _m41080_asyncpg_insert_entry(
                    dsn, async_write_cap, tenant_a, member_other, 15000,
                    async_race_key,
                )

            raced = await asyncio.gather(*(race_insert() for _ in range(4)))
            assert raced.count("INSERTED") == 1, "M41080_ASYNCPG_RACE_INSERT_COUNT"
            assert raced.count("DUPLICATE") == 3, "M41080_ASYNCPG_RACE_DUPLICATE_COUNT"
            return once_key, async_race_key

        once_key, race_key = asyncio.run(exercise_m41080_asyncpg())
        once_count = owner.execute(
            "SELECT count(*) FROM m41050.protected_entries "
            "WHERE tenant_id=%s AND idempotency_key=%s",
            (tenant_a, once_key),
        ).fetchone()[0]
        race_count = owner.execute(
            "SELECT count(*) FROM m41050.protected_entries "
            "WHERE tenant_id=%s AND idempotency_key=%s",
            (tenant_a, race_key),
        ).fetchone()[0]
        assert once_count == 1 and race_count == 1, "M41080_ASYNCPG_IDEMPOTENCY_ROW_COUNT"
        print("M41080_ASYNCPG_IDEMPOTENCY_SINGLE_ROW=PASS")
        print("M41080_ASYNCPG_CONCURRENT_IDEMPOTENCY_SINGLE_ROW=PASS")
        _m41110_exercise_role_binding(
            owner, dsn, auth_dsn, app_dsn, key, tenant_a, member_a, member_other
        )
        print("M41110_STATUS=PASS_DISPOSABLE_ROLE_BINDING_ONLY")
        _m41120_exercise_ticket_context(
            owner, auth_dsn, app_dsn, key, tenant_a, member_a, member_other
        )
        print("M41120_STATUS=PASS_DISPOSABLE_TICKET_CONTEXT_ONLY")
        _m41130_exercise_lifecycle(
            owner,auth_dsn,app_dsn,key,tenant_a,tenant_b,member_a,admin_a,member_other
        )
        print("M41130_STATUS=PASS_DISPOSABLE_LIFECYCLE_ONLY")
        _m41140_exercise_revocation_write_races(
            owner,dsn,auth_dsn,app_dsn,key,tenant_a,member_a,admin_a
        )
        print("M41080_STATUS=PASS_DISPOSABLE_ASYNCPG_RLS_ONLY")
        print("M41050_GATE=NO_GO_UNTIL_KEY_CUSTODY_AND_RUNTIME_ATTESTATION")
        print("M41060_STATUS=PASS_DISPOSABLE_WRITE_RLS_ONLY")


def main() -> int:
    print("=== FR FINANCE M41050 — VÍNCULO DE TICKET, CAPABILITY E RLS ===")
    try:
        dsn=require_disposable()
        run(dsn)
    except Exception as exc:
        diagnostic = str(exc)
        if (
            isinstance(exc, AssertionError)
            and diagnostic.startswith(("M41080_ASYNCPG_", "M41090_ASYNCPG_", "M41100_ASYNCPG_", "M41110_", "M41130_", "M41140_"))
            and diagnostic.replace("_", "").isalnum()
        ):
            if diagnostic.startswith("M41140_"):
                prefix = "M41140_DIAGNOSTIC="
            elif diagnostic.startswith("M41130_"):
                prefix = "M41130_DIAGNOSTIC="
            elif diagnostic.startswith("M41110_"):
                prefix = "M41110_DIAGNOSTIC="
            elif diagnostic.startswith("M41100_"):
                prefix = "M41100_DIAGNOSTIC="
            elif diagnostic.startswith("M41090_"):
                prefix = "M41090_DIAGNOSTIC="
            else:
                prefix = "M41080_DIAGNOSTIC="
            print(prefix+diagnostic)
        print("M41050_STATUS=BLOCKED_"+type(exc).__name__)
        return 2
    finally:
        print("M41050_LOCAL_DATABASE_CONNECTIONS=NONE")
        print("M41050_TERMUX_PG_5433=NOT_ACCESSED")
        print("M41050_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M41050_LOCAL_SQL=NONE")
        print("M41050_LOCAL_MIGRATIONS=NONE")
        print("M41050_LOCAL_DB_WRITES=NONE")
        print("M41050_SERVICE_RESTARTS=NONE")
        print("M41050_PIX_REAL=OFF")
        print("M41050_PAGAMENTOS_REAIS=OFF")
        print("M41050_ATIVACAO_REAL=OFF")
        print("M41050_PRODUCTION=BLOCKED")
    print("M41050_STATUS=PASS_DISPOSABLE_PROOF_ONLY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
