#!/usr/bin/env python3
"""FR Finance M39080 — elegibilidade do ciclo para campanha interna, READ ONLY.

Consulta APENAS contagens por tenant e metadados de schema no banco ORIGINAL.
Não exibe nome, e-mail, UUID, documento, saldos, valores dos créditos, senha
ou qualquer campo de auditoria pessoal. NÃO cria ciclo, concessão ou oferta.
"""
from __future__ import annotations

import getpass
import sys

from backend.scripts.frfinance_m39054_auth_pg18_preflight import (
    verify_original,
)
from backend.scripts.frfinance_m39026_credit_only_preflight import (
    DB, OWNER, DATA_DIRECTORY,
)

CREDIT_TABLES = (
    "special_credit_grants",
    "special_credit_campaigns",
    "special_credit_recipients",
    "special_credit_preferences",
    "special_credit_outbox",
    "special_credit_audit",
)
CREDIT_TRIGGERS = (
    "sc_m39020_grant_transition",
    "sc_m39020_campaign_transition",
    "sc_m39020_recipient_insert",
    "sc_m39020_reply_transition",
    "sc_m39020_outbox_insert",
)


def eligibility_state(
    active_tenants: int,
    open_cycles: int,
    current_cycles: int,
    active_members: int,
) -> str:
    if active_tenants != 1:
        return "BLOCKED_SELECT_TENANT_SAFELY" if active_tenants > 1 else "BLOCKED_NO_ACTIVE_TENANT"
    if open_cycles == 0:
        return "BLOCKED_NO_OPEN_CYCLE"
    if open_cycles != 1:
        return "BLOCKED_MULTIPLE_OPEN_CYCLES"
    if current_cycles != 1:
        return "BLOCKED_CYCLE_DATES_INCONSISTENT"
    if active_members == 0:
        return "BLOCKED_NO_ELIGIBLE_ACTIVE_MEMBERS"
    return "PASS_READY_TO_TEST_INTERNAL_GRANTS"


def original_database_identity(conn) -> bool:
    data = conn.execute(
        "SELECT current_database(),current_user,session_user,"
        "host(inet_server_addr()),inet_server_port(),"
        "current_setting('data_directory'),"
        "current_setting('server_version_num')::integer,"
        "current_setting('transaction_read_only')"
    ).fetchone()
    return data[:6] == (
        DB, OWNER, OWNER, "127.0.0.1", 5433, DATA_DIRECTORY
    ) and 180000 <= data[6] < 190000 and data[7] == "on"


def audit(conn) -> str:
    with conn.transaction():
        conn.execute("SET TRANSACTION READ ONLY")
        if not original_database_identity(conn):
            raise RuntimeError("NOT_FR_FINANCE_ORIGINAL_PG18")

        schema = conn.execute(
            "SELECT count(*) FILTER (WHERE c.relrowsecurity AND c.relforcerowsecurity),"
            " count(*) FROM pg_catalog.pg_class c "
            "JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' AND c.relname=ANY(%s)",
            (list(CREDIT_TABLES),),
        ).fetchone()
        guards = conn.execute(
            "SELECT count(*) FROM pg_catalog.pg_trigger "
            "WHERE tgname=ANY(%s) AND tgenabled='O' AND NOT tgisinternal",
            (list(CREDIT_TRIGGERS),),
        ).fetchone()[0]
        if schema != (6, 6) or guards != 5:
            raise RuntimeError("CREDIT_SCHEMA_RLS_OR_TRIGGER_MISMATCH")

        active = conn.execute(
            "SELECT id FROM public.tenants WHERE status='ATIVO' ORDER BY id"
        ).fetchall()
        active_tenants = len(active)
        print(f"M39080_ACTIVE_TENANTS={active_tenants}")
        if active_tenants != 1:
            return eligibility_state(active_tenants, 0, 0, 0)

        tenant_id = active[0][0]
        cycles = conn.execute(
            "SELECT count(*) FILTER (WHERE status='ABERTO'),"
            " count(*) FILTER (WHERE status='ABERTO' "
            "AND start_date<=CURRENT_DATE AND end_date>=CURRENT_DATE) "
            "FROM public.cycles WHERE tenant_id=%s",
            (tenant_id,),
        ).fetchone()
        members = conn.execute(
            "SELECT count(*) FROM public.memberships "
            "WHERE tenant_id=%s AND role='TENANT_MEMBER' AND status='ATIVA'",
            (tenant_id,),
        ).fetchone()[0]
        records = conn.execute(
            "SELECT "
            "(SELECT count(*) FROM public.special_credit_grants g "
            "WHERE g.tenant_id=%s AND g.status='ACTIVE' AND g.expires_at>now()),"
            "(SELECT count(*) FROM public.special_credit_campaigns c "
            "WHERE c.tenant_id=%s AND c.status='DRAFT'),"
            "(SELECT count(*) FROM public.special_credit_campaigns c "
            "WHERE c.tenant_id=%s AND c.status='PUBLISHED' AND c.expires_at>now()),"
            "(SELECT count(*) FROM public.special_credit_recipients r "
            "WHERE r.tenant_id=%s AND r.response_status='PENDING')",
            (tenant_id, tenant_id, tenant_id, tenant_id),
        ).fetchone()

        print(f"M39080_OPEN_CYCLES={cycles[0]}")
        print(f"M39080_CURRENT_OPEN_CYCLES={cycles[1]}")
        print(f"M39080_ELIGIBLE_MEMBERS={members}")
        print(f"M39080_ACTIVE_SPECIAL_GRANTS={records[0]}")
        print(f"M39080_DRAFT_CAMPAIGNS={records[1]}")
        print(f"M39080_PUBLISHED_VALID_CAMPAIGNS={records[2]}")
        print(f"M39080_PENDING_RECIPIENT_REPLIES={records[3]}")
        if any(records):
            print("M39080_EXISTING_RECORDS=REVIEW_BEFORE_NEW_WRITES")
        else:
            print("M39080_EXISTING_RECORDS=NONE")
        return eligibility_state(active_tenants, cycles[0], cycles[1], members)


def main() -> int:
    print("=== FR FINANCE M39080 — CAMPANHAS READ ONLY ===", flush=True)
    try:
        verify_original()
    except Exception:
        print("M39080_STATUS=BLOCKED_REPOSITORY_BRANCH_OR_SHA")
        print("M39080_DATABASE_WRITES=NONE")
        return 2
    try:
        import psycopg
        password = getpass.getpass("Senha PostgreSQL FR Finance frc_ai_owner (oculta): ")
        if not password:
            raise RuntimeError("EMPTY_PASSWORD")
        with psycopg.connect(
            host="127.0.0.1",
            port=5433,
            dbname=DB,
            user=OWNER,
            password=password,
            connect_timeout=5,
            options="-c default_transaction_read_only=on "
                    "-c statement_timeout=10000 -c lock_timeout=2000",
            autocommit=True,
        ) as conn:
            result = audit(conn)
        print("M39080_PG18_ORIGINAL=PASS")
        print("M39080_SQL110_111_RLS_AND_TRIGGERS=PASS")
        print("M39080_STATUS=" + result)
        return 0 if result.startswith("PASS") else 2
    except RuntimeError as error:
        print("M39080_STATUS=BLOCKED_" + str(error))
        return 2
    except Exception:
        print("M39080_STATUS=BLOCKED_READONLY_INSPECTION_FAILED")
        return 2
    finally:
        print("M39080_DATABASE_WRITES=NONE")
        print("M39080_MIGRATIONS=NONE")
        print("M39080_LOAN_APPROVAL_OR_DISBURSEMENT=NONE")
        print("M39080_EXTERNAL_DISPATCH=NONE")
        print("M39080_PIX_MUTATIONS=NONE")
        print("M39080_USER_IDENTITIES_PRINTED=NONE")


if __name__ == "__main__":
    sys.exit(main())
