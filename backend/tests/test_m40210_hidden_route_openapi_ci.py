"""M40210 synthetic regression: hidden M40060 routes are not OpenAPI omissions."""
from pathlib import Path
import pytest

from backend.scripts import frfinance_m40210_hidden_route_openapi_correction as m

ROOT = Path(__file__).resolve().parents[2]


def synthetic_visible_openapi():
    paths = {}
    for group, (method, declared) in m.GROUPS.items():
        hidden = m.HIDDEN[group][2] if group in m.HIDDEN else None
        for path in declared:
            if path != hidden:
                paths.setdefault(path, {})[method] = {}
    return {"paths": paths}


def test_actual_hidden_source_two_routes_and_registration():
    assert m.hidden_source_check() == "PASS_TWO_HIDDEN_SOURCE_DECLARATIONS_NOT_RUNTIME_TESTED"
    assert m.PUBLIC_EXPECTED == 33
    assert m.HIDDEN_COUNT == 2
    assert m.EXPECTED_COUNT == 35


def test_real_hidden_source_fails_if_router_made_public(tmp_path):
    contents = m.HIDDEN_SOURCE.read_text(encoding="utf-8")
    changed = contents.replace("include_in_schema=False", "include_in_schema=True")
    sample = tmp_path / "modified.py"
    sample.write_text(changed, encoding="utf-8")
    assert m.hidden_source_check(module_path=sample).startswith("BLOCKED_")


def test_hidden_router_needs_real_auth_dependencies(tmp_path):
    contents = m.HIDDEN_SOURCE.read_text(encoding="utf-8")
    contents = contents.replace("Depends(require_master)", "Depends(get_current_session)")
    path = tmp_path / "modified.py"
    path.write_text(contents, encoding="utf-8")
    assert m.hidden_source_check(module_path=path) == (
        "BLOCKED_HIDDEN_AUTH_OR_DECORATOR"
    )


def test_missing_registration_blocked(tmp_path):
    contents = m.MAIN_SOURCE.read_text(encoding="utf-8")
    contents = contents.replace(
        'app.include_router(_review_policy_gaps.master_router, prefix=settings.API_V1_STR)',
        '# intentionally removed in synthetic test')
    path = tmp_path / "modified_main.py"
    path.write_text(contents, encoding="utf-8")
    assert m.hidden_source_check(main_path=path) == (
        "BLOCKED_HIDDEN_ROUTER_NOT_REGISTERED_IN_SOURCE"
    )


def test_openapi_visible_33_are_complete():
    groups, missing, count = m.visible_schema(synthetic_visible_openapi())
    assert count == 33
    assert missing == ()
    assert groups["ADMIN_READ"] == "11_OF_11"
    assert groups["MASTER_READ"] == "4_OF_4"
    assert groups["ADMIN_WRITE_DOCUMENTED_ONLY"] == "5_OF_5"
    assert groups["MEMBER_READ"] == "9_OF_9"


def test_absence_of_hidden_routes_does_not_fail_public_inventory():
    doc = synthetic_visible_openapi()
    assert not any(path.endswith("review-policy-gaps") for path in doc["paths"])
    assert m.visible_schema(doc)[1] == ()


def test_missing_visible_route_fails_closed():
    doc = synthetic_visible_openapi()
    path = m.TENANT + "/special-credit/campaigns"
    # Same URL has both GET and POST: remove GET only, preserving POST.
    doc["paths"][path].pop("get")
    _, missing, count = m.visible_schema(doc)
    assert missing == ("GET " + path,)
    assert count == 32


@pytest.mark.parametrize("bad", [None, [], {}, {"paths": []}, {"paths": None}])
def test_malformed_openapi(bad):
    assert m.visible_schema(bad) is None


def test_full_probe_pass_has_explicit_runtime_limitation():
    doc = synthetic_visible_openapi()
    def fetch(path):
        if path == m.ROUTES:
            return 200, doc
        assert path == m.HEALTH
        return 200, {"app": "FR Finance", "status": "ONLINE"}
    r = m.report(preflight=lambda: {"M40190_STATUS": "PASS_LOCAL_READONLY_FUNCTIONAL_SMOKE"},
                 fetch=fetch)
    assert r["M40210_STATUS"] == "PASS_33_PUBLIC_AND_2_HIDDEN_SOURCE_ONLY"
    assert r["M40210_HIDDEN_RUNTIME_REACHABILITY"] == "NOT_TESTED"
    assert r["M40210_ADMIN_AUTHENTICATED_RLS"] == "NOT_TESTED"
    assert r["M40210_FINANCIAL_REVIEW_APPROVAL"] == "FALSE"


def test_preflight_failure_skips_http():
    def forbidden(_):
        pytest.fail("HTTP should be skipped")
    r=m.report(preflight=lambda: {"M40190_STATUS": "BLOCKED"}, fetch=forbidden)
    assert r["M40210_STATUS"] == "BLOCKED_M40190_OPERATIONAL_READINESS"


def test_exclusions_do_not_remove_safety_rules():
    source=(ROOT / "backend/scripts/frfinance_m40210_hidden_route_openapi_correction.py"
            ).read_text(encoding="utf-8")
    for text in ("M40210_PROTECTED_ENDPOINT_CALLS=NONE",
                 "M40210_DATABASE_WRITES=NONE_FROM_TERMINAL_PROBE",
                 "M40210_FASTAPI_RESTART=NONE",
                 "M40210_PRODUCTION=BLOCKED"):
        assert text in source
    for forbidden in ("os.kill(", "subprocess.Popen(", "psycopg.connect(",
                      "asyncpg.connect(", "shell=True", "requests.post(",
                      "pg_ctl start", "pg_ctl restart"):
        assert forbidden not in source


def test_source_only_without_live_api(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40210_LIVE_API=NOT_QUERIED" in capsys.readouterr().out
    assert m.main([]) == 2
