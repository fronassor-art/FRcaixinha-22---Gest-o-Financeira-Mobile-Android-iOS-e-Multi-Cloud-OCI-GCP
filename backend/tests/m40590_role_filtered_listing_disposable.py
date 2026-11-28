#!/usr/bin/env python3
"""M40590: test real fixed route SQL against *disposable* PostgreSQL 18.

No usage on Termux or user infrastructure; fake principals/tenants and rows.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import sys
from uuid import uuid4
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
TARGETS = {
    "loans": ("backend/app/routers/loans.py", "list_tenant_loans", "FROM loans l"),
    "quotas": ("backend/app/routers/contributions.py", "list_tenant_quotas", "FROM quotas q"),
    "contributions": (
        "backend/app/routers/contributions.py",
        "list_tenant_contributions",
        "FROM contributions c",
    ),
}


def require_disposable_ci() -> str:
    if (os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("CI_M40590_DISPOSABLE") != "1"
        or os.environ.get("FRCAIXINHA_CI_ISOLATED") != "1"
        or os.environ.get("PIX_REAL") != "OFF"
        or os.environ.get("PAGAMENTOS_REAIS") != "OFF"
        or os.environ.get("ATIVACAO_REAL") != "OFF"):
        raise RuntimeError("M40590_ONLY_DISPOSABLE_GITHUB_ACTIONS")
    url = os.environ.get("CI_M40590_DATABASE_URL", "")
    parsed = urlparse(url)
    if (parsed.scheme not in ("postgresql", "postgres")
        or parsed.hostname != "127.0.0.1"
        or parsed.port != 55434
        or parsed.path != "/fr_m40590_disposable_ci"
        or parsed.username != "postgres"
        or parsed.query or parsed.fragment):
        raise RuntimeError("M40590_REFUSES_UNTRUSTED_DB_TARGET")
    return url


def load_literal_query(key: str) -> str:
    file, endpoint, table = TARGETS[key]
    tree = ast.parse((ROOT / file).read_text(), filename=file)
    matches = []
    for node in tree.body:
        if not isinstance(node, ast.AsyncFunctionDef) or node.name != endpoint:
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                continue
            if (call.func.attr != "fetch" or not isinstance(call.func.value, ast.Name)
                or call.func.value.id != "conn"):
                continue
            if call.args and isinstance(call.args[0], ast.Constant):
                arg = call.args[0].value
                if isinstance(arg, str) and table in arg:
                    matches.append(arg)
    if len(matches) != 1:
        raise AssertionError("M40590_MISSING_OR_DYNAMIC_" + key.upper())
    query = matches[0]
    for token in ("$1", "$2::boolean", "$3::uuid", "m.role = 'TENANT_MEMBER'",
                  "m.status = 'ATIVA'"):
        if token not in query:
            raise AssertionError("M40590_MISSING_PARAMETER_GUARD_" + key.upper())
    # No string is interpolated. psycopg needs %s where asyncpg uses $N.
    for placeholder in ("$1", "$2", "$3"):
        query = query.replace(placeholder, "%s")
    return query


def create_fixtures(conn) -> tuple:
    """Disposable objects only. No migrations or production schemas."""
    conn.execute(
        "CREATE TABLE users (id uuid PRIMARY KEY,full_name text NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE memberships (id uuid PRIMARY KEY,user_id uuid NOT NULL,"
        "role text,status text)"
    )
    conn.execute(
        "CREATE TABLE loans (id uuid DEFAULT gen_random_uuid(),"
        "tenant_id uuid,cycle_id uuid DEFAULT gen_random_uuid(),"
        "borrower_membership_id uuid,is_admin_loan boolean DEFAULT false,"
        "principal numeric DEFAULT 300,monthly_rate numeric DEFAULT 0.02,"
        "term_months int DEFAULT 3,monthly_payment numeric DEFAULT 102,"
        "last_payment numeric DEFAULT 102,total_interest numeric DEFAULT 6,"
        "status text DEFAULT 'DRAFT',created_at timestamptz DEFAULT now(),"
        "disbursed_at timestamptz)"
    )
    conn.execute(
        "CREATE TABLE quotas (id uuid DEFAULT gen_random_uuid(),"
        "tenant_id uuid,membership_id uuid,quota_number int,"
        "value_brl numeric DEFAULT 150,status text DEFAULT 'ATIVA',"
        "created_at timestamptz DEFAULT now())"
    )
    conn.execute(
        "CREATE TABLE contributions (id uuid DEFAULT gen_random_uuid(),"
        "tenant_id uuid,cycle_id uuid DEFAULT gen_random_uuid(),"
        "membership_id uuid,competence date DEFAULT CURRENT_DATE,"
        "due_date date DEFAULT CURRENT_DATE,amount_due numeric DEFAULT 150,"
        "amount_paid numeric DEFAULT 0,payment_status text DEFAULT 'PENDING',"
        "due_status text DEFAULT 'ON_TIME',paid_at timestamptz)"
    )
    a,b=uuid4(),uuid4()
    people=[uuid4() for _ in range(5)]
    members=[uuid4() for _ in range(5)]
    for user_id,name in zip(people,("MEMBER_A1","MEMBER_A2","ADMIN_A","INACTIVE_A","MEMBER_B")):
        conn.execute("INSERT INTO users(id,full_name) VALUES (%s,%s)",(user_id,name))
    for mem_id,user_id,role,status in zip(
        members,people,
        ("TENANT_MEMBER","TENANT_MEMBER","TENANT_ADMIN","TENANT_MEMBER","TENANT_MEMBER"),
        ("ATIVA","ATIVA","ATIVA","INATIVA","ATIVA")
    ):
        conn.execute(
            "INSERT INTO memberships(id,user_id,role,status) VALUES (%s,%s,%s,%s)",
            (mem_id,user_id,role,status),
        )
    for index, (mem_id,tid) in enumerate(zip(members,(a,a,a,a,b)),1):
        conn.execute(
            "INSERT INTO loans(tenant_id,borrower_membership_id) VALUES (%s,%s)",
            (tid,mem_id),
        )
        conn.execute(
            "INSERT INTO quotas(tenant_id,membership_id,quota_number) VALUES (%s,%s,%s)",
            (tid,mem_id,index),
        )
        conn.execute(
            "INSERT INTO contributions(tenant_id,membership_id) VALUES (%s,%s)",
            (tid,mem_id),
        )
    return a,b,people


def run_tests(conn) -> None:
    a,b,people=create_fixtures(conn)
    for category in TARGETS:
        sql=load_literal_query(category)
        def count(tenant,member_mode,actor):
            return len(conn.execute(sql,(tenant,member_mode,actor)).fetchall())
        assert count(a,False,people[2])==4,category+" admin sees all tenant A"
        assert count(a,True,people[0])==1,category+" member1 only own active"
        assert count(a,True,people[1])==1,category+" member2 only own active"
        assert count(a,True,people[2])==0,category+" admin cannot masquerade member"
        assert count(a,True,people[3])==0,category+" inactive member excluded"
        assert count(a,True,people[4])==0,category+" other tenant cannot see A"
        assert count(b,False,people[4])==1,category+" admin of B sees B only"
        assert count(b,True,people[4])==1,category+" member B sees own"
        print("M40590_" + category.upper() + "_TENANT_ROLE_FILTER=PASS_8_CASES")
    print("M40590_ROLE_FILTER_CASES=24_OF_24_PASS_DISPOSABLE_ONLY")


def main() -> int:
    try:
        url=require_disposable_ci()
        import psycopg
        with psycopg.connect(url, autocommit=True, connect_timeout=5) as conn:
            run_tests(conn)
    except Exception as exc:
        print("M40590_STATUS=BLOCKED_" + type(exc).__name__)
        return 2
    finally:
        print("M40590_PG18_5433_ORIGINAL=NOT_ACCESSED")
        print("M40590_FR_CAIXINHA_2_2=NOT_ACCESSED")
        print("M40590_LOCAL_SQL=NONE")
        print("M40590_LOCAL_MIGRATIONS=NONE")
        print("M40590_LOCAL_DB_WRITES=NONE")
        print("M40590_SERVICE_RESTARTS=NONE")
        print("M40590_PIX_REAL=OFF")
        print("M40590_PAGAMENTOS_REAIS=OFF")
        print("M40590_ATIVACAO_REAL=OFF")
        print("M40590_PRODUCTION=BLOCKED")
    print("M40590_STATUS=PASS_DISPOSABLE_ONLY_NOT_PRODUCTION")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())