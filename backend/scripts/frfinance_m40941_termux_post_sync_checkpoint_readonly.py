#!/usr/bin/env python3
"""M40941 native-Termux POST source-sync read-only checkpoint.

This is not a sync, migration, deployment, FastAPI restart or production
authorization. Call only after M40600 fast-forward source-only has succeeded.
No Postgres, network, environment secret, provider or process actions.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
TERMUX=Path("/data/data/com.termux/files/home")
BRANCH="atualizacao-ai-studio-9b46a63187"
REPO="fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP"
ORIGINS={
    "https://github.com/"+REPO,
    "https://github.com/"+REPO+".git",
    "git@github.com:"+REPO,
    "git@github.com:"+REPO+".git",
}
HEX40=re.compile(r"[a-f0-9]{40}\Z")


class CheckpointBlocked(ValueError):
    pass


def native_termux(env: dict[str,str], home: Path, root: Path) -> bool:
    return (
        env.get("PREFIX")=="/data/data/com.termux/files/usr"
        and env.get("HOME")==str(TERMUX)
        and home==TERMUX
        and root==TERMUX/"fr-finance"
        and not root.is_symlink()
        and not (root/".git").is_symlink()
        and (root/".git").exists()
    )


def local_git(*args: str) -> str:
    # All Git operations are READ ONLY. No remote, checkout, merge or hooks.
    if not args or args[0] not in {
        "rev-parse", "branch", "remote", "status",
    }:
        raise CheckpointBlocked("M40941_GIT_MUTATION_DISALLOWED")
    r=subprocess.run(["git",*args],cwd=ROOT,capture_output=True,
                     text=True,timeout=15,check=False)
    if r.returncode!=0:
        raise CheckpointBlocked("M40941_GIT_READ_FAILED")
    return r.stdout.strip()


def evaluate(*, env: dict[str,str], home: Path, root: Path,
             expected_head: str, git_read=local_git) -> tuple[str,dict]:
    if not HEX40.fullmatch(expected_head):
        raise CheckpointBlocked("M40941_INVALID_PINNED_SHA")
    if not native_termux(env,home,root):
        raise CheckpointBlocked("M40941_NOT_NATIVE_FR_FINANCE_TERMUX")
    if git_read("rev-parse","--show-toplevel")!=str(root):
        raise CheckpointBlocked("M40941_WRONG_CHECKOUT")
    if git_read("branch","--show-current")!=BRANCH:
        raise CheckpointBlocked("M40941_WRONG_BRANCH")
    if git_read("remote","get-url","origin") not in ORIGINS:
        raise CheckpointBlocked("M40941_WRONG_REPOSITORY")
    observed=git_read("rev-parse","HEAD")
    if observed!=expected_head:
        raise CheckpointBlocked("M40941_SHA_DIFFERS_FROM_APPROVED_SOURCE")
    if git_read("status","--porcelain","--untracked-files=no"):
        raise CheckpointBlocked("M40941_DIRTY_TRACKED_FILES")

    # Make this standalone Termux script independent of caller PYTHONPATH.
    # No package installation or filesystem write is performed.
    backend_path=str(ROOT/"backend")
    if backend_path not in sys.path:
        sys.path.insert(0,backend_path)
    # Source-only inventory. This validates dependencies and enforces NO-GO;
    # it never approves SQL, provider money, migrations or runtime reload.
    from scripts.frfinance_m40939_release_gate import MANIFEST, validate
    import json
    summary=validate(json.loads(MANIFEST.read_text(encoding="utf-8")))
    if summary["M40939_DECISION"]!="NO_GO":
        raise CheckpointBlocked("M40941_INVALID_NO_GO_GUARD")
    return observed,{
        "M40941_TERMUX":"NATIVE_FR_FINANCE",
        "M40941_BRANCH":"PINNED",
        "M40941_REMOTE":"EXPECTED_REPOSITORY",
        "M40941_TRACKED_WORKTREE":"CLEAN",
        "M40941_SOURCE":"PINNED_HEAD_VERIFIED",
        "M40941_PLAN":"VALIDATED_NO_GO",
        "M40941_RUNTIME":"NOT_RELOADED_OR_ATTESTED",
        "M40941_DB_CONNECTIONS":"NONE",
        "M40941_DB_WRITES":"NONE",
        "M40941_MIGRATIONS":"NONE",
        "M40941_SERVICE_RESTARTS":"NONE",
        "M40941_PIX_REAL":"OFF",
        "M40941_PAGAMENTOS_REAIS":"OFF",
        "M40941_ATIVACAO_REAL":"OFF",
        "M40941_PRODUCTION":"BLOCKED",
    }


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(description="FR Finance M40941 read-only after source sync")
    parser.add_argument("--expected-head",required=True)
    args=parser.parse_args(argv)
    try:
        observed,markers=evaluate(
            env=dict(os.environ),home=Path.home(),root=ROOT,
            expected_head=args.expected_head,
        )
        print("M40941_HEAD="+observed[:12])
        for key,value in markers.items():
            print(key+"="+value)
        print("M40941_STATUS=PASS_SOURCE_ONLY_NO_GO")
        return 0
    except (CheckpointBlocked,OSError,ValueError,KeyError,ImportError,
            subprocess.TimeoutExpired) as exc:
        print("M40941_STATUS=BLOCKED_"+(
            str(exc) if isinstance(exc,CheckpointBlocked)
            else type(exc).__name__
        ))
        return 2
    finally:
        print("M40941_NO_DATABASE_OR_MIGRATION_ACTIONS=CONFIRMED_BY_DESIGN")


if __name__=="__main__":
    raise SystemExit(main())
