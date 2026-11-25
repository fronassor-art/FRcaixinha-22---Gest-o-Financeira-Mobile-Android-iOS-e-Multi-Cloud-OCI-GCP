#!/usr/bin/env python3
"""M41050 adversarial fixture; connect only to disposable GitHub Actions PG18."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import os
from pathlib import Path
import secrets
import sys
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[2]
APP_PATH = ROOT / "backend" / "app"
sys.path.insert(0, str(APP_PATH))
from m41050_session_context_seal_prototype import (
    SessionClaims,
    make_session_proof,
)

DATABASE = "fr_m41050_disposable_ci"
PORT = 55450
PASSWORD = "only_m41050_disposable_ci"
ISSUER_PASSWORD = "m41050_fixture_issuer_only"
APP_PASSWORD = "m41050_fixture_app_only"


def require_disposable() -> str:
    expected = {
        "GITHUB_ACTIONS": "true",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "CI_M41050_DISPOSABLE": "1",
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
            and parsed.password == PASSWORD
            and not parsed.query
            and not parsed.fragment
        )
    except (ValueError, AttributeError, TypeError):
        valid = False
    if not valid:
        raise RuntimeError("M41050_DISPOSABLE_DATABASE_IDENTITY_DENIED")
    return dsn


def connect(dsn: str, *, user: str = "postgres", password: str = PASSWORD,
            autocommit: bool = True):
    import psycopg
    parsed = urlsplit(dsn)
    return psycopg.connect(
        host=parsed.hostname,
        port=parsed.port,
        dbname=parsed.path[1:],
        user=user,
        password=password,
        autocommit=autocommit,
        connect_timeout=5,
    )


def bootstrap(owner, key: bytes) -> None:
    owner.execute("CREATE EXTENSION pgcrypto")
    owner.execute(
        "CREATE ROLE m41050_owner NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    owner.execute(
        "CREATE ROLE m41050_issuer NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    owner.execute(
        "CREATE ROLE m41050_app NOLOGIN NOINHERIT NOBYPASSRLS"
    )
    owner.execute(
        "CREATE ROLE m41050_issuer_login LOGIN NOINHERIT NOBYPASSRLS "
        "PASSWORD 'm41050_fixture_issuer_only'"
    )
    owner.execute(
        "CREATE ROLE m41050_app_login LOGIN NOINHERIT NOBYPASSRLS "
        "PASSWORD 'm41050_fixture_app_only'"
    )
    owner.execute("GRANT m41050_issuer TO m41050_issuer_login")
    owner.execute("GRANT m41050_app TO m41050_app_login")
    owner.execute(
        "CREATE SCHEMA m41050 AUTHORIZATION m41050_owner"
    )
    owner.execute(
        "GRANT USAGE ON SCHEMA m41050 TO m41050_issuer,m41050_app"
    )

    owner.execute("SET ROLE m41050_owner")
    owner.execute("""
        CREATE TABLE m41050.key_material (
            key_id text PRIMARY KEY,
            verify_key bytea NOT NULL CHECK (pg_catalog.octet_length(verify_key)=32),
            active boolean NOT NULL DEFAULT true
        )
    """)
    owner.execute("""
        CREATE TABLE m41050.used_nonces (
            nonce uuid PRIMARY KEY,
            claims_digest bytea NOT NULL,
            expires_epoch bigint NOT NULL
        )
    """)
    owner.execute("""
        CREATE TABLE m41050.sessions (
            token_hash bytea PRIMARY KEY CHECK (pg_catalog.octet_length(token_hash)=32),
            session_id uuid NOT NULL,
            user_id uuid NOT NULL,
            role_name text NOT NULL,
            tenant_id uuid,
            scope_name text NOT NULL CHECK (scope_name='READ_ONLY'),
            expires_epoch bigint NOT NULL,
            revoked_at timestamptz
        )
    """)
    owner.execute("""
        CREATE TABLE m41050.legacy_promotions (
            promotion_id integer PRIMARY KEY,
            created_by uuid NOT NULL,
            title text NOT NULL
        )
    """)
    owner.execute("""
        CREATE TABLE m41050.sealed_promotions (
            promotion_id integer PRIMARY KEY,
            created_by uuid NOT NULL,
            title text NOT NULL
        )
    """)
    owner.execute("""
        CREATE TABLE m41050.entries (
            entry_id uuid PRIMARY KEY,
            tenant_id uuid NOT NULL,
            member_id uuid NOT NULL,
            amount_cents integer NOT NULL CHECK (amount_cents > 0)
        )
    """)

    owner.execute("""
        CREATE FUNCTION m41050.constant_time_equal(p_left bytea,p_right bytea)
        RETURNS boolean
        LANGUAGE plpgsql IMMUTABLE STRICT
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE v_diff integer := 0; v_i integer;
        BEGIN
          IF pg_catalog.octet_length(p_left)<>32
             OR pg_catalog.octet_length(p_right)<>32
          THEN RETURN false; END IF;
          FOR v_i IN 0..31 LOOP
            v_diff := v_diff | (
              pg_catalog.get_byte(p_left,v_i) # pg_catalog.get_byte(p_right,v_i)
            );
          END LOOP;
          RETURN v_diff=0;
        END
        $body$
    """)
    owner.execute("""
        CREATE FUNCTION m41050.issue_session(
            p_session_id uuid,p_user_id uuid,p_role text,p_tenant_id uuid,
            p_nonce uuid,p_expires_epoch bigint,p_scope text,p_proof bytea
        )
        RETURNS text
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
        DECLARE
          v_now bigint;
          v_claims text;
          v_key bytea;
          v_nonce uuid;
          v_token text;
        BEGIN
          IF p_session_id IS NULL OR p_session_id='00000000-0000-0000-0000-000000000000'
             OR p_user_id IS NULL OR p_user_id='00000000-0000-0000-0000-000000000000'
             OR p_nonce IS NULL OR p_nonce='00000000-0000-0000-0000-000000000000'
             OR p_role IS NULL OR p_role NOT IN ('MASTER','TENANT_ADMIN','TENANT_MEMBER')
             OR p_scope IS DISTINCT FROM 'READ_ONLY'
             OR p_proof IS NULL OR pg_catalog.octet_length(p_proof)<>32
          THEN RETURN NULL; END IF;
          IF p_role='MASTER' AND p_tenant_id IS NOT NULL
          THEN RETURN NULL; END IF;
          IF p_role IN ('TENANT_ADMIN','TENANT_MEMBER')
             AND (p_tenant_id IS NULL
                  OR p_tenant_id='00000000-0000-0000-0000-000000000000')
          THEN RETURN NULL; END IF;

          v_now := pg_catalog.floor(
            EXTRACT(EPOCH FROM pg_catalog.statement_timestamp())
          )::bigint;
          IF p_expires_epoch IS NULL OR p_expires_epoch<=v_now
             OR p_expires_epoch>v_now+60
          THEN RETURN NULL; END IF;

          v_claims := 'FRF-M41050|v1|SESSION|'
            || p_session_id::text || '|' || p_user_id::text || '|'
            || p_role || '|' || COALESCE(p_tenant_id::text,'-') || '|'
            || p_nonce::text || '|' || p_expires_epoch::text || '|'
            || p_scope;
          SELECT verify_key INTO v_key
            FROM m41050.key_material
           WHERE key_id='v1' AND active;
          IF v_key IS NULL OR NOT m41050.constant_time_equal(
               public.hmac(
                 pg_catalog.convert_to(v_claims,'UTF8'),v_key,'sha256'
               ),
               p_proof
             )
          THEN RETURN NULL; END IF;

          INSERT INTO m41050.used_nonces(nonce,claims_digest,expires_epoch)
          VALUES(
            p_nonce,
            public.digest(pg_catalog.convert_to(v_claims,'UTF8'),'sha256'),
            p_expires_epoch
          )
          ON CONFLICT(nonce) DO NOTHING
          RETURNING nonce INTO v_nonce;
          IF NOT FOUND THEN RETURN NULL; END IF;

          v_token := pg_catalog.encode(public.gen_random_bytes(32),'hex');
          INSERT INTO m41050.sessions(
            token_hash,session_id,user_id,role_name,tenant_id,scope_name,expires_epoch
          )
          VALUES(
            public.digest(pg_catalog.convert_to(v_token,'UTF8'),'sha256'),
            p_session_id,p_user_id,p_role,p_tenant_id,p_scope,p_expires_epoch
          );
          RETURN v_token;
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
          SELECT s.user_id,s.role_name,s.tenant_id,s.scope_name
            FROM m41050.sessions AS s
           WHERE s.token_hash=public.digest(
                   pg_catalog.convert_to(v_capability,'UTF8'),'sha256'
                 )
             AND s.scope_name='READ_ONLY'
             AND s.revoked_at IS NULL
             AND s.expires_epoch >
                 pg_catalog.floor(
                   EXTRACT(EPOCH FROM pg_catalog.statement_timestamp())
                 )::bigint;
        END
        $body$
    """)
    owner.execute("ALTER TABLE m41050.key_material OWNER TO m41050_owner")
    owner.execute("ALTER TABLE m41050.used_nonces OWNER TO m41050_owner")
    owner.execute("ALTER TABLE m41050.sessions OWNER TO m41050_owner")
    owner.execute(
        "INSERT INTO m41050.key_material(key_id,verify_key) VALUES ('v1',%s)",
        (key,),
    )
    owner.execute("""
        ALTER TABLE m41050.legacy_promotions OWNER TO m41050_owner
    """)
    owner.execute("""
        ALTER TABLE m41050.sealed_promotions OWNER TO m41050_owner
    """)
    owner.execute("ALTER TABLE m41050.entries OWNER TO m41050_owner")
    owner.execute("""
        ALTER FUNCTION m41050.constant_time_equal(bytea,bytea)
        OWNER TO m41050_owner
    """)
    owner.execute("""
        ALTER FUNCTION m41050.issue_session(uuid,uuid,text,uuid,uuid,bigint,text,bytea)
        OWNER TO m41050_owner
    """)
    owner.execute("""
        ALTER FUNCTION m41050.current_claims()
        OWNER TO m41050_owner
    """)
    owner.execute("""
        ALTER TABLE m41050.legacy_promotions ENABLE ROW LEVEL SECURITY
    """)
    owner.execute("""
        ALTER TABLE m41050.legacy_promotions FORCE ROW LEVEL SECURITY
    """)
    owner.execute("""
        CREATE POLICY legacy_guc_read ON m41050.legacy_promotions
        FOR SELECT TO m41050_app
        USING (
          pg_catalog.current_setting('app.current_role',true)='MASTER'
          AND created_by =
              NULLIF(pg_catalog.current_setting('app.current_user_id',true),'')::uuid
        )
    """)
    owner.execute("""
        ALTER TABLE m41050.sealed_promotions ENABLE ROW LEVEL SECURITY
    """)
    owner.execute("""
        ALTER TABLE m41050.sealed_promotions FORCE ROW LEVEL SECURITY
    """)
    owner.execute("""
        CREATE POLICY signed_master_read ON m41050.sealed_promotions
        FOR SELECT TO m41050_app
        USING (
          EXISTS (
            SELECT 1 FROM m41050.current_claims() AS c
             WHERE c.role_name='MASTER'
               AND c.scope_name='READ_ONLY'
               AND c.user_id=sealed_promotions.created_by
          )
        )
    """)
    owner.execute("ALTER TABLE m41050.entries ENABLE ROW LEVEL SECURITY")
    owner.execute("ALTER TABLE m41050.entries FORCE ROW LEVEL SECURITY")
    owner.execute("""
        CREATE POLICY signed_member_read ON m41050.entries
        FOR SELECT TO m41050_app
        USING (
          EXISTS (
            SELECT 1 FROM m41050.current_claims() AS c
             WHERE c.role_name='TENANT_MEMBER'
               AND c.scope_name='READ_ONLY'
               AND c.user_id=entries.member_id
               AND c.tenant_id=entries.tenant_id
          )
        )
    """)
    owner.execute("REVOKE ALL ON ALL TABLES IN SCHEMA m41050 FROM PUBLIC")
    owner.execute(
        "REVOKE ALL ON ALL FUNCTIONS IN SCHEMA m41050 FROM PUBLIC"
    )
    owner.execute("""
        GRANT SELECT ON m41050.legacy_promotions,
          m41050.sealed_promotions,m41050.entries TO m41050_app
    """)
    owner.execute("""
        GRANT EXECUTE ON FUNCTION m41050.current_claims()
        TO m41050_app
    """)
    owner.execute("""
        GRANT EXECUTE ON FUNCTION
          m41050.issue_session(uuid,uuid,text,uuid,uuid,bigint,text,bytea)
        TO m41050_issuer
    """)
    owner.execute("RESET ROLE")

    owner.execute("""
        INSERT INTO m41050.legacy_promotions
          (promotion_id,created_by,title) VALUES (1,%s,'fixture legacy')
    """, (MASTER_ID,))
    owner.execute("""
        INSERT INTO m41050.sealed_promotions
          (promotion_id,created_by,title) VALUES (1,%s,'fixture protected')
    """, (MASTER_ID,))
    owner.execute(
        "INSERT INTO m41050.entries(entry_id,tenant_id,member_id,amount_cents) "
        "VALUES (%s,%s,%s,12500),(%s,%s,%s,9800)",
        (ENTRY_A, TENANT_A, MEMBER_A, ENTRY_B, TENANT_B, MEMBER_B),
    )


def login_connection(dsn: str, role: str, *, autocommit: bool):
    passwords = {
        "m41050_issuer_login": ISSUER_PASSWORD,
        "m41050_app_login": APP_PASSWORD,
    }
    return connect(
        dsn, user=role, password=passwords[role], autocommit=autocommit
    )


def issue(dsn: str, claims: SessionClaims, proof: bytes) -> str | None:
    with login_connection(
        dsn, "m41050_issuer_login", autocommit=True
    ) as conn:
        conn.execute("SET ROLE m41050_issuer")
        return conn.execute(
            "SELECT m41050.issue_session(%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                claims.session_id, claims.user_id, claims.role,
                claims.tenant_id, claims.nonce, claims.expires_epoch,
                claims.scope, proof,
            ),
        ).fetchone()[0]


def app_count(dsn: str, query: str, capability: str | None = None,
              forged: tuple[str, str, str] | None = None) -> list[tuple]:
    with login_connection(dsn, "m41050_app_login", autocommit=False) as conn:
        conn.execute("SET ROLE m41050_app")
        if capability is not None:
            conn.execute(
                "SELECT pg_catalog.set_config('app.session_capability',%s,true)",
                (capability,),
            )
        if forged is not None:
            role, user_id, tenant_id = forged
            conn.execute(
                "SELECT pg_catalog.set_config('app.current_role',%s,true)",
                (role,),
            )
            conn.execute(
                "SELECT pg_catalog.set_config('app.current_user_id',%s,true)",
                (user_id,),
            )
            conn.execute(
                "SELECT pg_catalog.set_config('app.current_tenant_id',%s,true)",
                (tenant_id,),
            )
        return conn.execute(query).fetchall()


def expiry(seconds: int = 50) -> int:
    return int(datetime.now(timezone.utc).timestamp()) + seconds


def _assert_role_acl(owner) -> None:
    roles = owner.execute(
        "SELECT rolname,rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolcanlogin "
        "FROM pg_catalog.pg_roles "
        "WHERE rolname IN ('m41050_owner','m41050_issuer','m41050_app',"
        "'m41050_issuer_login','m41050_app_login') ORDER BY rolname"
    ).fetchall()
    assert len(roles) == 5
    for name, superuser, bypass, create_role, create_db, can_login in roles:
        assert not any((superuser, bypass, create_role, create_db)), name
        assert can_login == name.endswith("_login"), name
    for role in ("m41050_app", "m41050_issuer"):
        for table in (
            "m41050.key_material", "m41050.sessions", "m41050.used_nonces",
        ):
            assert not owner.execute(
                "SELECT has_table_privilege(%s,%s,'SELECT')", (role, table)
            ).fetchone()[0], (role, table)
    issue_sig = (
        "m41050.issue_session(uuid,uuid,text,uuid,uuid,bigint,text,bytea)"
    )
    assert owner.execute(
        "SELECT has_function_privilege('m41050_issuer',%s,'EXECUTE')",
        (issue_sig,),
    ).fetchone()[0]
    assert not owner.execute(
        "SELECT has_function_privilege('m41050_app',%s,'EXECUTE')",
        (issue_sig,),
    ).fetchone()[0]
    for table in ("m41050.sealed_promotions", "m41050.entries"):
        rls = owner.execute(
            "SELECT relrowsecurity,relforcerowsecurity "
            "FROM pg_catalog.pg_class WHERE oid=%s::regclass", (table,)
        ).fetchone()
        assert rls == (True, True), (table, rls)
    print("M41050_ROLE_ACL_FORCE_RLS_AND_SECRET_TABLES=PASS")


def run(dsn: str) -> None:
    global MASTER_ID, TENANT_A, TENANT_B, MEMBER_A, MEMBER_B, ENTRY_A, ENTRY_B
    MASTER_ID = uuid4()
    TENANT_A, TENANT_B = uuid4(), uuid4()
    MEMBER_A, MEMBER_B = uuid4(), uuid4()
    ENTRY_A, ENTRY_B = uuid4(), uuid4()
    key = secrets.token_bytes(32)
    import psycopg

    with connect(dsn, autocommit=True) as owner:
        bootstrap(owner, key)
        _assert_role_acl(owner)

        # Reproduce the legacy custom-GUC behavior, then show that the new
        # policy ignores the forged values and needs a signed capability.
        forged = ("MASTER", str(MASTER_ID), "")
        legacy = app_count(
            dsn, "SELECT promotion_id FROM m41050.legacy_promotions", forged=forged
        )
        sealed_without_cap = app_count(
            dsn, "SELECT promotion_id FROM m41050.sealed_promotions",
            forged=forged,
        )
        assert legacy == [(1,)]
        assert sealed_without_cap == []
        print("M41050_LEGACY_GUC_SPOOF=REPRODUCED")
        print("M41050_FORGED_GUCS_WITHOUT_CAPABILITY=DENIED")

        master = SessionClaims(
            uuid4(), MASTER_ID, "MASTER", None, uuid4(), expiry()
        )
        master_proof = make_session_proof(key=key, claims=master)
        # A stolen issuer SQL login has EXECUTE only; without a valid HMAC proof
        # it cannot mint a Master capability. Invalid proof must not burn nonce.
        wrong_proof = bytes(value ^ 1 for value in master_proof)
        assert issue(dsn, master, wrong_proof) is None
        print("M41050_COMPROMISED_ISSUER_SQL_LOGIN_WITHOUT_PROOF=DENIED")
        changed = SessionClaims(
            master.session_id, master.user_id, "TENANT_ADMIN", TENANT_A,
            master.nonce, master.expires_epoch,
        )
        assert issue(dsn, changed, master_proof) is None
        print("M41050_SIGNED_CLAIM_TAMPERING=DENIED")
        expired = SessionClaims(
            uuid4(), MASTER_ID, "MASTER", None, uuid4(),
            int(datetime.now(timezone.utc).timestamp()) - 1,
        )
        assert issue(
            dsn, expired, make_session_proof(key=key, claims=expired)
        ) is None
        print("M41050_EXPIRED_SESSION=DENIED")

        master_cap = issue(dsn, master, master_proof)
        assert isinstance(master_cap, str) and len(master_cap) == 64
        master_rows = app_count(
            dsn, "SELECT promotion_id FROM m41050.sealed_promotions",
            capability=master_cap, forged=("TENANT_MEMBER", str(MEMBER_A), str(TENANT_A)),
        )
        master_member_rows = app_count(
            dsn, "SELECT entry_id FROM m41050.entries",
            capability=master_cap,
        )
        assert master_rows == [(1,)]
        assert master_member_rows == []
        print("M41050_VALID_MASTER_READ_AND_PRIVATE_LEDGER_DENIAL=PASS")

        member = SessionClaims(
            uuid4(), MEMBER_A, "TENANT_MEMBER", TENANT_A,
            uuid4(), expiry(),
        )
        member_proof = make_session_proof(key=key, claims=member)
        member_cap = issue(dsn, member, member_proof)
        assert isinstance(member_cap, str) and len(member_cap) == 64
        # All legacy GUCs claim a different master and tenant. RLS takes
        # identity solely from the random DB capability associated with MAC.
        member_rows = app_count(
            dsn,
            "SELECT tenant_id,member_id,amount_cents FROM m41050.entries",
            capability=member_cap,
            forged=("MASTER", str(MASTER_ID), str(TENANT_B)),
        )
        assert member_rows == [(TENANT_A, MEMBER_A, 12500)]
        print("M41050_FORGED_MASTER_GUCS_WITH_MEMBER_CAPABILITY=DENIED")
        print("M41050_TENANT_CROSSING=DENIED")

        # Atomic nonce uniqueness covers exact replay and concurrent issuers.
        assert issue(dsn, member, member_proof) is None
        print("M41050_NONCE_REPLAY_SINGLE_ISSUE=PASS")
        concurrent = SessionClaims(
            uuid4(), MASTER_ID, "MASTER", None, uuid4(), expiry()
        )
        concurrent_proof = make_session_proof(key=key, claims=concurrent)
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(
                lambda _n: issue(dsn, concurrent, concurrent_proof), range(6)
            ))
        accepted = [value for value in results if value is not None]
        assert len(accepted) == 1
        print("M41050_CONCURRENT_NONCE_SINGLE_ISSUE=PASS")

        # Revocation is effective for a capability already issued.
        owner.execute(
            "UPDATE m41050.sessions SET revoked_at=pg_catalog.clock_timestamp() "
            "WHERE token_hash=public.digest(pg_catalog.convert_to(%s,'UTF8'),'sha256')",
            (master_cap,),
        )
        assert app_count(
            dsn, "SELECT promotion_id FROM m41050.sealed_promotions",
            capability=master_cap,
        ) == []
        print("M41050_REVOKED_CAPABILITY=DENIED")
        print("M41050_GATE=NO_GO_UNTIL_EXTERNAL_REVIEW_AND_RUNTIME_ATTESTATION")


def main() -> int:
    print("=== FR FINANCE M41050 — ASSINATURA DE CONTEXTO SQL ===")
    try:
        dsn = require_disposable()
        run(dsn)
    except Exception as exc:
        print("M41050_STATUS=BLOCKED_" + type(exc).__name__)
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
