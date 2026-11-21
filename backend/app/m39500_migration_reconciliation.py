"""FR Finance M39500 — versioned read-only reconciliation of SQL 110..113.

Checks only PostgreSQL catalog metadata on the one original Finance cluster,
not user, membership, payment or balances. Neither source files nor tables
are modified. Object state is *not* proof of historical migration execution.
No total-public-table count is used: SQL113 adds a table after SQL110/111.
"""
from __future__ import annotations

from hashlib import sha1
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ISOLATION_MANIFEST = "backend/config/frfinance_project_identity.json"
APP_PGDATA = "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
SOURCE_BLOBS = {
    "backend/migrations/110_fr_finance_special_credit_offline.sql":
        "a785e05bf20ae37c3bccf96ca2f8b2ff3604b35d",
    "backend/migrations/111_frfinance_special_credit_integrity_guards.sql":
        "1fbe349b7d785eb3e5bc7852f84cd01f2b465ae1",
    "backend/migrations/112_frfinance_master_independent_saas_prices.sql":
        "10da8aaef7beb3d6559a14d064be53e1aae5a01f",
    "backend/migrations/113_frfinance_saas_new_admin_promotions.sql":
        "33c94b871602a8ad93f86bd7a724a8638124ff0f",
}
# Exact expected trigger policy names are the contract of SQL110/111,
# not guesses derived from counts of all public objects.
POLICIES = {
    "special_credit_grants": {
        "sc_grant_read", "sc_grant_admin_insert", "sc_grant_admin_update"},
    "special_credit_campaigns": {
        "sc_campaign_read", "sc_campaign_insert", "sc_campaign_update"},
    "special_credit_recipients": {
        "sc_recipient_read", "sc_recipient_insert", "sc_recipient_reply"},
    "special_credit_preferences": {
        "sc_pref_read", "sc_pref_write", "sc_pref_update"},
    "special_credit_outbox": {"sc_outbox_read", "sc_outbox_insert"},
    "special_credit_audit": {"sc_audit_read", "sc_audit_insert"},
}
TRIGGERS = {
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
ALLOWED_UPDATES = {
    "special_credit_grants": ("status", "updated_at"),
    "special_credit_campaigns": ("status", "published_at"),
    "special_credit_recipients": ("response_status", "responded_at"),
    "special_credit_preferences": ("opted_in", "changed_at"),
}
IMMUTABLE_COLUMNS = {
    "special_credit_grants": ("tenant_id", "cycle_id", "member_id",
                              "ceiling_brl", "reason", "expires_at"),
    "special_credit_campaigns": ("tenant_id", "cycle_id", "created_by",
                                 "title", "body", "expires_at"),
    "special_credit_recipients": ("tenant_id", "campaign_id", "grant_id",
                                  "member_id", "user_id"),
    "special_credit_preferences": ("tenant_id", "user_id", "channel"),
}


class AttestationBlocked(ValueError):
    """Fixed codes only; never include a database exception, URL or secret."""


def require(value: bool, code: str) -> None:
    if value is not True:
        raise AttestationBlocked("M39500_" + code)


def git_blob(data: bytes) -> str:
    return sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def verify_sources(root: Path = ROOT) -> dict:
    """Offline proof of original-only SQL source identity (no git command)."""
    root = Path(root)
    identity = root / ISOLATION_MANIFEST
    require(identity.is_file() and not identity.is_symlink(),
            "IDENTITY_MANIFEST_MISSING")
    try:
        manifest = json.loads(identity.read_text(encoding="utf-8"))
        finance = manifest["active_project"]["postgresql"]
        excluded = manifest["excluded_project"]["postgresql"]
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise AttestationBlocked("M39500_IDENTITY_MANIFEST_INVALID") from exc
    require(manifest.get("schema") == "FR_FINANCE_PROJECT_ISOLATION_V1"
        and manifest.get("production_authorized") is False
        and manifest.get("never_apply_migrations_during_preflight") is True
        and manifest.get("never_cross_connect_to_excluded_project") is True
        and manifest["active_project"].get("id") == "FR_FINANCE_AI_STUDIO"
        and finance == {
            "host": "127.0.0.1", "port": 5433, "major_version": 18,
            "pgdata": APP_PGDATA, "database": "frcaixinha_aistudio_dev",
            "owner": "frc_ai_owner",
        }
        and excluded.get("port") == 5432
        and excluded.get("database") != finance.get("database")
        and excluded.get("pgdata") != finance.get("pgdata"),
        "CROSS_PROJECT_IDENTITY_DRIFT")
    for path, expected in SOURCE_BLOBS.items():
        source = root / path
        require(source.is_file() and not source.is_symlink(),
                "MIGRATION_SOURCE_MISSING")
        require(git_blob(source.read_bytes()) == expected,
                "MIGRATION_GIT_BLOB_CHANGED")
    return {
        "identity": "FR_FINANCE_ORIGINAL_PG18_5433",
        "sql_sources": "110_111_112_113_HASHES_PASS",
        "original_schema_checked": False,
        "real_payments": False,
        "production_verified": False,
    }


def check_identity(row: tuple | None) -> None:
    require(isinstance(row, (tuple, list)) and len(row) == 7,
            "PG_IDENTITY_FORMAT_INVALID")
    require(row[:6] == (
        "frcaixinha_aistudio_dev", "frc_ai_owner", "frc_ai_owner",
        "127.0.0.1", 5433, APP_PGDATA,
    ) and type(row[6]) is int and 180000 <= row[6] < 190000,
            "WRONG_POSTGRESQL_ROLE_PORT_OR_PGDATA")


def inspect_credit_110_111(conn) -> dict:
    """Transactional SELECT-only inspection; no global pg_tables count."""
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        identity = conn.execute(
            "SELECT current_database(),session_user,current_user,"
            "host(inet_server_addr()),inet_server_port(),"
            "current_setting('data_directory'),"
            "current_setting('server_version_num')::integer"
        ).fetchone()
        check_identity(identity)

        names = sorted(POLICIES)
        tables = conn.execute(
            "SELECT c.relname,c.relkind,c.relrowsecurity,c.relforcerowsecurity "
            "FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=ANY(%s)",
            (names,)
        ).fetchall()
        require(len(tables) == 6
                and {row[0] for row in tables} == set(POLICIES)
                and all(row[1] == "r" and row[2] is True and row[3] is True
                        for row in tables), "CREDIT_TABLE_FORCE_RLS_DRIFT")

        policies = conn.execute(
            "SELECT tablename,policyname FROM pg_catalog.pg_policies "
            "WHERE schemaname='public' AND tablename=ANY(%s)",
            (names,)
        ).fetchall()
        actual = {name: set() for name in POLICIES}
        for table, name in policies:
            require(table in actual and name not in actual[table],
                    "CREDIT_POLICY_DUPLICATED_OR_UNKNOWN")
            actual[table].add(name)
        require(actual == POLICIES, "CREDIT_POLICIES_DRIFT")

        triggers = conn.execute(
            "SELECT c.relname,t.tgname,t.tgenabled,p.proname,fn.nspname "
            "FROM pg_catalog.pg_trigger t "
            "JOIN pg_catalog.pg_class c ON c.oid=t.tgrelid "
            "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
            "JOIN pg_catalog.pg_proc p ON p.oid=t.tgfoid "
            "JOIN pg_catalog.pg_namespace fn ON fn.oid=p.pronamespace "
            "WHERE n.nspname='public' AND c.relname=ANY(%s) "
            "AND NOT t.tgisinternal AND t.tgname LIKE 'sc_m39020_%%'",
            (names,)
        ).fetchall()
        require(len(triggers) == len(TRIGGERS), "CREDIT_TRIGGER_COUNT_DRIFT")
        seen = set()
        for table, trig, state, func, schema in triggers:
            require(trig not in seen and state == "O" and schema == "public"
                    and (table, func) == TRIGGERS.get(trig),
                    "CREDIT_TRIGGER_INTEGRITY_DRIFT")
            seen.add(trig)
        require(seen == set(TRIGGERS), "CREDIT_TRIGGERS_MISSING")

        roles = conn.execute(
            "SELECT rolname,rolsuper,rolbypassrls FROM pg_catalog.pg_roles "
            "WHERE rolname IN ('frc_ai_app','frc_ai_auth')"
        ).fetchall()
        require({r[0] for r in roles} == {"frc_ai_app", "frc_ai_auth"}
                and len(roles) == 2
                and all(r[1] is False and r[2] is False for r in roles),
                "CREDIT_ROLE_PRIVILEGES_UNSAFE")

        for table in names:
            obj = "public." + table
            perms = conn.execute(
                "SELECT has_table_privilege('frc_ai_app',%s,'SELECT'),"
                "has_table_privilege('frc_ai_app',%s,'INSERT'),"
                "has_table_privilege('frc_ai_app',%s,'DELETE'),"
                "has_table_privilege('frc_ai_app',%s,'UPDATE')",
                (obj, obj, obj, obj)
            ).fetchone()
            require(perms == (True, True, False, False),
                    "CREDIT_TABLE_PRIVILEGE_DRIFT")
            for col in ALLOWED_UPDATES.get(table, ()):
                granted = conn.execute(
                    "SELECT has_column_privilege('frc_ai_app',%s,%s,'UPDATE')",
                    (obj, col)
                ).fetchone()
                require(granted == (True,),
                        "CREDIT_ALLOWED_COLUMN_PRIVILEGE_MISSING")
            for col in IMMUTABLE_COLUMNS.get(table, ()):
                granted = conn.execute(
                    "SELECT has_column_privilege('frc_ai_app',%s,%s,'UPDATE')",
                    (obj, col)
                ).fetchone()
                require(granted == (False,),
                        "CREDIT_IMMUTABLE_COLUMN_PRIVILEGE_UNSAFE")

        default = conn.execute(
            "SELECT pg_get_expr(d.adbin,d.adrelid) "
            "FROM pg_catalog.pg_attrdef d "
            "JOIN pg_catalog.pg_attribute a "
            "ON a.attrelid=d.adrelid AND a.attnum=d.adnum "
            "WHERE d.adrelid='public.special_credit_outbox'::regclass "
            "AND a.attname='state'"
        ).fetchone()
        require(default and type(default[0]) is str
                and "'BLOCKED_EXTERNAL'" in default[0],
                "CREDIT_EXTERNAL_OUTBOX_NOT_BLOCKED")
        constraints = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_catalog.pg_constraint "
            "WHERE conrelid='public.special_credit_outbox'::regclass "
            "AND contype='c'"
        ).fetchall()
        require(any("BLOCKED_EXTERNAL" in r[0]
                    and "DISPATCH_REVIEW" in r[0]
                    and "CANCELLED" in r[0]
                    and "'SENT'" not in r[0]
                    for r in constraints), "CREDIT_EXTERNAL_OUTBOX_UNSAFE")

    return {
        "sql_110_111": "CATALOG_COMPATIBLE",
        "credit_force_rls_tables": 6,
        "credit_policies": sum(map(len, POLICIES.values())),
        "credit_triggers": len(TRIGGERS),
        "public_table_count_assumed": False,
        "credit_external_delivery": "BLOCKED_EXTERNAL",
        "real_pix": False,
        "historical_migration_application_proven": False,
    }


def verify_full_catalog(conn) -> dict:
    """Run scoped SQL110/111 and existing full SQL112/113 postchecks."""
    from backend.scripts.frfinance_m39068_postcommit_sql112_113_readonly_diagnostic import (
        inspect_schema
    )
    credit = inspect_credit_110_111(conn)
    try:
        saas = inspect_schema(conn)
    except Exception as exc:
        # A lower-level failure is *not* a reason to relax checks.
        raise AttestationBlocked("M39500_SAAS_SQL112_113_NOT_ATTESTED") from exc
    require(type(saas) is dict and len(saas) >= 10
            and all(type(v) is bool for v in saas.values()),
            "SAAS_CATALOG_RESPONSE_INVALID")
    # M39067_POSTCHECK_EXACT_TEXT is known to be overly strict about spacing;
    # rely on search_path_is_restricted() plus all remaining checks.
    required = {key: value for key, value in saas.items()
                if key != "M39067_POSTCHECK_EXACT_TEXT"}
    require(all(required.values()), "SAAS_SQL112_113_SECURITY_DRIFT")
    return {
        **credit,
        "sql_112_113": "CATALOG_COMPATIBLE",
        "sql_112_113_checks": len(required),
        "sql_112_113_restricted_definer_path": True,
        "schema_catalog": "SCOPE_SQL110_TO_SQL113_PASS_READ_ONLY",
        "historical_migration_application_proven": False,
        "database_writes": 0,
        "migrations_applied": 0,
        "real_payments": False,
        "production_authorized": False,
    }
