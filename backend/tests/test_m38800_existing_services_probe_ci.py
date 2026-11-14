"""M38800-M38879: keep FR Finance inside one worktree/PG18/FastAPI."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import types
import urllib.error

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/frfinance_m38800_existing_services_probe.py"


def load(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("m38800_services", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_offline_does_not_contact_pg_or_fastapi(monkeypatch, capsys):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "_pg_ready", lambda: pytest.fail("PG must not be called"))
    monkeypatch.setattr(mod, "_get_local_json", lambda *_: pytest.fail("HTTP must not be called"))
    monkeypatch.setattr(mod.identity, "inspect_local", lambda _: pytest.fail("no local inspect"))
    assert mod.main(["offline"]) == 0
    out = capsys.readouterr().out
    assert "M38800_FASTAPI_8000=NOT_QUERIED" in out
    assert "M38800_NEW_DATABASE=NONE" in out
    assert "M38800_NEW_REPOSITORY=NONE" in out
    assert "M38800_NEW_WORKTREE=NONE" in out
    assert "M38800_NEW_FASTAPI=NONE" in out


@pytest.mark.parametrize("args", [
    ["local"], ["local", "CREATE_DATABASE"],
    ["offline", "AUTHORIZE_FRFINANCE_EXISTING_SERVICES_READONLY"],
])
def test_explicit_readonly_gate(monkeypatch, args):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod, "probe", lambda: pytest.fail("not authorized"))
    assert mod.main(args) == 2


def test_wrong_repository_blocked_before_any_pg_or_api_probe(monkeypatch, capsys):
    mod = load(monkeypatch)
    def blocked(_):
        raise mod.identity.IsolationBlocked("M38794_REMOTE_MISMATCH")
    monkeypatch.setattr(mod.identity, "inspect_local", blocked)
    monkeypatch.setattr(mod, "_pg_ready", lambda: pytest.fail("no Pg"))
    monkeypatch.setattr(mod, "_get_local_json", lambda _: pytest.fail("no HTTP"))
    assert mod.main(["local", mod.AUTH]) == 2
    assert "M38800_AUDIT=BLOCKED_ISOLATION" in capsys.readouterr().out


@pytest.mark.parametrize("pg_status", [
    "ACCEPTING", "NO_RESPONSE", "REJECTING", "UNKNOWN", "UNAVAILABLE",
])
@pytest.mark.parametrize("http_status,health_body", [
    ("HTTP_200_JSON", {"app": "FR Finance", "status": "ONLINE"}),
    ("HTTP_200_JSON", {"app": "FR Caixinha 2.2", "status": "ONLINE"}),
    ("HTTP_200_JSON", {"app": "FR Finance", "status": "OFFLINE"}),
    ("UNREACHABLE", None),
    ("HTTP_503", None),
    ("INVALID_BODY", None),
])
def test_api_pg_matrix_never_fabricates_readiness(
        monkeypatch, pg_status, http_status, health_body):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.identity, "inspect_local",
                        lambda _: {"M38794_GIT_IDENTITY": "FR_FINANCE_AI_STUDIO",
                                   "M38794_PGDATA_IDENTITY": "FR_FINANCE_AI_STUDIO_PG18"})
    monkeypatch.setattr(mod, "_pg_ready", lambda: pg_status)
    calls = []
    def http(url):
        calls.append(url)
        if url == mod.API_HEALTH_URL:
            return http_status, health_body
        return "HTTP_503", None
    monkeypatch.setattr(mod, "_get_local_json", http)
    report = mod.probe()
    assert report["M38800_PG_5433"] == pg_status
    assert report["M38800_PRODUCTION"] == "BLOCKED"
    assert report["M38800_PG_SERVER_IDENTITY"] == "NOT_ATTESTED_BY_PG_ISREADY"
    if http_status == "HTTP_200_JSON" and health_body["app"] == "FR Caixinha 2.2":
        assert report["M38800_FASTAPI_8000"] == "WRONG_APPLICATION_ON_8000"
        assert report["M38800_NEXT_STEP"] == "BLOCKED_VERIFY_EXISTING_API_8000"
    if pg_status != "ACCEPTING":
        assert report["M38800_FASTAPI_READY"] == "NOT_CHECKED_POSTGRES_UNAVAILABLE"
        assert mod.API_READY_URL not in calls
        assert report["M38800_NEXT_STEP"] in (
            "CHECK_EXISTING_POSTGRES_5433_FIRST", "BLOCKED_VERIFY_EXISTING_API_8000",
        )
    if http_status != "HTTP_200_JSON" or health_body.get("status") != "ONLINE" or health_body.get("app") != "FR Finance":
        assert mod.API_READY_URL not in calls


@pytest.mark.parametrize("ready_status,payload,expected", [
    ("HTTP_200_JSON", {"status": "READY_FOR_TEST_AUTH", "scope": "LOCAL_HOMOLOGATION_ONLY"},
     "READY_FOR_TEST_AUTH"),
    ("HTTP_200_JSON", {"status": "READY_FOR_TEST_AUTH", "scope": "PRODUCTION"},
     "NOT_ATTESTED"),
    ("HTTP_200_JSON", {"status": "OTHER", "scope": "LOCAL_HOMOLOGATION_ONLY"},
     "NOT_ATTESTED"),
    ("HTTP_503", None, "HTTP_503_NOT_READY"),
    ("UNREACHABLE", None, "NO_RESPONSE"),
    ("INVALID_BODY", None, "NOT_ATTESTED"),
])
def test_ready_requires_original_existing_api_and_test_only_scope(
        monkeypatch, ready_status, payload, expected):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.identity, "inspect_local",
                        lambda _: {"M38794_GIT_IDENTITY": "FR_FINANCE_AI_STUDIO",
                                   "M38794_PGDATA_IDENTITY": "FR_FINANCE_AI_STUDIO_PG18"})
    monkeypatch.setattr(mod, "_pg_ready", lambda: "ACCEPTING")
    def fake(url):
        if url == mod.API_HEALTH_URL:
            return "HTTP_200_JSON", {"app": "FR Finance", "status": "ONLINE"}
        return ready_status, payload
    monkeypatch.setattr(mod, "_get_local_json", fake)
    report = mod.probe()
    assert report["M38800_FASTAPI_8000"] == "ONLINE_FR_FINANCE"
    assert report["M38800_FASTAPI_READY"] == expected
    if expected == "READY_FOR_TEST_AUTH":
        assert report["M38800_NEXT_STEP"] == "CONTINUE_EXISTING_FR_FINANCE_HOMOLOGATION"
    else:
        assert report["M38800_NEXT_STEP"] == "CHECK_EXISTING_API_CONFIGURATION"


@pytest.mark.parametrize("ret,expected", [
    (0, "ACCEPTING"), (1, "REJECTING"), (2, "NO_RESPONSE"),
    (3, "UNKNOWN"), (127, "UNKNOWN"),
])
def test_pg_isready_is_fixed_5433_without_env_leak(monkeypatch, ret, expected):
    mod = load(monkeypatch)
    monkeypatch.setenv("PGHOST", "foreign")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.setenv("PGPASSWORD", "fake_sensitive")
    monkeypatch.setenv("PGDATABASE", "frcaixinha_2_2_dev")
    calls = []
    def fake_run(argv, **kw):
        calls.append((argv,kw))
        return types.SimpleNamespace(returncode=ret, stdout="", stderr="")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    assert mod._pg_ready() == expected
    argv, options = calls[0]
    assert argv == ["pg_isready", "-q", "-t", "3", "-h", "127.0.0.1", "-p", "5433",
                    "-U", "frc_ai_owner", "-d", "frcaixinha_aistudio_dev"]
    assert options["capture_output"] is True
    assert all(not k.startswith("PG") for k in options["env"])
    assert "5432" not in argv


def test_pg_missing_tool_is_not_misinterpreted_as_corruption(monkeypatch):
    mod = load(monkeypatch)
    monkeypatch.setattr(mod.subprocess, "run",
                        lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError()))
    assert mod._pg_ready() == "UNAVAILABLE"


def test_disallow_unrelated_url_and_http_redirect(monkeypatch):
    mod = load(monkeypatch)
    with pytest.raises(mod.ExistingServiceBlocked, match="UNAPPROVED_LOCAL_URL"):
        mod._get_local_json("http://127.0.0.1:5432/api/health")
    assert mod._NoRedirects().redirect_request(None,None,302,"Found",{}, 
        "https://example.org") is None


def test_failing_http_probe_never_prints_exception_body(monkeypatch, capsys):
    mod = load(monkeypatch)
    class Opener:
        def open(self, *_args, **_kw):
            raise urllib.error.HTTPError(mod.API_HEALTH_URL, 503, "PRIVATE",
                                         None, None)
    monkeypatch.setattr(mod.urllib.request, "build_opener", lambda *args: Opener())
    assert mod._get_local_json(mod.API_HEALTH_URL) == ("HTTP_503", None)
    assert "PRIVATE" not in capsys.readouterr().out


def test_fake_health_json_consumed_with_hard_max(monkeypatch):
    mod = load(monkeypatch)
    class Response:
        status = 200
        def __init__(self, payload):
            self.payload = payload
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, size):
            return self.payload[:size]
    class Opener:
        def __init__(self, data):
            self.data = data
        def open(self, *_args, **_kw):
            return Response(self.data)
    monkeypatch.setattr(mod.urllib.request, "build_opener", 
                        lambda *args: Opener(b'{"app":"FR Finance","status":"ONLINE"}'))
    assert mod._get_local_json(mod.API_HEALTH_URL) == (
        "HTTP_200_JSON", {"app": "FR Finance", "status": "ONLINE"})
    monkeypatch.setattr(mod.urllib.request, "build_opener", 
                        lambda *args: Opener(b"x" * (mod.MAX_RESPONSE_BYTES + 2)))
    assert mod._get_local_json(mod.API_HEALTH_URL) == ("INVALID_BODY", None)


def test_source_cannot_start_pg_or_api_or_migrate():
    src = SCRIPT.read_text(encoding="utf-8")
    for forbidden in (
        "pg_ctl start", "pg_ctl stop", "initdb", "createdb",
        "CREATE DATABASE", "CREATE ROLE", "CREATE SCHEMA",
        "psql -", "pg_resetwal", "uvicorn app.main",
        "mkdir(", "shutil.copytree(", "git clone", "git init",
        "os.remove(", "unlink(", "os.rename(", "open('wb'",
    ):
        assert forbidden not in src
    assert "127.0.0.1:8000/api/health" in src
    assert '"-p", "5433"' in src
