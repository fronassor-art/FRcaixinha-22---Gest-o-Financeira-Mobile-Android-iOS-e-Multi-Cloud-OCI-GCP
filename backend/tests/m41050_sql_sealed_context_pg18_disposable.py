#!/usr/bin/env python3
"""M41050: bind consumed M40700 tickets to a disposable RLS capability."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
from pathlib import Path
import secrets
import sys
from threading import Barrier
from urllib.parse import urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "backend" / "tests"
sys.path.insert(0, str(TESTS))
from m40700_request_proof_disposable import (
    SCOPE,
    WRITE_SCOPE,
    bootstrap as bootstrap_m40700,
    sign as sign_m40700,
)

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


def build_context_schema(owner) -> None:
    owner.execute("CREATE SCHEMA m41050 AUTHORIZATION m40650_owner")
    owner.execute("REVOKE ALL ON SCHEMA m41050 FROM PUBLIC")
    owner.execute("GRANT USAGE ON SCHEMA m41050 TO m40650_app")
    owner.execute("""
        CREATE TABLE m41050.session_caps (
          token_hash bytea PRIMARY KEY
            CHECK (pg_catalog.octet_length(token_hash)=32),
          session_digest text NOT NULL,
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
          SELECT t.session_digest,t.expires_at,x.scope_name
            INTO v_session_digest,v_expiry,v_scope
            FROM m40650.m40680_tickets AS t
            JOIN m40700.ticket_scopes AS x
              ON x.ticket_digest=t.digest
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
             AND s.revoked_at IS NULL
             AND s.expires_at>pg_catalog.statement_timestamp()
             AND s.active_role IN ('TENANT_ADMIN','TENANT_MEMBER')
             AND s.active_tenant_id=p_tenant;
          IF NOT FOUND OR v_expiry<=pg_catalog.statement_timestamp()
          THEN RETURN NULL; END IF;

          v_capability :=
            pg_catalog.replace(pg_catalog.gen_random_uuid()::text,'-','')
            || pg_catalog.replace(pg_catalog.gen_random_uuid()::text,'-','');
          INSERT INTO m41050.session_caps(
            token_hash,session_digest,tenant_id,expires_at,scope_name
          )
          VALUES(
            pg_catalog.sha256(
              pg_catalog.convert_to(v_capability,'UTF8')
            ),
            v_session_digest,v_tenant,v_expiry,v_scope
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
        RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path=pg_catalog,pg_temp
        AS $body$
          SELECT EXISTS(
            SELECT 1
              FROM m41050.current_claims() AS c
              JOIN m40650.memberships AS m
                ON m.user_id=p_member
               AND m.tenant_id=p_tenant
               AND m.role='TENANT_MEMBER'
               AND m.status='ATIVA'
              JOIN m40650.users AS u
                ON u.id=m.user_id AND u.status='ACTIVE'
             WHERE c.scope_name='WRITE_TEST_ENTRY'
               AND c.role_name='TENANT_ADMIN'
               AND c.tenant_id=p_tenant
          )
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


def issue_ticket(auth_dsn: str, key: bytes, session_digest: str,
                 tenant_id, *, nonce=None, expiry=None,
                 scope: str = SCOPE) -> str | None:
    import psycopg
    nonce = nonce or uuid4()
    expiry = expiry or int(datetime.now(timezone.utc).timestamp())+15
    proof = sign_m40700(key,session_digest,tenant_id,nonce,expiry,scope)
    with psycopg.connect(auth_dsn,autocommit=True) as auth:
        auth.execute("SET ROLE m40680_auth")
        return auth.execute(
            "SELECT m40700.issue_bound(%s,%s,%s,%s,%s,%s)",
            (session_digest,tenant_id,nonce,expiry,scope,proof),
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
    print("M41050_APP_CANNOT_READ_CAPABILITY_STORE_OR_ISSUER=PASS")
    print("M41050_RLS_FORCE_AND_SCOPED_EXECUTE=PASS")
    print("M41060_APPEND_ONLY_SELECT_INSERT_ACL=PASS")
    print("M41060_WRITE_RLS_POLICY_PRESENT=PASS")


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
            auth_dsn,key,digest_master,tenant_a
        ) is None
        print("M41050_FORGED_GUCS_WITHOUT_CAPABILITY=DENIED")
        print("M41050_MASTER_SESSION_TICKET=DENIED")

        # Correct tenant-member ticket gives only its own rows, even when all
        # old GUCs claim Master and a different tenant.
        ticket_a=issue_ticket(auth_dsn,key,digest_a,tenant_a)
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
        ticket_admin=issue_ticket(auth_dsn,key,digest_admin,tenant_a)
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
            auth_dsn,key,digest_a,tenant_a,scope=WRITE_SCOPE
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
            auth_dsn,key,digest_admin,tenant_a,scope="WRITE_ANYTHING"
        ) is None
        print("M41060_UNLISTED_SCOPE=DENIED")

        admin_write_ticket=issue_ticket(
            auth_dsn,key,digest_admin,tenant_a,scope=WRITE_SCOPE
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
        race_ticket=issue_ticket(auth_dsn,key,digest_other,tenant_a)
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
        ticket_b=issue_ticket(auth_dsn,key,digest_b,tenant_b)
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
        print("M41050_GATE=NO_GO_UNTIL_KEY_CUSTODY_AND_RUNTIME_ATTESTATION")
        print("M41060_STATUS=PASS_DISPOSABLE_WRITE_RLS_ONLY")


def main() -> int:
    print("=== FR FINANCE M41050 — VÍNCULO DE TICKET, CAPABILITY E RLS ===")
    try:
        dsn=require_disposable()
        run(dsn)
    except Exception as exc:
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
