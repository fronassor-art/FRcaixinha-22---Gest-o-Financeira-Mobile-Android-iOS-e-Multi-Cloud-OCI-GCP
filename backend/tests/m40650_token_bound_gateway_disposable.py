#!/usr/bin/env python3
"""M40650: isolated PG18 proof for an opaque-token, SQL-function-only read gateway.

This is an experimental CI fixture, NOT a migration, application integration,
deployed credential, RLS replacement or claim that existing GUC spoofing is fixed.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import os
import secrets
import sys
from urllib.parse import urlsplit
from uuid import uuid4

DB = "fr_m40650_disposable_ci"
PORT = 55435
GATE = "m40650.read_entries(text,uuid)"


def require_disposable() -> None:
    expected = {
        "GITHUB_ACTIONS": "true",
        "CI_M40650_DISPOSABLE": "1",
        "FRCAIXINHA_CI_ISOLATED": "1",
        "PIX_REAL": "OFF",
        "PAGAMENTOS_REAIS": "OFF",
        "ATIVACAO_REAL": "OFF",
    }
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise RuntimeError("M40650_DISPOSABLE_ONLY")
    try:
        url = urlsplit(os.environ.get("CI_M40650_DATABASE_URL", ""))
        if (url.scheme != "postgresql" or url.hostname != "127.0.0.1"
                or url.port != PORT or url.path != "/" + DB
                or url.username != "postgres" or not url.password
                or url.query or url.fragment):
            raise RuntimeError("M40650_WRONG_DATABASE_IDENTITY")
    except (ValueError, AttributeError) as exc:
        raise RuntimeError("M40650_WRONG_DATABASE_IDENTITY") from exc


def schema(conn) -> None:
    # All DDL is synthetic and permitted exclusively in the disposable CI DB.
    conn.execute("CREATE ROLE m40650_owner NOLOGIN NOINHERIT NOBYPASSRLS")
    conn.execute("CREATE ROLE m40650_app NOLOGIN NOINHERIT NOBYPASSRLS")
    conn.execute("CREATE SCHEMA m40650 AUTHORIZATION m40650_owner")
    conn.execute("REVOKE ALL ON SCHEMA m40650 FROM PUBLIC")
    conn.execute("GRANT USAGE ON SCHEMA m40650 TO m40650_app")
    conn.execute("""
        CREATE TABLE m40650.sessions (
          token_digest text PRIMARY KEY,
          user_id uuid NOT NULL,
          active_role text NOT NULL,
          active_tenant_id uuid,
          expires_at timestamptz NOT NULL,
          revoked_at timestamptz
        )
    """)
    conn.execute("""
        CREATE TABLE m40650.memberships (
          user_id uuid NOT NULL,
          tenant_id uuid NOT NULL,
          role text NOT NULL,
          status text NOT NULL,
          PRIMARY KEY (user_id, tenant_id, role)
        )
    """)
    conn.execute("""
        CREATE TABLE m40650.entries (
          id uuid PRIMARY KEY, tenant_id uuid NOT NULL,
          user_id uuid NOT NULL, amount numeric(12,2) NOT NULL
        )
    """)
    for table in ("sessions", "memberships", "entries"):
        conn.execute(f"ALTER TABLE m40650.{table} OWNER TO m40650_owner")
    conn.execute("REVOKE ALL ON ALL TABLES IN SCHEMA m40650 FROM PUBLIC, m40650_app")
    conn.execute("""
        CREATE FUNCTION m40650.read_entries(p_token text, p_tenant uuid)
        RETURNS TABLE(entry_id uuid, tenant_id uuid, amount numeric)
        LANGUAGE plpgsql SECURITY DEFINER
        SET search_path = pg_catalog, pg_temp
        AS $body$
        DECLARE
            v_user uuid;
            v_role text;
        BEGIN
            IF p_token IS NULL OR length(p_token) < 32 OR p_tenant IS NULL THEN
                RETURN;
            END IF;
            -- No client-controlled custom GUC provides authentication here.
            SELECT s.user_id, s.active_role INTO v_user, v_role
            FROM m40650.sessions AS s
            JOIN m40650.memberships AS m
              ON m.user_id = s.user_id
             AND m.tenant_id = s.active_tenant_id
             AND m.role = s.active_role
             AND m.status = 'ATIVA'
            WHERE s.token_digest =
                  pg_catalog.encode(
                    pg_catalog.sha256(pg_catalog.convert_to(p_token, 'UTF8')),
                    'hex')
              AND s.expires_at > pg_catalog.clock_timestamp()
              AND s.revoked_at IS NULL
              AND s.active_role IN ('TENANT_MEMBER', 'TENANT_ADMIN')
              AND s.active_tenant_id = p_tenant;
            IF NOT FOUND THEN
                RETURN;
            END IF;
            RETURN QUERY
              SELECT e.id, e.tenant_id, e.amount
              FROM m40650.entries AS e
              WHERE e.tenant_id = p_tenant
                AND (v_role = 'TENANT_ADMIN' OR e.user_id = v_user)
              ORDER BY e.id;
        END;
        $body$
    """)
    conn.execute("ALTER FUNCTION m40650.read_entries(text,uuid) OWNER TO m40650_owner")
    conn.execute("REVOKE ALL ON FUNCTION m40650.read_entries(text,uuid) FROM PUBLIC")
    conn.execute("GRANT EXECUTE ON FUNCTION m40650.read_entries(text,uuid) TO m40650_app")


def expect_denied(conn, query: str, params: tuple = ()) -> None:
    import psycopg
    try:
        with conn.transaction():
            conn.execute(query, params)
    except psycopg.Error as exc:
        if exc.sqlstate != "42501":
            raise AssertionError("M40650_UNEXPECTED_SQLSTATE") from exc
    else:
        raise AssertionError("M40650_UNAUTHORIZED_SQL_ALLOWED")


def proof(conn) -> None:
    schema(conn)
    member_a, member_b, admin_a, member_c, master = [uuid4() for _ in range(5)]
    tenant_a, tenant_b = uuid4(), uuid4()
    entries = [(uuid4(), tenant_a, member_a, 120),
               (uuid4(), tenant_a, member_b, 240),
               (uuid4(), tenant_b, member_c, 360)]
    now = datetime.now(timezone.utc)

    for user, tenant, role, status in (
        (member_a, tenant_a, "TENANT_MEMBER", "ATIVA"),
        (member_b, tenant_a, "TENANT_MEMBER", "ATIVA"),
        (admin_a, tenant_a, "TENANT_ADMIN", "ATIVA"),
        (member_c, tenant_b, "TENANT_MEMBER", "ATIVA"),
        (master, tenant_a, "TENANT_MEMBER", "ATIVA"),
    ):
        conn.execute("INSERT INTO m40650.memberships VALUES (%s,%s,%s,%s)",
                     (user, tenant, role, status))

    for item in entries:
        conn.execute("INSERT INTO m40650.entries VALUES (%s,%s,%s,%s)", item)

    tokens: dict[str, str] = {}
    for name, user, role, tenant, expiry, revoked in (
        ("member_a", member_a, "TENANT_MEMBER", tenant_a, now + timedelta(hours=1), None),
        ("member_b", member_b, "TENANT_MEMBER", tenant_a, now + timedelta(hours=1), None),
        ("admin_a", admin_a, "TENANT_ADMIN", tenant_a, now + timedelta(hours=1), None),
        ("member_c", member_c, "TENANT_MEMBER", tenant_b, now + timedelta(hours=1), None),
        ("master", master, "MASTER", None, now + timedelta(hours=1), None),
        ("expired", member_a, "TENANT_MEMBER", tenant_a, now - timedelta(hours=1), None),
        ("revoked", member_a, "TENANT_MEMBER", tenant_a, now + timedelta(hours=1), now),
    ):
        token = secrets.token_urlsafe(40)
        tokens[name] = token
        conn.execute(
            "INSERT INTO m40650.sessions VALUES (%s,%s,%s,%s,%s,%s)",
            (sha256(token.encode("utf-8")).hexdigest(), user, role, tenant, expiry, revoked),
        )

    conn.execute("SET ROLE m40650_app")
    assert conn.execute("SELECT current_user").fetchone()[0] == "m40650_app"
    attributes = conn.execute(
        "SELECT rolsuper,rolbypassrls,rolcreaterole,rolcreatedb,rolcanlogin "
        "FROM pg_catalog.pg_roles WHERE rolname='m40650_app'"
    ).fetchone()
    assert attributes == (False, False, False, False, False)
    assert not conn.execute(
        "SELECT pg_catalog.pg_has_role('m40650_app','m40650_owner','MEMBER')"
    ).fetchone()[0]

    for table in ("sessions", "memberships", "entries"):
        assert not conn.execute(
            "SELECT pg_catalog.has_table_privilege('m40650_app',%s,'SELECT')",
            ("m40650." + table,),
        ).fetchone()[0]
        expect_denied(conn, f"SELECT * FROM m40650.{table}")
    expect_denied(conn, "UPDATE m40650.sessions SET revoked_at=NULL")
    expect_denied(conn, "SET ROLE m40650_owner")
    print("M40650_DIRECT_TABLE_AND_OWNER_ESCALATION=DENIED")

    def visible(token: str, tenant) -> set:
        rows = conn.execute(
            "SELECT entry_id FROM m40650.read_entries(%s,%s)", (token, tenant)
        ).fetchall()
        return {row[0] for row in rows}

    assert visible(tokens["member_a"], tenant_a) == {entries[0][0]}
    assert visible(tokens["member_b"], tenant_a) == {entries[1][0]}
    assert visible(tokens["admin_a"], tenant_a) == {entries[0][0], entries[1][0]}
    assert visible(tokens["member_c"], tenant_b) == {entries[2][0]}
    assert visible(tokens["member_a"], tenant_b) == set()
    assert visible(tokens["admin_a"], tenant_b) == set()
    assert visible(tokens["master"], tenant_a) == set()
    assert visible(tokens["expired"], tenant_a) == set()
    assert visible(tokens["revoked"], tenant_a) == set()
    assert visible(secrets.token_urlsafe(40), tenant_a) == set()
    print("M40650_TOKEN_ROLE_MEMBERSHIP_TENANT_DENIAL=PASS")

    # The application role can spoof custom GUCs but cannot use them to widen
    # the fixed SECURITY DEFINER function's token-scoped results.
    for key, value in (
        ("app.current_role", "MASTER"),
        ("app.current_user_id", str(admin_a)),
        ("app.current_tenant_id", str(tenant_b)),
    ):
        conn.execute("SELECT pg_catalog.set_config(%s,%s,false)", (key, value))
    assert visible(tokens["member_a"], tenant_a) == {entries[0][0]}
    assert visible(tokens["member_a"], tenant_b) == set()
    assert visible(tokens["admin_a"], tenant_a) == {entries[0][0], entries[1][0]}
    print("M40650_SYNTHETIC_GUC_SPOOF_CANNOT_WIDEN_GATEWAY=PASS")

    conn.execute("SET search_path = pg_temp, public, m40650")
    conn.execute("CREATE TEMP TABLE entries (id uuid, tenant_id uuid, amount numeric)")
    assert visible(tokens["member_a"], tenant_a) == {entries[0][0]}
    print("M40650_SEARCH_PATH_TEMP_SHADOW=DENIED")

    conn.execute("RESET ROLE")
    conn.execute(
        "UPDATE m40650.memberships SET status='DESLIGADA' "
        "WHERE user_id=%s AND tenant_id=%s",
        (member_a, tenant_a),
    )
    conn.execute("SET ROLE m40650_app")
    assert visible(tokens["member_a"], tenant_a) == set()
    assert visible(tokens["admin_a"], tenant_a) == {entries[0][0], entries[1][0]}
    print("M40650_REVOKED_MEMBERSHIP_ACCESS=DENIED")
    conn.execute("RESET ROLE")
    print("M40650_EXISTING_APPLICATION_RLS=NOT_REMEDIATED")
    print("M40650_PROPOSED_GATEWAY=ISOLATED_PROTOTYPE_ONLY")
    print("M40650_HTTP_BEARER_INTEGRATION=NOT_TESTED")


def main() -> int:
    print("=== FR FINANCE M40650 — OPAQUE TOKEN GATEWAY DISPOSABLE PG18 ===")
    try:
        require_disposable()
        # Strict CI identity gate is evaluated before any driver import/connection.
        import psycopg
        with psycopg.connect(os.environ["CI_M40650_DATABASE_URL"], autocommit=True) as conn:
            proof(conn)
    except Exception as exc:
        print("M40650_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40650_ORIGINAL_PG_5433=NOT_ACCESSED")
        print("M40650_LOCAL_MIGRATIONS=NONE")
        print("M40650_LOCAL_DB_WRITES=NONE")
        print("M40650_SERVICE_RESTARTS=NONE")
        print("M40650_PIX_REAL=OFF")
        print("M40650_PAGAMENTOS_REAIS=OFF")
        print("M40650_ATIVACAO_REAL=OFF")
        print("M40650_PRODUCTION=BLOCKED")
    print("M40650_STATUS=PASS_ISOLATED_PROTOTYPE_ONLY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
