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
        "api_report": lambda: {"M40190_STATUS": m.EXPECTED_API},
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
    for status in ("BLOCKED_TEST_AUTH_READINESS", "BLOCKED_HEALTH_IDENTITY", None):
        r = samples(api_report=lambda:{"M40190_STATUS":status})
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
              "M40530_FASTAPI_RESTART=NONE", "M40530_POSTGRESQL_RESTART=NONE"):
        assert s in code
    for s in ("psycopg.connect(", "asyncpg.connect(", "subprocess.Popen(",
              "os.kill(", "shell=True", "pg_ctl start", "pg_ctl stop",
              "pg_ctl restart", "requests.post(", "urllib.request.urlopen(",
              "run_migration("):
        assert s not in code
