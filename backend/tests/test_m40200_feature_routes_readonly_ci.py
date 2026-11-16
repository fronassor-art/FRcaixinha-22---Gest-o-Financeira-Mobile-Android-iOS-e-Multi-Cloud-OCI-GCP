"""Synthetic M40200 tests: inspect feature declarations, never hit protected URLs."""
import ast
from pathlib import Path

import pytest

from backend.scripts import frfinance_m40200_feature_routes_readonly as m

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    "special_credit.py",
    "exclusive_cashboxes.py",
    "exclusive_cashbox_review_gaps.py",
    "tenants.py",
    "notifications.py",
    "auth.py",
    "saas_promotions.py",
)


def source_routes(filename):
    """Read static decorators, without importing the app or connecting to DB."""
    path = ROOT / "backend/app/routers" / filename
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=filename)
    prefixes = {}
    pairs = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            call = node.value
            if (isinstance(call.func, ast.Name)
                    and call.func.id == "APIRouter"):
                key = next((kw.value.value for kw in call.keywords
                            if kw.arg == "prefix" and isinstance(kw.value, ast.Constant)
                            and type(kw.value.value) is str), None)
                if key is not None:
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            prefixes[target.id] = key
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                d = decorator.func
                if (not isinstance(d, ast.Attribute)
                        or not isinstance(d.value, ast.Name)
                        or d.attr not in ("get", "post")
                        or not decorator.args
                        or not isinstance(decorator.args[0], ast.Constant)
                        or type(decorator.args[0].value) is not str):
                    continue
                root = prefixes.get(d.value.id)
                if root is not None:
                    pairs.add((d.attr, "/api/v1" + root + decorator.args[0].value))
    return pairs


def test_actual_router_declarations_match_all_inventory_pairs():
    declared = set()
    for file in SOURCES:
        declared.update(source_routes(file))
    expected = {
        (method, path)
        for method, paths in m.GROUPS.values()
        for path in paths
    }
    assert expected <= declared
    assert len(expected) == m.EXPECTED_COUNT


def complete_openapi():
    paths = {}
    for method, routes in m.GROUPS.values():
        for path in routes:
            paths.setdefault(path, {})[method] = {}
    return {"paths": paths}


def test_synthetic_all_groups_present():
    checks, missing = m.check_schema(complete_openapi())
    assert missing == ()
    for group, (_, routes) in m.GROUPS.items():
        assert checks[group] == f"{len(routes)}_OF_{len(routes)}"


def test_missing_method_not_satisfied_by_wrong_method():
    doc = complete_openapi()
    path = m.CREDIT + "/campaigns/{campaign_id}/publish"
    doc["paths"][path].pop("post")
    doc["paths"][path]["get"] = {}
    checks, missing = m.check_schema(doc)
    assert "POST " + path in missing
    assert checks["ADMIN_WRITE_DOCUMENTED_ONLY"] == "4_OF_5"


@pytest.mark.parametrize("bad", [None, "", {}, {"paths": []}, {"paths": None}])
def test_malformed_openapi(bad):
    assert m.check_schema(bad) is None


def test_live_inventory_success_does_not_attest_role_or_finance():
    documents = complete_openapi()
    def fetch(path):
        if path == m.ROUTES:
            return 200, documents
        assert path == m.HEALTH
        return 200, {"app": "FR Finance", "status": "ONLINE"}
    result = m.report(
        preflight=lambda: {"M40190_STATUS": "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"},
        fetch=fetch,
    )
    assert result["M40200_STATUS"] == "PASS_DOCUMENTED_FEATURE_ROUTES_ONLY"
    assert result["M40200_ADMIN_MEMBER_RLS"] == "NOT_TESTED"
    assert result["M40200_AUTHORIZED_MEMBER_LOGIN"] == "NOT_TESTED"
    assert result["M40200_CREDIT_CAMPAIGN_PUBLISH"] == "NOT_EXECUTED"
    assert result["M40200_PROCESS_OWNER"] == "NOT_ATTESTED_ANDROID_OR_UNKNOWN"
    assert result["M40200_PRODUCTION"] == "BLOCKED"


def test_preflight_failure_never_opens_openapi():
    def unexpected(_):
        pytest.fail("No requests if operational identity not proven")
    result = m.report(
        preflight=lambda: {"M40190_STATUS": "BLOCKED_HEALTH_IDENTITY"},
        fetch=unexpected,
    )
    assert result["M40200_STATUS"] == "BLOCKED_LOCAL_OPERATIONAL_GATE"


def test_refuses_missing_feature_without_post():
    doc = complete_openapi()
    doc["paths"].pop(m.CREDIT + "/campaigns")
    result = m.report(
        preflight=lambda: {"M40190_STATUS": "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"},
        fetch=lambda path: (200, doc) if path == m.ROUTES
        else (200, {"app": "FR Finance", "status": "ONLINE"}),
    )
    assert result["M40200_STATUS"] == "BLOCKED_FEATURE_ROUTES_INCOMPLETE"
    assert result["M40200_MISSING_COUNT"] == "2"


def test_health_must_remain_stable():
    result = m.report(
        preflight=lambda: {"M40190_STATUS": "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"},
        fetch=lambda path: (200, complete_openapi()) if path == m.ROUTES
        else (0, None),
    )
    assert result["M40200_STATUS"] == "BLOCKED_HEALTH_CHANGED_DURING_INVENTORY"


def test_only_existing_read_only_public_http_targets():
    code=(ROOT / "backend/scripts/frfinance_m40200_feature_routes_readonly.py"
          ).read_text(encoding="utf-8")
    assert "from backend.scripts.frfinance_m40190_operational_readonly_checkpoint" in code
    assert "guarded(fetch, ROUTES)" in code
    assert "guarded(fetch, HEALTH)" in code
    for forbidden in (
        "Request(", "urlopen(", "psycopg.connect(", "asyncpg.connect(",
        "subprocess.Popen(", "os.kill(", "shell=True", "pg_ctl start",
        "pg_ctl stop", "session.post(", "requests.post(",
    ):
        assert forbidden not in code


def test_source_only_and_termux_gate(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40200_LIVE_API=NOT_QUERIED" in capsys.readouterr().out
    assert m.main([]) == 2
