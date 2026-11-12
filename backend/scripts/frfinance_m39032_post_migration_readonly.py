#!/usr/bin/env python3
"""FR Finance M39032: atestacao READ ONLY de SQL 110+111 ja aplicadas.

Nao reaplica migracoes nem ativa Pix, marketing, FCM, SMS ou webhook.
Roda no Debian com venv PostgreSQL/psycopg ja instalado e PG18 Termux original.
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from frfinance_m39026_credit_only_preflight import (  # noqa: E402
    verify_repo, DB, OWNER, DATA_DIRECTORY, SPECIAL,
)

EXPECTED_POLICIES = {
    "special_credit_grants": {
        "sc_grant_read", "sc_grant_admin_insert", "sc_grant_admin_update",
    },
    "special_credit_campaigns": {
        "sc_campaign_read", "sc_campaign_insert", "sc_campaign_update",
    },
    "special_credit_recipients": {
        "sc_recipient_read", "sc_recipient_insert", "sc_recipient_reply",
    },
    "special_credit_preferences": {
        "sc_pref_read", "sc_pref_write", "sc_pref_update",
    },
    "special_credit_outbox": {"sc_outbox_read", "sc_outbox_insert"},
    "special_credit_audit": {"sc_audit_read", "sc_audit_insert"},
}
EXPECTED_TRIGGERS = {
    "sc_m39020_grant_transition":
        ("special_credit_grants", "sc_m39020_guard_grant_update"),
    "sc_m39020_campaign_transition":
        ("special_credit_campaigns", "sc_m39020_guard_campaign_update"),
    "sc_m39020_recipient_insert":
        ("special_credit_recipients", "sc_m39020_recipient_consistency"),
    "sc_m39020_reply_transition":
        ("special_credit_recipients", "sc_m39020_guard_reply"),
    "sc_m39020_outbox_insert":
        ("special_credit_outbox", "sc_m39020_outbox_consistency"),
}
ALLOWED_UPDATE_COLUMNS = {
    "special_credit_grants": ("status", "updated_at"),
    "special_credit_campaigns": ("status", "published_at"),
    "special_credit_recipients": ("response_status", "responded_at"),
    "special_credit_preferences": ("opted_in", "changed_at"),
}
FORBIDDEN_UPDATE_COLUMNS = {
    "special_credit_grants": ("tenant_id", "cycle_id", "member_id",
                               "ceiling_brl", "reason", "expires_at"),
    "special_credit_campaigns": ("tenant_id", "cycle_id", "created_by",
                                 "title", "body", "expires_at"),
    "special_credit_recipients": ("tenant_id", "campaign_id", "grant_id",
                                  "member_id", "user_id"),
    "special_credit_preferences": ("tenant_id", "user_id", "channel"),
}

def deny(message: str) -> None:
    raise RuntimeError(message)

def audit(conn) -> None:
    """Consulta apenas metadados públicos do catálogo PG18, em READ ONLY."""
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        identity = conn.execute(
            "SELECT current_database(),current_user,session_user,"
            "host(inet_server_addr()),inet_server_port(),"
            "current_setting('data_directory'),"
            "current_setting('server_version_num')::integer"
        ).fetchone()
        if (identity[:3] != (DB, OWNER, OWNER)
            or identity[3] != "127.0.0.1"
            or identity[4] != 5433
            or identity[5] != DATA_DIRECTORY
            or not 180000 <= identity[6] < 190000):
            deny("ORIGINAL_PG18_IDENTITY_MISMATCH")

        count = conn.execute(
            "SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'"
        ).fetchone()[0]
        if count != 53:
            deny("EXPECTED_53_PUBLIC_TABLES_FOUND_" + str(count))

        actual_tables = conn.execute(
            "SELECT c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=ANY(%s)",
            (list(SPECIAL),),
        ).fetchall()
        if len(actual_tables) != 6 or {
            name for name, *_ in actual_tables
        } != set(SPECIAL):
            deny("SPECIAL_CREDIT_TABLES_MISSING")
        if any(kind != 'r' or not rls or not force
               for _, kind, rls, force in actual_tables):
            deny("SPECIAL_CREDIT_RLS_NOT_FORCED")

        policy_rows = conn.execute(
            "SELECT tablename,policyname FROM pg_policies "
            "WHERE schemaname='public' AND tablename=ANY(%s)",
            (list(SPECIAL),),
        ).fetchall()
        actual_policies = {name: set() for name in SPECIAL}
        for table, policy in policy_rows:
            if policy in actual_policies[table]:
                deny("DUPLICATE_POLICY_" + table)
            actual_policies[table].add(policy)
        if actual_policies != EXPECTED_POLICIES:
            deny("POLICY_SET_DRIFT")

        trigger_rows = conn.execute(
            "SELECT c.relname,t.tgname,t.tgenabled,p.proname,fn.nspname "
            "FROM pg_trigger t "
            "JOIN pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "JOIN pg_proc p ON p.oid=t.tgfoid "
            "JOIN pg_namespace fn ON fn.oid=p.pronamespace "
            "WHERE n.nspname='public' AND c.relname=ANY(%s) "
            "AND NOT t.tgisinternal AND t.tgname LIKE 'sc_m39020_%%'",
            (list(SPECIAL),),
        ).fetchall()
        if len(trigger_rows) != len(EXPECTED_TRIGGERS):
            deny("EXPECTED_FIVE_TRIGGER_GUARDS")
        seen = set()
        for table, name, enabled, function, schema in trigger_rows:
            if name in seen or enabled != "O" or schema != "public" or (
                table, function
            ) != EXPECTED_TRIGGERS.get(name):
                deny("TRIGGER_OR_FUNCTION_DRIFT")
            seen.add(name)
        if seen != set(EXPECTED_TRIGGERS):
            deny("TRIGGER_GUARDS_MISSING")

        roles = conn.execute(
            "SELECT rolname,rolsuper,rolbypassrls FROM pg_roles "
            "WHERE rolname IN ('frc_ai_app','frc_ai_auth')"
        ).fetchall()
        if len(roles) != 2 or any(superuser or bypass for _, superuser, bypass in roles):
            deny("RUNTIME_ROLE_PRIVILEGE_DRIFT")

        for table in SPECIAL:
            table_id = "public." + table
            select_ok, insert_ok, delete_ok, update_ok = conn.execute(
                "SELECT has_table_privilege('frc_ai_app',%s,'SELECT'),"
                "has_table_privilege('frc_ai_app',%s,'INSERT'),"
                "has_table_privilege('frc_ai_app',%s,'DELETE'),"
                "has_table_privilege('frc_ai_app',%s,'UPDATE')",
                (table_id,)*4,
            ).fetchone()
            if not select_ok or not insert_ok or delete_ok or update_ok:
                deny("TABLE_PRIVILEGE_DRIFT_" + table)
            for column in ALLOWED_UPDATE_COLUMNS.get(table, ()):
                permitted = conn.execute(
                    "SELECT has_column_privilege('frc_ai_app',%s,%s,'UPDATE')",
                    (table_id, column),
                ).fetchone()[0]
                if not permitted:
                    deny("ALLOWED_COLUMN_UPDATE_MISSING_" + table + "_" + column)
            for column in FORBIDDEN_UPDATE_COLUMNS.get(table, ()):
                permitted = conn.execute(
                    "SELECT has_column_privilege('frc_ai_app',%s,%s,'UPDATE')",
                    (table_id, column),
                ).fetchone()[0]
                if permitted:
                    deny("FORBIDDEN_COLUMN_UPDATE_" + table + "_" + column)

        default_state = conn.execute(
            "SELECT pg_get_expr(d.adbin,d.adrelid) "
            "FROM pg_attrdef d JOIN pg_attribute a "
            "ON a.attrelid=d.adrelid AND a.attnum=d.adnum "
            "WHERE d.adrelid='public.special_credit_outbox'::regclass "
            "AND a.attname='state'"
        ).fetchone()
        if not default_state or "'BLOCKED_EXTERNAL'" not in default_state[0]:
            deny("EXTERNAL_OUTBOX_DEFAULT_NOT_BLOCKED")
        checks = [
            row[0] for row in conn.execute(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
                "WHERE conrelid='public.special_credit_outbox'::regclass "
                "AND contype='c'"
            ).fetchall()
        ]
        if not any(
            "BLOCKED_EXTERNAL" in condition
            and "DISPATCH_REVIEW" in condition
            and "CANCELLED" in condition
            and "'SENT'" not in condition
            for condition in checks
        ):
            deny("EXTERNAL_OUTBOX_STATE_CONSTRAINT_UNSAFE")

        print("M39032_IDENTITY=PG18_ORIGINAL_PASS")
        print("M39032_TABLES_PUBLIC=53")
        print("M39032_SPECIAL_TABLES=6_OF_6")
        print("M39032_FORCE_RLS=6_OF_6")
        print("M39032_POLICIES=16_OF_16")
        print("M39032_TRIGGERS=5_OF_5")
        print("M39032_RUNTIME_ROLE_ISOLATION=PASS")
        print("M39032_TABLE_AND_COLUMN_PRIVILEGES=PASS")
        print("M39032_EXTERNAL_OUTBOX=BLOCKED_EXTERNAL")
        print("M39032_DATABASE_WRITES=NONE")
        print("M39032_SQL110_111=ALREADY_APPLIED_DO_NOT_REPEAT")
        print("M39032_STATUS=PASS")

def main() -> int:
    print("=== FR FINANCE M39032 — POST-MIGRATION READ ONLY ===")
    try:
        verify_repo()
    except Exception:
        print("M39032_STATUS=BLOCKED_REPOSITORY_CHECK")
        return 2
    try:
        import psycopg
    except ImportError:
        print("M39032_STATUS=BLOCKED_USE_EXISTING_PYTHON_VENV")
        return 2
    password = getpass.getpass("Senha frc_ai_owner (oculta): ")
    if not password:
        print("M39032_STATUS=BLOCKED_NO_DB_PASSWORD")
        return 2
    try:
        with psycopg.connect(
            host="127.0.0.1", port=5433, dbname=DB, user=OWNER,
            password=password, connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=12000 -c lock_timeout=2000",
        ) as conn:
            del password
            audit(conn)
        return 0
    except RuntimeError as e:
        print("M39032_STATUS=BLOCKED")
        print("M39032_REASON=" + str(e))
        print("M39032_DATABASE_WRITES=NONE")
        return 2
    except Exception:
        print("M39032_STATUS=BLOCKED_DATABASE_AUDIT")
        print("M39032_DATABASE_WRITES=NONE")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
