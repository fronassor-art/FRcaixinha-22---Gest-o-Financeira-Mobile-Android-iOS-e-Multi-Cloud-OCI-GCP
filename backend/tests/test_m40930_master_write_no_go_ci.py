"""M40930: no real Master SQL write without approved independent custody.

Tests are offline, use a synthetic FastAPI app, and never connect to PG.
The old SQL route code remains for future architectural review, not release.
"""
from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.m40930_master_write_no_go import require_unreleased_master_write


ROOT = Path(__file__).resolve().parents[2]
ROUTE_FILES = (
    ("backend/app/routers/master.py", {"/license-prices"}),
    ("backend/app/routers/saas_promotions.py", {"/draft", "/transition"}),
)


def _master_post_dependencies(path: Path) -> dict[str, set[str]]:
    result = {}
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (not isinstance(decorator, ast.Call)
                    or not isinstance(decorator.func, ast.Attribute)
                    or decorator.func.attr != "post"
                    or not decorator.args
                    or not isinstance(decorator.args[0], ast.Constant)):
                continue
            route = decorator.args[0].value
            if not isinstance(route, str):
                continue
            dep = next(
                (keyword.value for keyword in decorator.keywords
                 if keyword.arg == "dependencies"),
                None,
            )
            names = set()
            if isinstance(dep, (ast.List, ast.Tuple)):
                for item in dep.elts:
                    if (isinstance(item, ast.Call)
                            and isinstance(item.func, ast.Name)
                            and item.func.id == "Depends"
                            and len(item.args) == 1
                            and isinstance(item.args[0], ast.Name)):
                        names.add(item.args[0].id)
            result[route] = names
    return result


@pytest.mark.parametrize("path, required_routes", ROUTE_FILES)
def test_all_known_real_master_mutation_routes_fail_closed(path, required_routes):
    source = (ROOT / path).read_text(encoding="utf-8")
    assert "from ..m40930_master_write_no_go import require_unreleased_master_write" in source
    routes = _master_post_dependencies(ROOT / path)
    for route in required_routes:
        assert route in routes
        assert "require_unreleased_master_write" in routes[route]


@pytest.mark.parametrize("environment", [
    {}, {"ENVIRONMENT": "development"},
    {"ENVIRONMENT": "staging"},
    {"ENVIRONMENT": "production"},
    {"ENVIRONMENT": "production", "PIX_REAL": "ON",
     "PAGAMENTOS_REAIS": "ON", "ATIVACAO_REAL": "ON"},
])
def test_no_environment_variable_can_release_master_write(environment):
    with patch.dict("os.environ", environment, clear=True):
        with pytest.raises(HTTPException) as info:
            require_unreleased_master_write()
    assert info.value.status_code == 503
    assert "custodia independente" in info.value.detail


def test_api_dependency_rejects_before_business_logic_without_db():
    calls = []
    api = FastAPI()

    @api.post("/synthetic-master-mutation",
              dependencies=[Depends(require_unreleased_master_write)])
    def synthetic_write(body: dict):
        calls.append(body)
        return {"allowed": True}

    with TestClient(api) as client:
        response = client.post("/synthetic-master-mutation", json={"amount": 1})
        assert response.status_code == 503
        assert calls == []
        assert "custodia independente" in response.json()["detail"]

        # Only a new, isolated test app permits explicit dependency override.
        api.dependency_overrides[require_unreleased_master_write] = lambda: None
        allowed = client.post("/synthetic-master-mutation", json={"amount": 1})
        assert allowed.status_code == 200
        assert calls == [{"amount": 1}]


def test_production_financial_sql_gate_m40840_unmodified():
    source = (ROOT / "backend/app/m40840_financial_sql_release_no_go.py").read_text()
    assert 'raise FinancialSQLReleaseBlocked("M40840_FINANCIAL_SQL_NO_GO")' in source
    assert "production" not in source.split("_NONPROD =", 1)[1].split("_REAL_FLAGS", 1)[0]
    assert "PIX_REAL" in source
    assert "PAGAMENTOS_REAIS" in source
    assert "ATIVACAO_REAL" in source


def test_guard_no_runtime_bypass_and_no_sql_side_effect():
    source = (ROOT / "backend/app/m40930_master_write_no_go.py").read_text()
    tree = ast.parse(source)
    banned_imports = {"asyncpg", "psycopg", "requests", "subprocess", "socket"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert not banned_imports.intersection(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom) and node.module:
            assert node.module not in banned_imports
    assert "raise HTTPException(" in source
    assert "getenv(" not in source
    assert "os.environ" not in source
