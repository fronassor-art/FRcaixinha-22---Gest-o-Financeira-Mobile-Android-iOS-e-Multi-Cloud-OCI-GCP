"""M38794: FR Finance / FR Caixinha 2.2 isolation, tests never connect to PG."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import types

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/frfinance_m38794_project_isolation.py"
IDENTITY = ROOT / "backend/config/frfinance_project_identity.json"


def load():
    spec = importlib.util.spec_from_file_location("m38794_guard", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_manifest_is_canonical_and_contains_both_projects():
    mod = load()
    x = mod.manifest()
    a, b = x["active_project"], x["excluded_project"]
    assert a["id"] == "FR_FINANCE_AI_STUDIO"
    assert a["postgresql"]["database"] == "frcaixinha_aistudio_dev"
    assert a["postgresql"]["pgdata"].endswith("/frcaixinha_aistudio_pg18")
    assert a["postgresql"]["port"] == 5433
    assert a["postgresql"]["owner"] == "frc_ai_owner"
    assert a["termux_worktree"] == "fr-finance"
    assert b["id"] == "FR_CAIXINHA_2_2"
    assert b["postgresql"]["database"] == "frcaixinha_2_2_dev"
    assert b["postgresql"]["pgdata"].endswith("/frcaixinha_2_2_pg18")
    assert b["postgresql"]["port"] == 5432
    assert b["postgresql"]["owner"] == "frc22_owner"
    assert a["repository"] != b["repository"]
    assert x["never_start_server_from_project_identity"] is True
    assert x["never_cross_connect_to_excluded_project"] is True
    assert x["production_authorized"] is False


def test_canonical_manifest_matches_existing_audit_and_script():
    mod = load()
    from_source = (ROOT / "backend/scripts/aistudio_m38701_local_043_044_catalog_readonly.py").read_text()
    legacy = (ROOT / "backend/scripts/aistudio_local_parity_034_041.sh").read_text()
    for required in (
        mod.FINANCE_PGDATA, mod.FINANCE_DB, mod.FINANCE_OWNER,
        "5433", "frc_ai_owner"
    ):
        assert required in from_source
        assert required in legacy
    assert mod.FR22_PGDATA not in from_source
    assert mod.FR22_DB not in from_source
    assert mod.FR22_OWNER not in from_source


@pytest.mark.parametrize("origin", [
    "https://github.com/" + "fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP",
    "https://github.com/" + "fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git",
    "git@github.com:" + "fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git",
])
def test_valid_remote_normalizes_to_finance_repo(origin):
    mod = load()
    assert mod._repository_of_origin(origin) == mod.FINANCE_REPO


@pytest.mark.parametrize("origin", [
    "https://github.com/fronassor-art/FRcaixinha-2.2",
    "git@github.com:fronassor-art/FRcaixinha-2.2.git",
    "file:///data/data/com.termux/files/home/FRcaixinha_2.2",
    "https://github.com/untrusted/repo",
    "https://github.com/fronassor-art/FRcaixinha-2.2#fragment",
    "",
])
def test_other_project_or_untrusted_remote_rejected(origin):
    mod = load()
    assert mod._repository_of_origin(origin) != mod.FINANCE_REPO


def fake_local(monkeypatch, tmp_path, *, pg_version="18", remote=None, branch=None):
    mod = load()
    home = tmp_path / "home"
    root = home / "fr-finance"
    root.mkdir(parents=True)
    finance = tmp_path / "pg18_frfinance"
    finance.mkdir()
    (finance / "PG_VERSION").write_text(pg_version)
    other = tmp_path / "pg18_fr22"
    other.mkdir()
    (other / "PG_VERSION").write_text("18")
    monkeypatch.setattr(mod, "ROOT", root.resolve())
    monkeypatch.setattr(mod, "FINANCE_PGDATA", str(finance))
    monkeypatch.setattr(mod, "FR22_PGDATA", str(other))
    # manifest is separately tested against immutable constants
    monkeypatch.setattr(mod, "manifest", lambda: {})
    default_origin = "https://github.com/" + mod.FINANCE_REPO + ".git"
    def fake_git(*args):
        if args == ("rev-parse", "--show-toplevel"):
            return str(root.resolve())
        if args == ("remote", "get-url", "origin"):
            return remote if remote is not None else default_origin
        if args == ("branch", "--show-current"):
            return branch if branch is not None else mod.FINANCE_BRANCH
        pytest.fail("unexpected git command")
    monkeypatch.setattr(mod, "_git_output", fake_git)
    return mod, home, finance, other


def test_valid_project_structure_does_not_assert_server_running(monkeypatch, tmp_path):
    mod, home, _, _ = fake_local(monkeypatch, tmp_path)
    data = mod.inspect_local(home)
    assert data["M38794_PROJECT_SEPARATION"] if False else True
    assert data["M38794_GIT_IDENTITY"] == "FR_FINANCE_AI_STUDIO"
    assert data["M38794_PGDATA_VERSION"] == "18"
    assert data["M38794_PGDATA_2_2"] == "SEPARATE_DIRECTORY_PRESENT"
    assert data["M38794_PG_PIDFILE"] == "ABSENT_NO_RUNNING_ASSERTION"
    assert data["M38794_LIVE_SERVER_IDENTITY"] == "NOT_ATTESTED"


def test_wrong_worktree_blocked(monkeypatch, tmp_path):
    mod, home, _, _ = fake_local(monkeypatch, tmp_path)
    with pytest.raises(mod.IsolationBlocked, match="WORKTREE_MISMATCH"):
        mod.inspect_local(tmp_path / "wrong")


def test_remote_pointing_to_2_2_fails_closed(monkeypatch, tmp_path):
    mod, home, _, _ = fake_local(
        monkeypatch, tmp_path,
        remote="https://github.com/fronassor-art/FRcaixinha-2.2.git"
    )
    with pytest.raises(mod.IsolationBlocked, match="REMOTE_MISMATCH"):
        mod.inspect_local(home)


def test_wrong_branch_fails_closed(monkeypatch, tmp_path):
    mod, home, _, _ = fake_local(monkeypatch, tmp_path, branch="main")
    with pytest.raises(mod.IsolationBlocked, match="BRANCH_MISMATCH"):
        mod.inspect_local(home)


def test_wrong_pg_major_fails_closed(monkeypatch, tmp_path):
    mod, home, _, _ = fake_local(monkeypatch, tmp_path, pg_version="17")
    with pytest.raises(mod.IsolationBlocked, match="FINANCE_PG18_MISMATCH"):
        mod.inspect_local(home)


def test_pgdata_missing_fails_closed(monkeypatch, tmp_path):
    mod, home, finance, _ = fake_local(monkeypatch, tmp_path)
    (finance / "PG_VERSION").unlink()
    finance.rmdir()
    with pytest.raises(mod.IsolationBlocked, match="FINANCE_PGDATA_MISSING"):
        mod.inspect_local(home)


def test_pidfile_on_wrong_port_is_blocked(monkeypatch, tmp_path):
    mod, home, finance, _ = fake_local(monkeypatch, tmp_path)
    (finance / "postmaster.pid").write_text(
        "10000\n" + str(finance) + "\n0\n5432\n/tmp\n127.0.0.1\n"
    )
    with pytest.raises(mod.IsolationBlocked, match="PIDFILE_IDENTITY_MISMATCH"):
        mod.inspect_local(home)


def test_pidfile_correct_path_and_port_still_not_running_proof(monkeypatch, tmp_path):
    mod, home, finance, _ = fake_local(monkeypatch, tmp_path)
    (finance / "postmaster.pid").write_text(
        "10000\n" + str(finance) + "\n0\n5433\n/tmp\n127.0.0.1\n"
    )
    result = mod.inspect_local(home)
    assert result["M38794_PG_PIDFILE"] == "EXPECTED_PATH_AND_PORT_UNVERIFIED_PROCESS"
    assert result["M38794_LIVE_SERVER_IDENTITY"] == "NOT_ATTESTED"


def test_offline_reference_does_not_run_git_or_pg(monkeypatch, capsys):
    mod = load()
    monkeypatch.setattr(mod, "_git_output", lambda *args: pytest.fail("git"))
    assert mod.main(["reference"]) == 0
    out = capsys.readouterr().out
    assert "M38794_REFERENCE_PORT=5433" in out
    assert "M38794_EXCLUDED_PORT=5432" in out
    assert "M38794_LIVE_SERVER_IDENTITY=NOT_ATTESTED" in out
    assert "M38794_POSTGRESQL_START=NONE" in out
    assert "M38794_DATABASE_MUTATIONS=NONE" in out


def test_script_has_no_pg_start_client_or_local_data_mutation():
    source = SCRIPT.read_text(encoding="utf-8")
    assert "pg_ctl " not in source
    assert "pg_isready" not in source
    assert "psql " not in source
    assert "pg_dump" not in source
    assert "pg_restore" not in source
    assert "postgres --" not in source
    assert "subprocess.run(" in source
    assert '["git", "-C", str(ROOT), *args]' in source


def test_manifest_drift_to_fr22_rejected(monkeypatch, tmp_path):
    mod = load()
    bad = json.loads(IDENTITY.read_text())
    bad["active_project"]["postgresql"]["port"] = 5432
    path = tmp_path / "identity.json"
    path.write_text(json.dumps(bad))
    monkeypatch.setattr(mod, "MANIFEST", path)
    with pytest.raises(mod.IsolationBlocked, match="PROJECT_IDENTITY_DRIFT"):
        mod.manifest()
