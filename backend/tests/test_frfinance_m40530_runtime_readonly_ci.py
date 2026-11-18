"""M40530 read-only preflight: synthetic tests only; no actual services."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "frfinance_m40530_runtime_readonly.py"
spec = spec_from_file_location("m40530", SOURCE)
assert spec and spec.loader
m = module_from_spec(spec)
spec.loader.exec_module(m)


def samples(**changes):
    callbacks = {
        "project": lambda: m.EXPECTED_PROJECT,
        "binaries": lambda: m.EXPECTED_BINARIES,
        "ctl_status": lambda: m.EXPECTED_CTL,
        "pg_ready": lambda: m.EXPECTED_READY,
        "api_report": lambda: {"M40530_API_STATUS": m.EXPECTED_API},
    }
    callbacks.update(changes)
    return m.assess(**callbacks)


def test_success_is_not_production_approval():
    r = samples()
    assert r["M40530_STATUS"] == "PASS_LOCAL_READONLY_NOT_PRODUCTION"
    assert r["M40530_PRODUCTION"] == "BLOCKED"
    assert r["M40530_DB_AUTHENTICATED_IDENTITY"] == "NOT_ATTESTED"
    assert r["M40530_RUNTIME_GIT_SHA"] == "NOT_ATTESTED"
    assert r["M40530_REAL_FINANCE"] == "OFF"


def test_reject_wrong_project_without_probes():
    def never():
        raise AssertionError("Forbidden probe")
    r = samples(project=lambda:"FR_CAIXINHA_2_2", binaries=never,
                ctl_status=never, pg_ready=never, api_report=never)
    assert r["M40530_STATUS"] == "BLOCKED_PROJECT_ISOLATION"
    assert r["M40530_API"] == "SKIPPED"


def test_reject_missing_tools_without_pg_or_api():
    def never():
        raise AssertionError("Forbidden probe")
    r = samples(binaries=lambda:"PG_TOOLS_NOT_ATTESTED",
                ctl_status=never, pg_ready=never, api_report=never)
    assert r["M40530_STATUS"] == "BLOCKED_PG_BINARIES"


def test_reject_wrong_pg_port_or_stopped_cluster_without_api():
    def never():
        raise AssertionError("Forbidden API probe")
    for c, pr in [
        ("ORIGINAL_PGDATA_PROCESS_REPORTED_STOPPED", m.EXPECTED_READY),
        (m.EXPECTED_CTL, "PORT_5433_NO_RESPONSE"),
    ]:
        r = samples(ctl_status=lambda:c, pg_ready=lambda:pr, api_report=never)
        assert r["M40530_STATUS"] == "BLOCKED_ORIGINAL_PG18_NOT_READY"
        assert r["M40530_API"] == "SKIPPED"


def test_reject_http_readiness_problems():
    for status in ("BLOCKED_API_MARKERS", "BLOCKED_HEALTH_IDENTITY", None):
        r = samples(api_report=lambda:{"M40530_API_STATUS":status})
        assert r["M40530_STATUS"] == "BLOCKED_API_OR_AUTH_READINESS"
        assert r["M40530_API"] == "NOT_ATTESTED_LOCAL_API"


def test_exceptions_fail_closed():
    def boom():
        raise RuntimeError("no")
    for kwargs, expected in [
        ({"project":boom},"BLOCKED_PROJECT_ISOLATION"),
        ({"binaries":boom},"BLOCKED_PG_BINARIES"),
        ({"ctl_status":boom},"BLOCKED_PG_STATUS_PROBE"),
        ({"api_report":boom},"BLOCKED_API_OR_AUTH_READINESS"),
    ]:
        assert samples(**kwargs)["M40530_STATUS"] == expected


def test_default_cli_does_not_import_termux_or_connect():
    p = subprocess.run([sys.executable, str(SOURCE)],
                       capture_output=True, text=True, check=True)
    assert "PASS_SOURCE_ONLY_NOT_RUNTIME_ATTESTED" in p.stdout
    assert "M40530_HTTP_POST=NONE" in p.stdout
    assert "M40530_DB_SQL=NONE" in p.stdout
    assert "M40530_PRODUCTION=BLOCKED" in p.stdout


def test_no_mutators_in_source():
    code = SOURCE.read_text(encoding="utf-8")
    for s in ("native_termux", "identity", "pg_ctl_status", "pg_isready_status",
              "M40530_MIGRATIONS=NONE", "M40530_PG_5432_FR22=NOT_ACCESSED",
              "M40530_FASTAPI_RESTART=NONE", "M40530_POSTGRESQL_RESTART=NONE",
              "M40530_HTTP_READY_ROUTE=NEVER_CALLED"):
        assert s in code
    for s in ("psycopg.connect(", "asyncpg.connect(", "subprocess.Popen(",
              "os.kill(", "shell=True", "pg_ctl start", "pg_ctl stop",
              "pg_ctl restart", "requests.post(", "urllib.request.urlopen(",
              "run_migration("):
        assert s not in code


def test_original_cli_bootstraps_repo_import_without_pythonpath(tmp_path):
    """Termux script path must work with isolated Python import paths."""
    code = (
        "import runpy, sys; "
        "ns=runpy.run_path(sys.argv[1], run_name='m40530_import_probe'); "
        "import backend.scripts.frfinance_m40150_original_pg18_status_readonly; "
        "print('M40530_ORIGINAL_IMPORTS=PASS')"
    )
    process = subprocess.run(
        [sys.executable, "-I", "-c", code, str(SOURCE)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    assert "M40530_ORIGINAL_IMPORTS=PASS" in process.stdout


def test_live_api_probe_only_queries_no_db_endpoints(monkeypatch):
    from backend.scripts import frfinance_m40190_operational_readonly_checkpoint as old
    from backend.scripts import frfinance_m40080_loaded_source_readonly as fingerprints
    from backend.app.m39700_runtime_contract import checkpoint_payload, EXPECTED_GET

    hashes = {key: "a" * 64 for key in (
        "main_py_sha256_at_import",
        "review_router_sha256_at_import",
        "marker_py_sha256_at_import",
    )}
    marker = {
        "product": "FR Finance",
        "workstream": "AI_STUDIO",
        "contract": "FR_FINANCE_M40080_LOADED_SOURCE_V1",
        "source_fingerprints_captured_on_import": True,
        **hashes,
        "git_commit_verified": False,
        "executable_bytecode_attested": False,
        "process_owner_verified": False,
        "real_session_revocation_attested": False,
        "review_policy_ratified": False,
        "financial_approval_enabled": False,
        "pix_real_enabled": False,
        "production_authorized": False,
    }
    docs = {
        old.HEALTH: (200, {"app": "FR Finance", "status": "ONLINE"}),
        old.CHECKPOINT: (200, checkpoint_payload()),
        old.MARKER: (200, marker),
        old.ROUTES: (200, {"paths": {path: {"get": {}} for path in EXPECTED_GET}}),
    }
    paths = []
    def get(path):
        assert path != old.READY, "M40530 must never query database-backed readiness"
        paths.append(path)
        return docs[path]
    monkeypatch.setattr(old, "safe_get", get)
    monkeypatch.setattr(fingerprints, "local_hashes", lambda: hashes)
    assert m.api_no_database_probe()["M40530_API_STATUS"] == m.EXPECTED_API
    assert paths == [old.HEALTH, old.CHECKPOINT, old.MARKER, old.ROUTES]


def test_api_probe_fails_without_valid_marker_and_skips_ready(monkeypatch):
    from backend.scripts import frfinance_m40190_operational_readonly_checkpoint as old
    from backend.scripts import frfinance_m40080_loaded_source_readonly as fingerprints
    monkeypatch.setattr(fingerprints, "local_hashes", lambda: {"bad": "x"})
    queried = []
    def get(path):
        queried.append(path)
        return (200, {"app": "FR Finance", "status": "ONLINE"})
    monkeypatch.setattr(old, "safe_get", get)
    assert m.api_no_database_probe()["M40530_API_STATUS"] == "BLOCKED_API_MARKERS"
    assert queried == []
