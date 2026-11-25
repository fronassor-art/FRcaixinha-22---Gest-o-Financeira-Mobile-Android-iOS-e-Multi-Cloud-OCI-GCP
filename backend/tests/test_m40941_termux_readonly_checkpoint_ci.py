"""M40941 harden Termux read-only checkpoint before any DB-change proposal."""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys

import pytest
from scripts.frfinance_m40941_termux_post_sync_checkpoint_readonly import (
    BRANCH, CheckpointBlocked, ORIGINS, TERMUX,
    evaluate, local_git, native_termux,
)

ROOT=Path(__file__).resolve().parents[2]
RUNNER=ROOT/"backend/scripts/frfinance_m40941_termux_post_sync_checkpoint_readonly.py"
DOC=ROOT/"docs/FR_FINANCE_M40941_TERMUX_CHECKPOINT_SOURCE_ONLY.md"
CI=ROOT/".github/workflows/frfinance-m40941-termux-readonly-checkpoint-ci.yml"
SHA="f"*40


def fixture_git(change:dict|None=None):
    expected={
        ("rev-parse","--show-toplevel"):str(TERMUX/"fr-finance"),
        ("branch","--show-current"):BRANCH,
        ("remote","get-url","origin"):sorted(ORIGINS)[0],
        ("rev-parse","HEAD"):SHA,
        ("status","--porcelain","--untracked-files=no"):"",
    }
    expected.update(change or {})
    return lambda *args: expected[args]


def test_non_termux_execution_fail_closed_without_system_effects():
    result=subprocess.run([sys.executable,"-B",str(RUNNER),
                           "--expected-head",SHA],capture_output=True,
                          text=True,timeout=10,
                          env={"PATH":os.environ.get("PATH","")})
    assert result.returncode==2
    assert "M40941_STATUS=BLOCKED_" in result.stdout
    assert "M40941_NO_DATABASE_OR_MIGRATION_ACTIONS=CONFIRMED_BY_DESIGN" in result.stdout


def test_source_only_invariants_without_real_termux():
    root=TERMUX/"fr-finance"
    env={"PREFIX":"/data/data/com.termux/files/usr","HOME":str(TERMUX)}
    # virtual fixture: never claim that this Github CI is native Termux.
    assert native_termux(env,TERMUX,root) is False


@pytest.mark.parametrize("change",[
    {("rev-parse","--show-toplevel"):"/tmp/other"},
    {("branch","--show-current"):"main"},
    {("remote","get-url","origin"):"https://github.com/other/repo.git"},
    {("rev-parse","HEAD"):"a"*40},
    {("status","--porcelain","--untracked-files=no"):" M backend/app/main.py"},
])
def test_wrong_worktree_branch_origin_sha_or_dirty_state_never_passes(change,monkeypatch):
    import scripts.frfinance_m40941_termux_post_sync_checkpoint_readonly as mod
    monkeypatch.setattr(mod,"native_termux",lambda *args:True)
    with pytest.raises(CheckpointBlocked):
        evaluate(
            env={},home=TERMUX,root=TERMUX/"fr-finance",
            expected_head=SHA,git_read=fixture_git(change)
        )


def test_valid_synthetic_metadata_still_never_claims_go(monkeypatch):
    import scripts.frfinance_m40941_termux_post_sync_checkpoint_readonly as mod
    monkeypatch.setattr(mod,"native_termux",lambda *args:True)
    observed,m=evaluate(
        env={},home=TERMUX,root=TERMUX/"fr-finance",
        expected_head=SHA,git_read=fixture_git()
    )
    assert observed==SHA
    assert m["M40941_PLAN"]=="VALIDATED_NO_GO"
    assert m["M40941_PRODUCTION"]=="BLOCKED"
    assert m["M40941_MIGRATIONS"]=="NONE"
    assert m["M40941_DB_CONNECTIONS"]=="NONE"
    assert m["M40941_SERVICE_RESTARTS"]=="NONE"


def test_no_git_mutations_and_doc_policy():
    source=RUNNER.read_text(encoding="utf-8")
    for forbidden in ("asyncpg","psycopg","requests","git fetch","git merge",
                      "git checkout","pg_ctl","os.kill","subprocess.Popen",
                      "CREATE DATABASE", "ALTER TABLE", "ALTER ROLE"):
        assert forbidden not in source
    assert "scripts.frfinance_m40939_release_gate" in source
    with pytest.raises(CheckpointBlocked):
        local_git("merge","--ff-only","HEAD")
    doc=DOC.read_text(encoding="utf-8")
    yml=CI.read_text(encoding="utf-8")
    for key in ("M40600","M40840","NO-GO","Termux",
                "PIX_REAL=OFF","MIGRATIONS=NONE"):
        assert key in doc
    assert "test_m40941_termux_readonly_checkpoint_ci.py" in yml
    assert "contents: read" in yml


def test_valid_metadata_resolves_gate_without_external_pythonpath(monkeypatch):
    import importlib
    import sys

    mod=importlib.import_module(
        "scripts.frfinance_m40941_termux_post_sync_checkpoint_readonly"
    )
    backend_path=str(ROOT/"backend")
    monkeypatch.setattr(mod,"ROOT",ROOT)
    monkeypatch.setattr(mod,"native_termux",lambda *args:True)
    monkeypatch.setattr(
        sys,"path",[entry for entry in sys.path
                    if Path(entry or ".").resolve()!=Path(backend_path).resolve()]
    )
    # Force a fresh namespace import so cached CI modules cannot mask the
    # standalone script's missing-PYTHONPATH regression.
    monkeypatch.delitem(sys.modules,"scripts.frfinance_m40939_release_gate",raising=False)
    monkeypatch.delitem(sys.modules,"scripts",raising=False)
    observed,markers=mod.evaluate(
        env={},home=TERMUX,root=TERMUX/"fr-finance",
        expected_head=SHA,git_read=fixture_git()
    )
    assert observed==SHA
    assert backend_path in sys.path
    assert markers["M40941_PLAN"]=="VALIDATED_NO_GO"
    assert markers["M40941_PRODUCTION"]=="BLOCKED"
