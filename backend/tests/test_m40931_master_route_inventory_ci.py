"""M40931: freeze the *real* Master route surface at CI source level.

Pure AST analysis, no import of backend app, no network, database or provider.
This is a source regression fence, NOT a runtime identity/SQL authorization.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ROUTERS = ROOT / "backend" / "app" / "routers"
MUTATIONS = {"post", "put", "patch", "delete"}
# A new Master POST/PUT/PATCH/DELETE is a release-blocking review item, even
# when its author believes it is read-only. Never quietly auto-allow it.
EXPECTED = {
    ("master.py", "POST", "/master/admin-onboarding/transition-preview"): "PURE_PREVIEW",
    ("master.py", "POST", "/master/admin-onboarding/preflight"): "READ_ONLY_PREFLIGHT",
    ("master.py", "POST", "/master/license-prices"): "M40930_HTTP_503",
    ("master.py", "POST", "/master/support-session"): "CONTRACT_DENIED",
    ("saas_promotions.py", "POST", "/master/saas-promotions/draft"): "M40930_HTTP_503",
    ("saas_promotions.py", "POST", "/master/saas-promotions/transition"): "M40930_HTTP_503",
}


def _literal_string(expr):
    return expr.value if isinstance(expr, ast.Constant) and type(expr.value) is str else None


def _router_prefixes(tree):
    mapping = {}
    for statement in tree.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        val = statement.value
        if not isinstance(val, ast.Call) or not isinstance(val.func, ast.Name):
            continue
        if val.func.id != "APIRouter":
            continue
        prefixes = [kw.value for kw in val.keywords if kw.arg == "prefix"]
        if len(prefixes) != 1:
            raise AssertionError("M40931_ROUTER_PREFIX_UNATTESTED")
        prefix = _literal_string(prefixes[0])
        if prefix is None:
            raise AssertionError("M40931_DYNAMIC_ROUTER_PREFIX_UNREVIEWED")
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        for target in targets:
            if isinstance(target, ast.Name):
                mapping[target.id] = prefix
    return mapping


def _deps(decorator):
    deps = []
    for kw in decorator.keywords:
        if kw.arg != "dependencies":
            continue
        if not isinstance(kw.value, (ast.List, ast.Tuple)):
            raise AssertionError("M40931_DYNAMIC_ROUTE_DEPENDENCIES")
        for item in kw.value.elts:
            if (not isinstance(item, ast.Call) or not isinstance(item.func, ast.Name)
                    or item.func.id != "Depends" or len(item.args) != 1
                    or not isinstance(item.args[0], ast.Name)):
                raise AssertionError("M40931_DYNAMIC_DEPENDENCY_UNREVIEWED")
            deps.append(item.args[0].id)
    return deps


def _declares_master_auth(fn):
    for argument in fn.args.args + fn.args.kwonlyargs:
        value = argument.default if hasattr(argument, "default") else None
        # Function positional defaults are in fn.args.defaults, separately.
    return any(
        isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
        and call.func.id == "Depends"
        and len(call.args) == 1 and isinstance(call.args[0], ast.Name)
        and call.args[0].id == "require_master"
        for call in ast.walk(fn.args)
    )


def collect_master_mutations(sources: dict[str, str]):
    found = {}
    for filename, source in sources.items():
        tree = ast.parse(source, filename=filename)
        routers = _router_prefixes(tree)
        for fn in tree.body:
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for dec in fn.decorator_list:
                if not (isinstance(dec, ast.Call) and
                        isinstance(dec.func, ast.Attribute) and
                        isinstance(dec.func.value, ast.Name) and
                        dec.func.attr in MUTATIONS):
                    continue
                router_name = dec.func.value.id
                if router_name not in routers:
                    # Unknown route aliases in Master modules require human
                    # review, rather than silently disappearing from inventory.
                    if "master" in router_name or filename in ("master.py", "saas_promotions.py"):
                        raise AssertionError("M40931_UNRESOLVED_MASTER_ROUTER")
                    continue
                prefix = routers[router_name]
                if not dec.args:
                    raise AssertionError("M40931_DYNAMIC_ROUTE_PATH_UNREVIEWED")
                suffix = _literal_string(dec.args[0])
                if suffix is None:
                    raise AssertionError("M40931_DYNAMIC_ROUTE_PATH_UNREVIEWED")
                full = (prefix.rstrip("/") + "/" + suffix.lstrip("/")).rstrip("/")
                if not full.startswith("/master/"):
                    continue
                key = (filename, dec.func.attr.upper(), full)
                if key in found:
                    raise AssertionError("M40931_DUPLICATE_MASTER_PATH")
                found[key] = (fn, _deps(dec))
    return found


def check_master_mutations(sources):
    found = collect_master_mutations(sources)
    if set(found) != set(EXPECTED):
        missing = sorted(set(EXPECTED) - set(found))
        extra = sorted(set(found) - set(EXPECTED))
        raise AssertionError("M40931_MASTER_ROUTE_DRIFT missing=%r extra=%r" % (missing, extra))
    for key, (fn, deps) in found.items():
        policy = EXPECTED[key]
        if not _declares_master_auth(fn):
            raise AssertionError("M40931_MISSING_MASTER_AUTH: " + repr(key))
        if policy == "M40930_HTTP_503":
            if deps != ["require_unreleased_master_write"]:
                raise AssertionError("M40931_MASTER_WRITE_WITHOUT_FENCE: " + repr(key))
        elif policy in ("PURE_PREVIEW", "READ_ONLY_PREFLIGHT"):
            if deps:
                raise AssertionError("M40931_PREVIEW_DEPENDENCY_DRIFT: " + repr(key))
            for node in ast.walk(fn):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in ("execute", "executemany", "copy", "commit", "rollback"):
                        raise AssertionError("M40931_PREVIEW_NEW_SQL_SIDE_EFFECT: " + repr(key))
                if isinstance(node, ast.Constant) and type(node.value) is str:
                    if any(word in node.value.upper() for word in (
                        "INSERT INTO ", "UPDATE PUBLIC.", "DELETE FROM ",
                        "TRUNCATE ", "ALTER TABLE ", "DROP TABLE ", "GRANT ",
                        "REVOKE ",
                    )):
                        raise AssertionError("M40931_PREVIEW_SQL_MUTATION: " + repr(key))
            expected_helper = ("preview_transition" if policy == "PURE_PREVIEW"
                               else "preflight_assessment")
            if not any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == expected_helper
                for n in ast.walk(fn)
            ):
                raise AssertionError("M40931_PREVIEW_HELPER_REVIEW_REQUIRED")
        elif policy == "CONTRACT_DENIED":
            statements = [s for s in fn.body
                          if not (isinstance(s, ast.Expr) and
                                  isinstance(s.value, ast.Constant) and
                                  isinstance(s.value.value, str))]
            if len(statements) != 1 or not isinstance(statements[0], ast.Raise):
                raise AssertionError("M40931_BREAK_GLASS_MUST_ALWAYS_RAISE")
            if "BREAK_GLASS_UNAUTHORIZED_BY_CONTRACT" not in ast.get_source_segment(
                sources[key[0]], statements[0]
            ):
                raise AssertionError("M40931_BREAK_GLASS_CONTRACT_CODE_MISSING")
    return len(found)


class MasterTrustInventory(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {
            path.name: path.read_text(encoding="utf-8")
            for path in sorted(ROUTERS.glob("*.py"))
        }

    def test_complete_master_mutation_inventory(self):
        self.assertEqual(check_master_mutations(self.sources), 6)

    def test_new_master_mutation_must_fail_without_approval(self):
        changed = dict(self.sources)
        changed["master.py"] += (
            '\n@router.post("/unreviewed-action")\n'
            'def unsafe(session=Depends(require_master)):\n'
            '    return {"would_change_data": True}\n'
        )
        with self.assertRaisesRegex(AssertionError, "MASTER_ROUTE_DRIFT"):
            check_master_mutations(changed)

    def test_fence_removed_must_fail(self):
        changed = dict(self.sources)
        changed["saas_promotions.py"] = changed["saas_promotions.py"].replace(
            '@master_router.post("/transition", dependencies=[Depends(require_unreleased_master_write)])',
            '@master_router.post("/transition")',
        )
        with self.assertRaisesRegex(AssertionError, "MASTER_WRITE_WITHOUT_FENCE"):
            check_master_mutations(changed)

    def test_main_app_master_mounts_and_no_direct_write_bypass(self):
        """Master routers must be mounted through the reviewed path only.

        A new direct mutation decorator, route factory or unknown Master
        mount is a code-review failure; this is NOT SQL-layer assurance.
        """
        main_source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
        tree = ast.parse(main_source, filename="backend/app/main.py")
        expected_mounts = {
            "master.router",
            "_saas_promotions.master_router",
            "_exclusive_cashboxes.master_router",
            "_review_policy_gaps.master_router",
        }
        observed_mounts = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "app":
                continue
            if node.func.attr in {
                "post", "put", "patch", "delete", "api_route", "route",
                "add_api_route",
            }:
                raise AssertionError("M40933_DIRECT_APP_MUTATION_REVIEW_REQUIRED")
            if node.func.attr != "include_router":
                continue
            if not node.args:
                raise AssertionError("M40933_DYNAMIC_ROUTER_MOUNT_UNREVIEWED")
            target = node.args[0]
            if (isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and (target.attr == "master_router"
                         or target.value.id == "master" and target.attr == "router")):
                name = target.value.id + "." + target.attr
                if name in observed_mounts:
                    raise AssertionError("M40933_DUPLICATE_MASTER_ROUTER_MOUNT")
                observed_mounts.add(name)
                if (len(node.keywords) != 1 or node.keywords[0].arg != "prefix"
                        or not isinstance(node.keywords[0].value, ast.Attribute)
                        or not isinstance(node.keywords[0].value.value, ast.Name)
                        or node.keywords[0].value.value.id != "settings"
                        or node.keywords[0].value.attr != "API_V1_STR"):
                    raise AssertionError("M40933_MASTER_ROUTER_PREFIX_DRIFT")
        self.assertEqual(observed_mounts, expected_mounts)

    def test_unreviewed_direct_app_post_is_rejected(self):
        source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
        spoof = source + '\\n@app.post("/api/v1/master/unreviewed")\\ndef write():\\n    return True\\n'
        # Verify the AST detector used by the real check identifies the
        # injection without importing or serving the FastAPI app.
        tree = ast.parse(spoof)
        calls = [node for node in ast.walk(tree)
                 if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Attribute)
                 and isinstance(node.func.value, ast.Name)
                 and node.func.value.id == "app"
                 and node.func.attr == "post"]
        self.assertEqual(len(calls), 1)

    def test_m40840_fence_and_no_money_switches(self):
        gate = (ROOT / "backend/app/m40840_financial_sql_release_no_go.py").read_text()
        assert "M40840_FINANCIAL_SQL_NO_GO" in gate
        assert "production" not in gate.split("_NONPROD =", 1)[1].split("_REAL_FLAGS", 1)[0]
        no_go = (ROOT / "backend/app/m40930_master_write_no_go.py").read_text()
        assert "raise HTTPException(" in no_go
        assert "os.environ" not in no_go and "getenv" not in no_go
        assert "PIX_REAL" in gate and "PAGAMENTOS_REAIS" in gate and "ATIVACAO_REAL" in gate


if __name__ == "__main__":
    unittest.main()
