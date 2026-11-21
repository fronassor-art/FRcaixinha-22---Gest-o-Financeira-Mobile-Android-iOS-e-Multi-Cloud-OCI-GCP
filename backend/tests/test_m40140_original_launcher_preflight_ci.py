"""M40140: synthetic project/launcher/config gate, no production IO."""
from pathlib import Path
import os
import pytest

from backend.scripts import frfinance_m40140_original_launcher_preflight_readonly as m


def test_original_launcher_static_contract():
    assert m.launcher_snapshot() == "PASS_M38801_ORIGINAL_STATIC_CONTRACT"
    assert m.legacy_snapshot() == "HISTORIC_WORKTREE_CONTROL_DO_NOT_EXECUTE"


def test_changed_launcher_fails_closed(tmp_path):
    file = tmp_path / "run.sh"
    file.write_text("#!/bin/sh\necho bad\n", encoding="utf-8")
    assert m.launcher_snapshot(file) == "BLOCKED_LAUNCHER_CONTRACT_DRIFT"
    assert m.launcher_snapshot(tmp_path / "no.sh") == "BLOCKED_LAUNCHER_ABSENT_OR_LINK"
    link = tmp_path / "link.sh"
    link.symlink_to(file)
    assert m.launcher_snapshot(link) == "BLOCKED_LAUNCHER_ABSENT_OR_LINK"


def test_env_metadata_only(tmp_path):
    target = tmp_path / "api.env"
    assert m.env_file_snapshot(target) == "ABSENT_NO_AUTH_CONFIG_ATTESTATION"
    target.write_text("SENSITIVE_VALUE=never_print_me\n", encoding="utf-8")
    target.chmod(0o600)
    assert m.env_file_snapshot(target) == "PRIVATE_FILE_PRESENT_CONTENT_NOT_READ"
    target.chmod(0o644)
    assert m.env_file_snapshot(target) == "BLOCKED_ENV_OWNER_OR_PERMISSIONS"
    target.chmod(0o600)
    link = tmp_path / "link"
    link.symlink_to(target)
    assert m.env_file_snapshot(link) == "BLOCKED_ENV_SYMLINK"


def test_identity_static_only():
    good = {
        "M38794_GIT_IDENTITY": "FR_FINANCE_AI_STUDIO",
        "M38794_PGDATA_IDENTITY": "FR_FINANCE_AI_STUDIO_PG18",
        "M38794_PGDATA_VERSION": "18",
    }
    assert m.local_identity(probe=lambda _: good) == "PASS_STATIC_FR_FINANCE_ONLY"
    assert m.local_identity(probe=lambda _: {
        **good, "M38794_PGDATA_VERSION": "17"
    }) == "BLOCKED_ORIGINAL_IDENTITY"
    def blocked(_):
        raise m.IsolationBlocked("no private info")
    assert m.local_identity(probe=blocked) == "BLOCKED_ORIGINAL_IDENTITY"


def defaults(**updates):
    params = dict(
        identity=lambda: "PASS_STATIC_FR_FINANCE_ONLY",
        launcher=lambda: "PASS_M38801_ORIGINAL_STATIC_CONTRACT",
        legacy=lambda: "HISTORIC_WORKTREE_CONTROL_DO_NOT_EXECUTE",
        env=lambda: "PRIVATE_FILE_PRESENT_CONTENT_NOT_READ",
        port=lambda: "TCP_CONNECTION_REFUSED",
        pgtools=lambda: "PG_TOOLS_LOCATED_NOT_EXECUTED",
    )
    params.update(updates)
    return m.report(**params)


def test_static_checks_never_authorize_start_or_restart():
    r = defaults()
    assert r["M40140_STATUS"] == (
        "BLOCKED_LIVE_PG_AND_RUNTIME_NOT_ATTESTED_NO_START_APPROVAL")
    assert r["M40140_LAUNCH_AUTHORIZED"] == "FALSE"
    assert r["M40140_RESTART_AUTHORIZED"] == "FALSE"
    assert r["M40140_PG_LIVE_IDENTITY"] == "NOT_ATTESTED"


@pytest.mark.parametrize("overrides,expected", [
    ({"identity": lambda: "BLOCKED_ORIGINAL_IDENTITY"}, "BLOCKED_PROJECT_IDENTITY"),
    ({"launcher": lambda: "BLOCKED_LAUNCHER_CONTRACT_DRIFT"}, "BLOCKED_LAUNCHER_SOURCE"),
    ({"env": lambda: "BLOCKED_ENV_SYMLINK"}, "BLOCKED_ENV_METADATA"),
    ({"port": lambda: "TCP_HANDSHAKE_ACCEPTED"}, "BLOCKED_PORT_ALREADY_OCCUPIED"),
    ({"port": lambda: "TCP_CONNECT_TIMEOUT"}, "BLOCKED_PORT_NOT_STABLY_AVAILABLE"),
    ({"pgtools": lambda: "PG_TOOLS_NOT_ATTESTED"}, "BLOCKED_DEPENDENCY_DISCOVERY"),
])
def test_guards(overrides, expected):
    assert defaults(**overrides)["M40140_STATUS"] == expected


def test_no_env_does_not_attest_auth_config():
    r = defaults(env=lambda: "ABSENT_NO_AUTH_CONFIG_ATTESTATION")
    assert r["M40140_API_ENV_METADATA"] == "ABSENT_NO_AUTH_CONFIG_ATTESTATION"
    assert r["M40140_LAUNCH_AUTHORIZED"] == "FALSE"


def test_bad_socket_value_fails_closed():
    r = defaults(port=lambda: "UNEXPECTED")
    assert r["M40140_PORT_8000"] == "TCP_NOT_ATTESTED"
    assert r["M40140_STATUS"] == "BLOCKED_PORT_NOT_STABLY_AVAILABLE"


def test_native_gate(monkeypatch, capsys):
    monkeypatch.setattr(m, "native_termux", lambda: False)
    assert m.main(["--source-only"]) == 0
    assert "M40140_RUNTIME=NOT_ATTESTED" in capsys.readouterr().out
    assert m.main([]) == 2


def test_no_running_control_or_db_access_in_script():
    script = (Path(__file__).resolve().parents[2] /
        "backend/scripts/frfinance_m40140_original_launcher_preflight_readonly.py"
    ).read_text(encoding="utf-8")
    for required in (
        "M40140_DATABASE_CONNECTIONS=NONE", "M40140_LOCAL_DB_WRITES=NONE",
        "M40140_MIGRATIONS=NONE", "M40140_SERVICE_START_STOP=NONE",
        "M40140_FASTAPI_RESTART=NONE", "M40140_PIX_REAL=OFF",
        "M40140_LAUNCH_AUTHORIZED", "M40140_PRODUCTION=BLOCKED",
    ):
        assert required in script
    for forbidden in (
        "os.kill(", "subprocess.run(", "subprocess.Popen(", "psycopg.connect(",
        "asyncpg.connect(", "os.system(", "shell=True", "pg_ctl -D", "pg_ctl status",
        "read_text(ENV_FILE)", "ENV_FILE.read_text(", "print(os.environ)",
    ):
        assert forbidden not in script
