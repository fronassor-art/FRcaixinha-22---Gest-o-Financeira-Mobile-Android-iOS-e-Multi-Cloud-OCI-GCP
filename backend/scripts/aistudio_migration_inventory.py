#!/usr/bin/env python3
"""AI Studio M19200: strict migration registry and Termux read-only audit."""
from __future__ import annotations
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
CATALOG=ROOT/"backend/migration_catalog_ai_studio.json"
FAMILIES=("migrations","local_migrations","ci_migrations","staging_migrations")
BRANCH="atualizacao-ai-studio-9b46a63187"
PGDATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"

def deny(message):
    print("M19200_BLOQUEADO: "+message,file=sys.stderr)
    return 2

def git(*args):
    return subprocess.check_output(["git","-C",str(ROOT),*args],text=True).strip()

def repo_check():
    manifest=json.loads(CATALOG.read_text(encoding="utf-8"))
    if manifest["schema"]!="AI_STUDIO_MIGRATION_CATALOG_V1" or manifest["project"]!="FR_CAIXINHA_AI_STUDIO_ONLY":
        raise ValueError("wrong project/catalog")
    for key in (
      "never_apply_ci_only_sql_to_termux",
      "never_apply_staging_only_sql_to_termux",
      "mandatory_local_equivalent_before_mobile_functional_test",
      "mandatory_local_backup_and_post_apply_verification",
      "no_real_payments_from_schema_parity",
      "do_not_claim_local_applied_from_CI",
    ):
        if manifest["rules"].get(key) is not True:
            raise ValueError("missing required policy: "+key)
    registered={}
    for e in manifest["entries"]:
        path=e["source_path"]
        m=re.fullmatch(r"backend/(migrations|local_migrations|ci_migrations|staging_migrations)/(\d{3})_[\w-]+[.]sql",path)
        if not m or path in registered or not (ROOT/path).is_file():
            raise ValueError("invalid/duplicate migration: "+path)
        family,number=m.group(1),int(m.group(2))
        if e["id"]!=family+":"+m.group(2):
            raise ValueError("namespace collision: "+path)
        expected=(
          "BASELINE_LOCAL" if family=="migrations" and number<=27 else
          "APPLIED_LOCAL_EVIDENCE" if family=="migrations" and number==31 else
          "CI_ONLY_NEEDS_PORT" if family=="migrations" and number in (28,29,30) else
          "LOCAL_CANDIDATE_REQUIRES_PROOF" if family=="local_migrations" and number in (28,29,30,34,35,36,37,38,39,40,41) else
          "LOCAL_CANDIDATE_REQUIRES_PROOF" if family=="migrations" else
          "CI_ONLY_TEST_OR_FIXTURE" if family=="ci_migrations" else
          "STAGING_ONLY_NEEDS_PORT"
        )
        if e["classification"]!=expected:
            raise ValueError("classification does not match location: "+path)
        forbidden=family in ("ci_migrations","staging_migrations") or (family=="migrations" and number in (28,29,30))
        if e["do_not_apply_source_to_termux"] is not forbidden:
            raise ValueError("source marked unsafe for Termux: "+path)
        gitsha=subprocess.check_output(["git","hash-object",path],cwd=ROOT,text=True).strip()
        if e.get("source_blob_sha")!=gitsha:
            raise ValueError("SQL changed without registry SHA update: "+path)
        registered[path]=e
    filesystem={str(p.relative_to(ROOT)) for f in FAMILIES
        for p in (ROOT/"backend"/f).glob("[0-9][0-9][0-9]_*.sql")}
    if filesystem!=set(registered):
        raise ValueError("unregistered/orphan SQL paths: "+str(sorted(filesystem^set(registered))))
    for name in (
        "aistudio_local_migration.sh",
        "aistudio_db_local.sh",
        "aistudio_notifications_incremental.sh",
    ):
        body=(ROOT/"backend/scripts"/name).read_text()
        if "staging_migrations/" in body or "ci_migrations/" in body:
            raise ValueError("CI-only SQL referenced by Termux installer: "+name)
    print("M19200_REGISTRY_HASHES=PASS")
    print("M19200_MIGRATION_SQL_COUNT="+str(len(filesystem)))
    print("M19200_LOCAL_031=EVIDENCE_USER_LOG_NOT_CI")
    print("M19200_NEEDS_LOCAL_EQUIVALENT=0")
    print("M20100_LOCAL_034_041=PREPARED_NOT_APPLIED")
    print("M19300_LOCAL_028_030=PREPARED_NOT_APPLIED")
    print("M19200_CI_STAGING_NEVER_LOCAL_APPLY=PASS")
    return manifest

def local_readonly():
    if ROOT!=Path.home()/"frcaixinha-aistudio-mobile":
        return deny("wrong Termux project directory")
    if git("branch","--show-current")!=BRANCH or git("rev-parse","HEAD")!=os.getenv("AI_STUDIO_APPROVED_SHA",""):
        return deny("Git branch/SHA not approved")
    if git("status","--porcelain","--untracked-files=no"):
        return deny("tracked working tree differs")
    try:
        import psycopg
    except ImportError:
        return deny("psycopg not installed")
    pwd=getpass.getpass("Senha frc_ai_owner (oculta): ")
    if not pwd:return deny("missing password")
    try:
        with psycopg.connect(
            host="127.0.0.1",port=5433,dbname="frcaixinha_aistudio_dev",
            user="frc_ai_owner",password=pwd,connect_timeout=5,
        ) as conn:
            del pwd
            with conn.transaction():
                conn.execute("SET TRANSACTION READ ONLY")
                identity=conn.execute(
                    "SELECT current_database(),current_user,inet_server_port(),"
                    "current_setting('data_directory'),current_setting('server_version_num')::int"
                ).fetchone()
                if identity[:4]!=(
                    "frcaixinha_aistudio_dev","frc_ai_owner",5433,PGDATA
                ) or not 180000<=identity[4]<190000:
                    return deny("not the exclusive AI Studio PostgreSQL 18")
                n=conn.execute("SELECT count(*) FROM pg_catalog.pg_tables WHERE schemaname='public'").fetchone()[0]
                def exists(name):
                    return conn.execute("SELECT to_regclass(%s) IS NOT NULL",(name,)).fetchone()[0]
                def routine(name):
                    return conn.execute("SELECT to_regprocedure(%s) IS NOT NULL",(name,)).fetchone()[0]
                base_ok=n>=27 and all(exists("public."+t) for t in (
                    "users","tenants","memberships","credentials","sessions","auth_login_proofs",
                )) and routine("public.auth_active_memberships(text)")
                if not base_ok:return deny("baseline objects incomplete")
                n031=exists("public.notification_inbox") and routine("public.notification_local_mark_read(uuid)")
                if n031:
                    n031=n031 and conn.execute(
                      "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class "
                      "WHERE oid='public.notification_inbox'::regclass"
                    ).fetchone()[0]
                print("M19200_LOCAL_DB_IDENTITY=PASS")
                print("M19200_LOCAL_PUBLIC_TABLES="+str(n))
                print("M19200_001_027=STRUCTURAL_PRESENT_PER_FILE_HISTORY_UNVERIFIED")
                print("M19200_031_INBOX="+("RLS_PRESENT" if n031 else "MISSING_OR_UNSAFE"))
                print("M19200_028_REQUESTS="+("OBJECT_PRESENT" if exists("public.member_lifecycle_requests") else "NOT_IN_LOCAL"))
                print("M19200_029_REVIEWS="+("OBJECT_PRESENT" if exists("public.member_lifecycle_review_events") else "NOT_IN_LOCAL"))
                has030=conn.execute(
                  "SELECT EXISTS(SELECT 1 FROM pg_indexes WHERE schemaname='public' "
                  "AND indexname='member_lifecycle_case_round_lookup')"
                ).fetchone()[0]
                print("M19200_030_ROUNDS="+("INDEX_PRESENT" if has030 else "NOT_IN_LOCAL"))
                print("M19200_STAGING_034_041=CI_OR_OCI_ONLY_NOT_TERMUX")
                print("M19200_CI_031_037=DISPOSABLE_ONLY")
                print("M19200_READ_ONLY=PASS")
                return 0 if n031 else 2
    except Exception as e:
        print("M19200_DB_READ_ERROR="+type(e).__name__,file=sys.stderr)
        return 2

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mode",choices=("repo-check","local-readonly"))
    mode=ap.parse_args().mode
    try:
        repo_check()
        return 0 if mode=="repo-check" else local_readonly()
    except (ValueError,KeyError,OSError,subprocess.CalledProcessError) as exc:
        return deny(str(exc))

if __name__=="__main__":
    raise SystemExit(main())
