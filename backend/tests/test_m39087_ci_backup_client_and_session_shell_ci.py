"""FR Finance M39087: CI-only shell and guarded session-shell regression.

This file never calls Docker, PostgreSQL or a network. A simulated executable
ensures the wrapper refuses all non-disposable execution contexts.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def _backup_script() -> str:
    workflow = (ROOT / ".github/workflows/validacao-atualizacao.yml").read_text()
    start = workflow.index("      - name: Backup cifrado age e restauração descartável")
    stop = workflow.index("  postgres18-preflight:", start)
    section = workflow[start:stop]
    block = section.split("        run: |\n", 1)[1]
    # YAML block content is indented 10 spaces; heredoc terminator becomes
    # column 0 after YAML removes the shared indentation.
    for line in block.splitlines():
        if line.strip():
            assert line.startswith("          "), "M39087_BACKUP_YAML_INDENT_DRIFT"
    return "\n".join(
        line[10:] if line.strip() else ""
        for line in block.splitlines()
    ) + "\n"


def _wrapper() -> str:
    script = _backup_script()
    assert script.count("<<'PG16_WRAP'") == 1
    assert script.count("\nPG16_WRAP\n") == 1
    return script.split("<<'PG16_WRAP'\n", 1)[1].split("\nPG16_WRAP\n", 1)[0] + "\n"


def test_main_backup_step_bash_valid():
    script = _backup_script()
    subprocess.run(["bash", "-n"], input=script, text=True, check=True)
    assert "set -euo pipefail" in script
    assert "docker image inspect postgres:16" in script
    assert "docker run --rm -i --network host" in script
    assert "age-keygen" in script
    assert "backend/scripts/restore_disposable_ci.sh" in script
    assert 'test "$restored" = "$original"' in script
    assert "postgresql-client-16" not in script


def test_wrapper_fails_closed_for_non_ci_environment(tmp_path):
    wrapper = tmp_path / "pg_restore"
    wrapper.write_text(_wrapper())
    env = {
        **os.environ,
        "GITHUB_ACTIONS": "false",
        "PGHOST": "127.0.0.1",
        "PGPORT": "5432",
        "PGUSER": "postgres",
        "PGDATABASE": "frcaixinha_restore_ci",
    }
    result = subprocess.run(
        ["bash", str(wrapper), "--version"],
        env=env, capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 2
    assert "M39087_PG16_CLIENT_WRAPPER=BLOCKED_NONDISPOSABLE_CONTEXT" in result.stderr


def test_wrapper_rejects_unknown_db_even_in_ci(tmp_path):
    wrapper = tmp_path / "pg_dump"
    wrapper.write_text(_wrapper())
    env = {
        **os.environ,
        "GITHUB_ACTIONS": "true",
        "PGHOST": "127.0.0.1",
        "PGPORT": "5432",
        "PGUSER": "postgres",
        "PGDATABASE": "frcaixinha_aistudio_dev",
    }
    result = subprocess.run(
        ["bash", str(wrapper), "--version"],
        env=env, capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 2
    assert "BLOCKED_NONDISPOSABLE_CONTEXT" in result.stderr


def test_wrapper_forwards_stdin_only_to_pg16_in_simulated_ci(tmp_path):
    wrapper = tmp_path / "pg_restore"
    wrapper.write_text(_wrapper())
    fake_docker = tmp_path / "docker"
    fake_docker.write_text("#!/bin/sh\nprintf '%s\\n' \"$@\"\n")
    fake_docker.chmod(0o700)
    env = {
        **os.environ,
        "PATH": str(tmp_path) + os.pathsep + os.environ.get("PATH", ""),
        "GITHUB_ACTIONS": "true",
        "PGHOST": "127.0.0.1",
        "PGPORT": "5432",
        "PGUSER": "postgres",
        "PGDATABASE": "frcaixinha_restore_ci",
        "PGPASSWORD": "synthetic-ci-only",
    }
    result = subprocess.run(
        ["bash", str(wrapper), "--version"],
        env=env, capture_output=True, text=True, timeout=5
    )
    assert result.returncode == 0, result.stderr
    args = result.stdout.splitlines()
    assert args[:4] == ["run", "--rm", "-i", "--network"]
    assert "host" in args
    assert "postgres:16" in args
    assert "pg_restore" in args
    assert "--version" in args


def test_android_test_keeps_session_safety_invariant():
    test = (ROOT / "src/tests/android_safe_area_ci.test.ts").read_text()
    app = (ROOT / "src/App.tsx").read_text()
    assert "M39087: M39075 preserves the mounted shell" in test
    assert "aria-hidden={resumeValidationPending} inert={resumeValidationPending}" in app
    assert "resumeValidationPending ? ' invisible pointer-events-none select-none' : ''" in app
    assert "className={'fr-app-shell " in app
