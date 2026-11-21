"""M40590: offline source safety for parameterized loan/quota/contribution listings."""
from pathlib import Path
import os
import subprocess
import sys
import ast

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"backend/tests/m40590_role_filtered_listing_disposable.py"
WORKFLOW=ROOT/".github/workflows/frfinance-m40590-literal-financial-queries-ci.yml"
SCANNER=ROOT/"backend/scripts/frfinance_m40580_sql_static_guard.py"
sys.path.insert(0,str(ROOT))


def test_disposable_runner_fails_closed_without_psycopg():
    r=subprocess.run([sys.executable,"-B",str(RUNNER)],text=True,capture_output=True,
                     env={"PATH":os.environ.get("PATH","")},timeout=10)
    assert r.returncode==2
    assert "M40590_STATUS=BLOCKED_RuntimeError" in r.stdout
    assert "M40590_PG18_5433_ORIGINAL=NOT_ACCESSED" in r.stdout


def test_all_three_financial_routes_have_literal_sql_and_bound_role_flag():
    from backend.scripts.frfinance_m40580_sql_static_guard import audit_source
    for module in ("loans.py","contributions.py"):
        file=ROOT/"backend/app/routers"/module
        count,errors=audit_source(file)
        assert count>=3
        assert not errors,(module,errors)
    source=RUNNER.read_text()
    assert "load_literal_query(category)" in source
    assert "M40590_ROLE_FILTER_CASES=24_OF_24_PASS_DISPOSABLE_ONLY" in source


def test_route_queries_never_append_sql_text_and_use_uuid_and_boolean_bindings():
    for file in ("loans.py","contributions.py"):
        code=(ROOT/"backend/app/routers"/file).read_text()
        assert "query +=" not in code
        assert "$2::boolean = FALSE" in code
        assert "m.user_id = $3::uuid" in code
        assert "session.role == \"TENANT_MEMBER\"" in code


def test_role_predicate_cannot_be_replaced_by_client_supplied_role():
    for file in ("loans.py","contributions.py"):
        source=(ROOT/"backend/app/routers"/file).read_text()
        tree=ast.parse(source)
        for node in ast.walk(tree):
            if (isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute)
                and node.func.attr=="fetch" and node.args and isinstance(node.args[0],ast.Constant)
                and isinstance(node.args[0].value,str) and "$2::boolean" in node.args[0].value):
                assert len(node.args)==4
                role=node.args[2]
                assert isinstance(role,ast.Compare)
                assert isinstance(role.left,ast.Attribute) and role.left.attr=="role"
                assert role.comparators[0].value=="TENANT_MEMBER"


def test_ci_is_ephemeral_and_never_original_pg():
    code=RUNNER.read_text()
    wf=WORKFLOW.read_text()
    for marker in ("GITHUB_ACTIONS","CI_M40590_DISPOSABLE","FRCAIXINHA_CI_ISOLATED",
                   "55434","fr_m40590_disposable_ci","M40590_PRODUCTION=BLOCKED"):
        assert marker in code
    for marker in ("postgres:18","55434:5432","fr_m40590_disposable_ci",
                   "CI_M40590_DISPOSABLE: '1'","FRCAIXINHA_CI_ISOLATED: '1'",
                   "PIX_REAL: 'OFF'","PAGAMENTOS_REAIS: 'OFF'","ATIVACAO_REAL: 'OFF'"):
        assert marker in wf
    assert "psql -h 127.0.0.1 -p 5433" not in code
    assert "ssh " not in wf


def test_static_scanner_now_covers_all_five_critical_files():
    from backend.scripts.frfinance_m40580_sql_static_guard import (
        SENSITIVE_PATHS,source_report,
    )
    assert "backend/app/routers/loans.py" in SENSITIVE_PATHS
    assert "backend/app/routers/contributions.py" in SENSITIVE_PATHS
    result=source_report()
    assert len(result)==5
    assert all(num>0 and not problems for num,problems in result.values())


def test_financial_operations_and_services_stay_off():
    code=RUNNER.read_text()
    for flag in ("M40590_LOCAL_MIGRATIONS=NONE","M40590_LOCAL_DB_WRITES=NONE",
                 "M40590_SERVICE_RESTARTS=NONE","M40590_PIX_REAL=OFF",
                 "M40590_PAGAMENTOS_REAIS=OFF","M40590_ATIVACAO_REAL=OFF",
                 "M40590_PRODUCTION=BLOCKED"):
        assert flag in code