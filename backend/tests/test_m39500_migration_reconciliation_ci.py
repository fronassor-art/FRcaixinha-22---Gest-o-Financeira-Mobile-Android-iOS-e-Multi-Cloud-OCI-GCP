"""FR Finance M39500 — offline-only proof of SQL110–113 read security.

Synthetic PG catalog only, no local DB, no real login, no SQL writes.
"""
from __future__ import annotations
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

import pytest

from app import m39500_migration_reconciliation as m

ROOT = Path(__file__).resolve().parents[2]


class Rows:
    def __init__(self, value):
        self.value = value
    def fetchone(self):
        return self.value
    def fetchall(self):
        return self.value


class FakePg18:
    def __init__(self, **changes):
        self.changes = changes
        self.queries = []
    def transaction(self):
        return nullcontext()
    def execute(self, sql, args=None):
        self.queries.append((sql, args))
        assert sql.lstrip().startswith(("SELECT ", "SET TRANSACTION READ ONLY"))
        if sql.startswith("SET TRANSACTION READ ONLY"):
            return Rows(None)
        if "current_database(),session_user,current_user" in sql:
            return Rows((
                "frcaixinha_aistudio_dev", "frc_ai_owner",
                self.changes.get("role", "frc_ai_owner"),
                "127.0.0.1", self.changes.get("port",5433),
                self.changes.get("pgdata",m.APP_PGDATA),
                self.changes.get("version",180006),
            ))
        if "FROM pg_catalog.pg_class c" in sql:
            rows = [(t, "r", True, True) for t in m.POLICIES]
            if self.changes.get("rls_off"):
                rows[0] = (rows[0][0],"r",True,False)
            if self.changes.get("table_missing"):
                rows.pop()
            return Rows(rows)
        if "FROM pg_catalog.pg_policies" in sql:
            rows = [(table,p) for table,names in m.POLICIES.items()
                    for p in names]
            if self.changes.get("policy_missing"):
                rows.pop()
            return Rows(rows)
        if "FROM pg_catalog.pg_trigger t" in sql:
            rows = [(table,name,"O",function,"public")
                    for name,(table,function) in m.TRIGGERS.items()]
            if self.changes.get("trigger_off"):
                a = rows[0]
                rows[0] = (a[0],a[1],"D",a[3],a[4])
            return Rows(rows)
        if "FROM pg_catalog.pg_roles" in sql:
            return Rows([
                ("frc_ai_app",False,bool(self.changes.get("role_bypass"))),
                ("frc_ai_auth",False,False),
            ])
        if "has_table_privilege" in sql:
            if self.changes.get("delete_allowed"):
                return Rows((True,True,True,False))
            return Rows((True,True,False,False))
        if "has_column_privilege" in sql:
            obj,col = args
            granted = col in m.ALLOWED_UPDATES.get(
                obj.removeprefix("public."),())
            if self.changes.get("immutable_update") and col=="tenant_id":
                granted = True
            return Rows((granted,))
        if "pg_get_expr(d.adbin,d.adrelid)" in sql:
            return Rows(("'BLOCKED_EXTERNAL'::character varying",))
        if "SELECT pg_get_constraintdef(oid)" in sql:
            if self.changes.get("outbox_sent"):
                return Rows([("CHECK (state IN ('SENT'))",)])
            return Rows([("CHECK (state IN "
                        "('BLOCKED_EXTERNAL','DISPATCH_REVIEW','CANCELLED'))",)])
        raise AssertionError("Unexpected SQL: "+sql)


def test_offline_sql_blobs_and_identity_are_locked():
    v = m.verify_sources()
    assert v["sql_sources"] == "110_111_112_113_HASHES_PASS"
    assert v["original_schema_checked"] is False
    assert v["production_verified"] is False
    assert len(m.SOURCE_BLOBS)==4
    for name,digest in m.SOURCE_BLOBS.items():
        assert m.git_blob((ROOT/name).read_bytes())==digest


def test_credit_catalog_is_independent_of_total_public_table_count():
    conn = FakePg18()
    v = m.inspect_credit_110_111(conn)
    assert v["sql_110_111"]=="CATALOG_COMPATIBLE"
    assert v["credit_force_rls_tables"]==6
    assert v["credit_policies"]==16
    assert v["credit_triggers"]==5
    assert v["historical_migration_application_proven"] is False
    assert v["public_table_count_assumed"] is False
    assert all(query.startswith(("SELECT ","SET TRANSACTION READ ONLY"))
               for query,_ in conn.queries)
    assert all("count(*) FROM pg_catalog.pg_tables" not in q
               for q,_ in conn.queries)


@pytest.mark.parametrize("changes,reason",[
    ({"role":"frcaixinha_2_2_owner"},"WRONG_POSTGRESQL_ROLE_PORT_OR_PGDATA"),
    ({"port":5432},"WRONG_POSTGRESQL_ROLE_PORT_OR_PGDATA"),
    ({"pgdata":"/tmp/frcaixinha_2_2"},"WRONG_POSTGRESQL_ROLE_PORT_OR_PGDATA"),
    ({"version":170000},"WRONG_POSTGRESQL_ROLE_PORT_OR_PGDATA"),
    ({"table_missing":True},"CREDIT_TABLE_FORCE_RLS_DRIFT"),
    ({"rls_off":True},"CREDIT_TABLE_FORCE_RLS_DRIFT"),
    ({"policy_missing":True},"CREDIT_POLICIES_DRIFT"),
    ({"trigger_off":True},"CREDIT_TRIGGER_INTEGRITY_DRIFT"),
    ({"role_bypass":True},"CREDIT_ROLE_PRIVILEGES_UNSAFE"),
    ({"delete_allowed":True},"CREDIT_TABLE_PRIVILEGE_DRIFT"),
    ({"immutable_update":True},"CREDIT_IMMUTABLE_COLUMN_PRIVILEGE_UNSAFE"),
    ({"outbox_sent":True},"CREDIT_EXTERNAL_OUTBOX_UNSAFE"),
])
def test_credit_catalog_fails_closed_on_security_drift(changes,reason):
    with pytest.raises(m.AttestationBlocked,match="M39500_"+reason):
        m.inspect_credit_110_111(FakePg18(**changes))


def test_sql112_113_existing_inspector_is_used_and_all_required_checks_pass(monkeypatch):
    from backend.scripts import (
        frfinance_m39068_postcommit_sql112_113_readonly_diagnostic as old,
    )
    def success(_conn):
        return {
            "SQL112_ANNUAL_INDEPENDENT":True,
            "SQL113_TABLE_EXISTS":True,
            "SQL113_READER_EXISTS":True,
            "SQL112_COLUMN_INSERT_AND_CONSTRAINT":True,
            "SQL113_RLS_ENABLED":True,
            "SQL113_RLS_FORCE":True,
            "SQL113_APP_SELECT_ALLOWED":True,
            "SQL113_AUTH_SELECT_DENIED":True,
            "SQL113_APP_UPDATE_DENIED":True,
            "SQL113_APP_DELETE_DENIED":True,
            "SQL113_APP_READER_ALLOWED":True,
            "SQL113_AUTH_READER_DENIED":True,
            "SQL113_TRIGGER_ACTIVE":True,
            "SQL113_READER_SECURITY_DEFINER":True,
            "SQL113_READER_PATH_RESTRICTED":True,
            "M39067_POSTCHECK_EXACT_TEXT":False,
        }
    monkeypatch.setattr(old,"inspect_schema",success)
    conn=FakePg18()
    result=m.verify_full_catalog(conn)
    assert result["sql_110_111"]=="CATALOG_COMPATIBLE"
    assert result["sql_112_113"]=="CATALOG_COMPATIBLE"
    assert result["schema_catalog"]=="SCOPE_SQL110_TO_SQL113_PASS_READ_ONLY"
    assert result["migrations_applied"]==0
    assert result["database_writes"]==0
    assert result["production_authorized"] is False
    for name in ("SQL113_RLS_FORCE","SQL113_APP_DELETE_DENIED",
                 "SQL113_READER_PATH_RESTRICTED"):
        def drift(_conn,field=name):
            checks=success(_conn)
            checks[field]=False
            return checks
        monkeypatch.setattr(old,"inspect_schema",drift)
        with pytest.raises(m.AttestationBlocked,
                           match="M39500_SAAS_SQL112_113_SECURITY_DRIFT"):
            m.verify_full_catalog(FakePg18())


def test_offline_cli_requires_no_db_driver_or_password():
    cli=ROOT/"backend/scripts/frfinance_m39500_readonly_homologation.py"
    p=subprocess.run([sys.executable,"-B",str(cli),"--offline"],
                     capture_output=True,text=True,cwd=ROOT,check=True)
    assert "M39500_SQL_SOURCES=110_111_112_113_HASHES_PASS" in p.stdout
    assert "M39500_DB_SCHEMA=NOT_INSPECTED_OFFLINE" in p.stdout
    assert "M39500_HISTORY=NOT_ATTESTED" in p.stdout
    assert "M39500_MIGRATIONS=NONE" in p.stdout
    assert "M39500_FASTAPI_RESTART=NONE" in p.stdout
    assert "M39500_PG5432_ACCESS=NONE" in p.stdout
    assert "M39500_PAYMENTS_REAL=OFF" in p.stdout


def test_readonly_mode_refuses_non_interactive_ci():
    cli=ROOT/"backend/scripts/frfinance_m39500_readonly_homologation.py"
    p=subprocess.run([sys.executable,"-B",str(cli),"--original-readonly"],
                     input="",capture_output=True,text=True,cwd=ROOT)
    assert p.returncode==2
    assert "BLOCKED_INTERACTIVE_TERMINAL_REQUIRED" in p.stdout
    assert "Senha" not in p.stdout
    assert "M39500_PG5432_ACCESS=NONE" in p.stdout


def test_only_select_and_locked_db_identity_in_source():
    script=(ROOT/"backend/scripts/frfinance_m39500_readonly_homologation.py").read_text()
    module=(ROOT/"backend/app/m39500_migration_reconciliation.py").read_text()
    assert "SET TRANSACTION READ ONLY" in module
    assert "default_transaction_read_only=on" in script
    assert 'port=5433' in script
    assert 'dbname="frcaixinha_aistudio_dev"' in script
    assert 'user="frc_ai_owner"' in script
    for forbidden in ("INSERT INTO ","DROP TABLE ","ALTER TABLE ",
                      "CREATE ROLE ","TRUNCATE ","DELETE FROM ",
                      "UPDATE public.","subprocess.Popen("):
        assert forbidden not in module+script
