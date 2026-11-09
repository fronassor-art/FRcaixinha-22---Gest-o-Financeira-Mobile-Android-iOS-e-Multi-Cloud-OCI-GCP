#!/usr/bin/env python3
"""M37370: local Termux PostgreSQL 18 catalog only; asks hidden DB password."""
from __future__ import annotations
import getpass
import os
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.local_pg18_evidence_readonly import (
    DBNAME,ROLE,PORT,LocalEvidenceBlocked,audit_local_catalog,format_local_evidence,
)
from aistudio_auth_baseline_readonly import inspect_local_auth_baseline

BRANCH="atualizacao-ai-studio-9b46a63187"
def check_repo():
    root=Path(__file__).resolve().parents[2]
    if root!=Path.home()/"fr-finance":
        raise LocalEvidenceBlocked("LOCAL_PROJECT_PATH_MISMATCH")
    try:
        def git(*args):
            return subprocess.check_output(
                ["git","-C",str(root),*args],text=True,stderr=subprocess.DEVNULL).strip()
        head=git("rev-parse","HEAD")
        remote=git("rev-parse","refs/remotes/origin/"+BRANCH)
        actual=git("branch","--show-current")
        changed=git("status","--porcelain","--untracked-files=no")
    except (OSError,subprocess.CalledProcessError):
        raise LocalEvidenceBlocked("LOCAL_REPOSITORY_UNAVAILABLE") from None
    if (actual!=BRANCH or head!=remote
            or len(head)!=40 or any(c not in "0123456789abcdef" for c in head)
            or changed):
        raise LocalEvidenceBlocked("LOCAL_REPOSITORY_NOT_SYNCED")

def main()->int:
    try:
        check_repo()
        import psycopg
        secret=getpass.getpass("Senha local frc_ai_owner (oculta): ")
        if not secret:
            raise LocalEvidenceBlocked("LOCAL_PASSWORD_MISSING")
        try:
            with psycopg.connect(
                host="127.0.0.1",port=PORT,dbname=DBNAME,
                user=ROLE,password=secret,connect_timeout=5,
                options="-c default_transaction_read_only=on -c statement_timeout=10000 -c lock_timeout=2000",
            ) as conn:
                del secret
                report=audit_local_catalog(conn,inspect_local_auth_baseline)
        except LocalEvidenceBlocked:
            raise
        except Exception:
            raise LocalEvidenceBlocked("LOCAL_PG18_READ_ONLY_CONNECTION_FAILED") from None
        for line in format_local_evidence(report):
            print(line)
        return 0
    except LocalEvidenceBlocked as exc:
        print("M37370_STATUS=BLOCKED")
        print("M37370_CAUSE="+str(exc))
        print("M37370_DB_WRITES=NONE")
        print("M37370_PIX_REAL=OFF")
        return 2
    except Exception:
        print("M37370_STATUS=BLOCKED")
        print("M37370_CAUSE=LOCAL_READ_ONLY_RUNTIME_FAILED")
        print("M37370_DB_WRITES=NONE")
        print("M37370_PIX_REAL=OFF")
        return 2

if __name__=="__main__":
    raise SystemExit(main())
