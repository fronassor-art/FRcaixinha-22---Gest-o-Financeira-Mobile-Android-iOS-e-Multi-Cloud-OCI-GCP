#!/usr/bin/env python3
"""FR Finance M38701-M38790: opt-in read-only catalog audit, no DB migrations.

Checks only PostgreSQL pg_catalog metadata of the existing Termux DB at
127.0.0.1:5433. Never queries rows in financial/business tables.
A matching schema is NOT proof that migration 043/044 was applied.
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import subprocess
import sys

HOST = "127.0.0.1"
PORT = "5433"
DATABASE = "frcaixinha_aistudio_dev"
USER = "frc_ai_owner"
AUTHORIZE = "AUTHORIZE_PG18_043_044_CATALOG_READ_ONLY"
EXPECTED_PGDATA = "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
FIELDS = (
    "DB_TARGET_OK",
    "M043_POLICY_FLOOR",
    "M043_QUOTA_FLOOR",
    "M043_NO_DEFAULTS",
    "M043_WRAPPER_FLOOR",
    "M043_LEGACY_RESTRICTED",
    "M044_AUDIT_RLS",
    "M044_IMMUTABLE_TRIGGERS",
    "M044_CREATE_FLOOR",
    "M044_ROLE_BOUNDARY",
    "M044_UNIQUE_REPLAY",
)
FLOOR_043 = FIELDS[1:6]
FLOOR_044 = FIELDS[6:]

# The SELECT text and target are fixed; inputs do not interpolate into SQL.
# READ ONLY + pg_catalog only: no user data, no functions executed.
QUERY = r"""
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '5s';
SET LOCAL lock_timeout = '2s';
WITH evidence AS (
SELECT
  (
    current_database() = 'frcaixinha_aistudio_dev'
    AND current_user = 'frc_ai_owner'
    AND session_user = 'frc_ai_owner'
    AND inet_server_port() = 5433
    AND current_setting('data_directory', true) =
      '/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18'
    AND current_setting('server_version_num')::int BETWEEN 180000 AND 189999
  ) AS db_target_ok,
  EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint c
    WHERE c.conrelid = to_regclass('public.policies')
      AND c.conname = 'policy_minimum_150_new' AND c.contype = 'c'
      AND regexp_replace(pg_get_constraintdef(c.oid), '[[:space:]]', '', 'g')
        LIKE '%contribution_per_quota>=150%'
  ) AS policy_floor,
  EXISTS (
    SELECT 1 FROM pg_catalog.pg_constraint c
    WHERE c.conrelid = to_regclass('public.quotas')
      AND c.conname = 'quota_minimum_150_new' AND c.contype = 'c'
      AND regexp_replace(pg_get_constraintdef(c.oid), '[[:space:]]', '', 'g')
        LIKE '%value_brl>=150%'
  ) AS quota_floor,
  (
    to_regclass('public.policies') IS NOT NULL
    AND to_regclass('public.quotas') IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM pg_catalog.pg_attribute a
      JOIN pg_catalog.pg_attrdef d
        ON d.adrelid = a.attrelid AND d.adnum = a.attnum
      WHERE (a.attrelid = to_regclass('public.policies')
              AND a.attname = 'contribution_per_quota')
         OR (a.attrelid = to_regclass('public.quotas')
              AND a.attname = 'value_brl')
    )
  ) AS no_defaults,
  EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    WHERE p.oid = to_regprocedure(
      'public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)')
      AND p.prosecdef
      AND position('NOT BETWEEN 15000 AND 1000000'
                   in pg_get_functiondef(p.oid)) > 0
      AND position('cycle_price_change_legacy_m20400'
                   in pg_get_functiondef(p.oid)) > 0
  ) AS wrapper_floor,
  CASE WHEN
      EXISTS (SELECT 1 FROM pg_catalog.pg_roles
              WHERE rolname = 'frcaixinha_app_role')
      AND to_regprocedure(
        'public.cycle_price_change_legacy_m20400(text,uuid,uuid,bigint,text,uuid)'
      ) IS NOT NULL
      AND to_regprocedure(
        'public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)'
      ) IS NOT NULL
    THEN
      NOT has_function_privilege(
        'frcaixinha_app_role',
        'public.cycle_price_change_legacy_m20400(text,uuid,uuid,bigint,text,uuid)',
        'EXECUTE'
      )
      AND has_function_privilege(
        'frcaixinha_app_role',
        'public.cycle_price_change(text,uuid,uuid,bigint,text,uuid)', 'EXECUTE'
      )
    ELSE FALSE END AS legacy_restricted,
  EXISTS (
    SELECT 1 FROM pg_catalog.pg_class c
    WHERE c.oid = to_regclass('public.cycle_opening_audit')
      AND c.relkind = 'r'
      AND c.relrowsecurity AND c.relforcerowsecurity
  ) AS audit_rls,
  (
    SELECT count(*) = 2
    FROM pg_catalog.pg_trigger t
    WHERE t.tgrelid = to_regclass('public.cycle_opening_audit')
      AND t.tgenabled = 'O'
      AND t.tgname IN (
        'cycle_opening_immutable_row', 'cycle_opening_immutable_truncate')
  ) AS immutable_triggers,
  EXISTS (
    SELECT 1 FROM pg_catalog.pg_proc p
    WHERE p.oid = to_regprocedure(
      'public.cycle_open_create(text,uuid,integer,bigint,text,uuid)')
      AND p.prosecdef
      AND position('p_amount_cents NOT BETWEEN 15000 AND 1000000'
                   in pg_get_functiondef(p.oid)) > 0
      AND position('cycle_price_admin_actor'
                   in pg_get_functiondef(p.oid)) > 0
      AND position('p_amount_cents::numeric/100'
                   in pg_get_functiondef(p.oid)) > 0
  ) AS create_floor,
  CASE WHEN
      EXISTS (SELECT 1 FROM pg_catalog.pg_roles
              WHERE rolname = 'frcaixinha_app_role')
      AND EXISTS (SELECT 1 FROM pg_catalog.pg_roles
                  WHERE rolname = 'frcaixinha_auth_role')
      AND to_regprocedure(
        'public.cycle_open_create(text,uuid,integer,bigint,text,uuid)'
      ) IS NOT NULL
    THEN
      has_function_privilege(
        'frcaixinha_app_role',
        'public.cycle_open_create(text,uuid,integer,bigint,text,uuid)',
        'EXECUTE'
      )
      AND NOT has_function_privilege(
        'frcaixinha_auth_role',
        'public.cycle_open_create(text,uuid,integer,bigint,text,uuid)',
        'EXECUTE'
      )
      AND NOT has_table_privilege(
        'frcaixinha_app_role', 'public.cycle_opening_audit', 'INSERT'
      )
    ELSE FALSE END AS role_boundary,
  (
    SELECT count(*) = 2 FROM pg_catalog.pg_constraint c
    WHERE c.conrelid = to_regclass('public.cycle_opening_audit')
      AND c.contype = 'u'
      AND (
        regexp_replace(pg_get_constraintdef(c.oid), '[[:space:]]', '', 'g')
          LIKE '%UNIQUE(tenant_id,idempotency_key)%'
        OR regexp_replace(pg_get_constraintdef(c.oid), '[[:space:]]', '', 'g')
          LIKE '%UNIQUE(tenant_id,cycle_year)%'
      )
  ) AS unique_replay
)
SELECT label || '=' || CASE WHEN COALESCE(flag, FALSE)
                           THEN 'TRUE' ELSE 'FALSE' END
FROM evidence
CROSS JOIN LATERAL (VALUES
  ('DB_TARGET_OK', db_target_ok),
  ('M043_POLICY_FLOOR', policy_floor),
  ('M043_QUOTA_FLOOR', quota_floor),
  ('M043_NO_DEFAULTS', no_defaults),
  ('M043_WRAPPER_FLOOR', wrapper_floor),
  ('M043_LEGACY_RESTRICTED', legacy_restricted),
  ('M044_AUDIT_RLS', audit_rls),
  ('M044_IMMUTABLE_TRIGGERS', immutable_triggers),
  ('M044_CREATE_FLOOR', create_floor),
  ('M044_ROLE_BOUNDARY', role_boundary),
  ('M044_UNIQUE_REPLAY', unique_replay)
) AS flags(label, flag)
ORDER BY label;
COMMIT;
"""

class CatalogAuditBlocked(Exception):
    """Constant failures only. Never expose PostgreSQL diagnostics or secrets."""


def parse_report(raw: object) -> dict[str, bool]:
    if type(raw) is not str or not raw or len(raw) > 4096:
        raise CatalogAuditBlocked("M38790_REPORT_INVALID")
    parsed: dict[str, bool] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if line.count("=") != 1:
            raise CatalogAuditBlocked("M38790_REPORT_INVALID")
        name, value = line.split("=", 1)
        if name not in FIELDS or name in parsed or value not in ("TRUE", "FALSE"):
            raise CatalogAuditBlocked("M38790_REPORT_INVALID")
        parsed[name] = value == "TRUE"
    if set(parsed) != set(FIELDS):
        raise CatalogAuditBlocked("M38790_REPORT_INCOMPLETE")
    if not parsed["DB_TARGET_OK"]:
        raise CatalogAuditBlocked("M38790_WRONG_POSTGRES_CLUSTER")
    return parsed


def _prompt_password() -> str:
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        raise CatalogAuditBlocked("M38790_INTERACTIVE_TTY_REQUIRED")
    try:
        password = getpass.getpass("Senha local PostgreSQL (oculta): ")
    except Exception:
        raise CatalogAuditBlocked("M38790_PASSWORD_PROMPT_UNAVAILABLE") from None
    if type(password) is not str or not 1 <= len(password) <= 512:
        raise CatalogAuditBlocked("M38790_PASSWORD_INVALID")
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in password):
        raise CatalogAuditBlocked("M38790_PASSWORD_INVALID")
    return password


def fetch_catalog(password: str) -> dict[str, bool]:
    if type(password) is not str or not 1 <= len(password) <= 512:
        raise CatalogAuditBlocked("M38790_PASSWORD_INVALID")
    if any(ord(ch) < 33 or ord(ch) > 126 for ch in password):
        raise CatalogAuditBlocked("M38790_PASSWORD_INVALID")
    # Controlled child environment: no inherited PGHOST, PGSERVICE or PGOPTIONS
    # that could silently redirect the audit to an unapproved database.
    env = {k: v for k, v in os.environ.items() if not k.startswith("PG")}
    env.update({
        "PGPASSWORD": password,
        "PGCONNECT_TIMEOUT": "5",
        "PGSSLMODE": "disable",  # Local loopback only.
        "PGOPTIONS": "-c default_transaction_read_only=on",
    })
    argv = [
        "psql", "-X", "-w", "-q", "-A", "-t",
        "-v", "ON_ERROR_STOP=1",
        "-h", HOST, "-p", PORT, "-U", USER, "-d", DATABASE,
    ]
    try:
        completed = subprocess.run(
            argv, input=QUERY, text=True, capture_output=True,
            env=env, timeout=20, check=False,
        )
    except Exception:
        raise CatalogAuditBlocked("M38790_LOCAL_PSQL_UNAVAILABLE") from None
    finally:
        env.pop("PGPASSWORD", None)
    if completed.returncode != 0:
        raise CatalogAuditBlocked("M38790_LOCAL_PG_QUERY_FAILED")
    return parse_report(completed.stdout)


def _closed() -> None:
    print("M38790_QUERY_SCOPE=PG_CATALOG_ONLY")
    print("M38790_FINANCIAL_ROW_READS=NONE")
    print("M38790_DATABASE_MUTATIONS=NONE")
    print("M38790_SQL_MIGRATIONS=NONE")
    print("M38790_CLOUD_MUTATIONS=NONE")
    print("M38790_EMAIL_REAL=OFF")
    print("M38790_PIX_REAL=OFF")
    print("M38790_PAYMENTS_REAL=OFF")
    print("M38790_ACTIVATION_REAL=OFF")
    print("M38790_PRODUCTION=BLOCKED")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Termux PG18 043/044 read-only catalog audit")
    parser.add_argument("mode", nargs="?", choices=("offline", "local"), default="offline")
    parser.add_argument("authorization", nargs="?")
    args = parser.parse_args(argv)
    print("=== FR FINANCE M38701-M38790 LOCAL PG18 043/044 ===")
    if args.mode == "offline":
        if args.authorization is not None:
            print("M38790_AUDIT=BLOCKED_UNEXPECTED_AUTHORIZATION")
            _closed()
            return 2
        print("M38790_MODE=OFFLINE_NO_DB_NO_CREDENTIALS")
        print("M38790_LOCAL_043_SCHEMA=NOT_QUERIED")
        print("M38790_LOCAL_044_SCHEMA=NOT_QUERIED")
        print("M38790_MIGRATION_PROVENANCE=NOT_ATTESTED")
        _closed()
        return 0
    if args.authorization != AUTHORIZE:
        print("M38790_AUDIT=BLOCKED_EXPLICIT_AUTHORIZATION_REQUIRED")
        _closed()
        return 2
    try:
        password = _prompt_password()
        try:
            evidence = fetch_catalog(password)
        finally:
            # Immutable strings cannot be securely zeroized in CPython.
            del password
    except CatalogAuditBlocked as exc:
        print("M38790_AUDIT=BLOCKED")
        print("M38790_CAUSE=" + str(exc))
        print("M38790_MIGRATION_PROVENANCE=NOT_ATTESTED")
        _closed()
        return 2
    except Exception:
        print("M38790_AUDIT=BLOCKED_UNCLASSIFIED")
        print("M38790_MIGRATION_PROVENANCE=NOT_ATTESTED")
        _closed()
        return 2
    print("M38790_MODE=LOCAL_POSTGRES_CATALOG_READ_ONLY")
    print("M38790_DB_TARGET=VERIFIED_LOCAL_PG18")
    for name in FIELDS[1:]:
        print("M38790_" + name + "=" + ("TRUE" if evidence[name] else "FALSE"))
    print("M38790_LOCAL_043_SCHEMA=" + (
        "COMPATIBLE_OBSERVED" if all(evidence[k] for k in FLOOR_043) else "INCOMPLETE_OR_MISSING"))
    print("M38790_LOCAL_044_SCHEMA=" + (
        "COMPATIBLE_OBSERVED" if all(evidence[k] for k in FLOOR_044) else "INCOMPLETE_OR_MISSING"))
    print("M38790_MIGRATION_PROVENANCE=NOT_ATTESTED")
    print("M38790_PRODUCTION_APPROVAL=NOT_GRANTED")
    _closed()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
