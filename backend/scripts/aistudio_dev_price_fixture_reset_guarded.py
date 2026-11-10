#!/usr/bin/env python3
"""M37439: gated synthetic price-fixture cleanup on the ORIGINAL local PG18.

Default is preflight only. CI may only statically test this file.
"""
from __future__ import annotations
import getpass
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT=Path.home()/"fr-finance"
BRANCH="atualizacao-ai-studio-9b46a63187"
DB="frcaixinha_aistudio_dev"
ROLE="frc_ai_owner"
PORT=5433
CLUSTER="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
BACKUP=Path.home()/".local/share/fr-finance/dev-backups/before_clean_dev_20261110T012710Z_4901.dump.age"
BACKUP_SHA256="714bc50de8dfc42d25f1b9bbe54e9841df883f0d606f467015c0e153b4d9b88b"
CANDIDATE=ROOT/"backend/scripts/aistudio_dev_price_fixture_reset_candidate.sql"
BASELINE=(1,1,12,1,0,0,0,0,0,1,1,2,3,1,1,0,2,2)
AFTER=(0,0,0,0,0,1,1,2,4,2)

BASELINE_SQL="""
SELECT
 (SELECT count(*) FROM public.policies WHERE contribution_per_quota<150),
 (SELECT count(*) FROM public.quotas WHERE value_brl<150),
 (SELECT count(*) FROM public.contributions WHERE amount_due<150),
 (SELECT count(*) FROM public.cycle_contribution_price_audit WHERE old_price_cents<15000 OR requested_price_cents<15000),
 (SELECT count(*) FROM public.contributions WHERE amount_paid>0 OR paid_at IS NOT NULL OR payment_status='QUITADA'),
 (SELECT count(*) FROM public.pix_payment_intents),
 (SELECT count(*) FROM public.ledger_transactions),
 (SELECT count(*) FROM public.ledger_entries),
 (SELECT count(*) FROM public.loans),
 (SELECT count(*) FROM public.users),
 (SELECT count(*) FROM public.tenants),
 (SELECT count(*) FROM public.memberships),
 (SELECT count(*) FROM public.audit_events),
 (SELECT count(*) FROM public.cycle_contribution_price_audit WHERE change_status='PENDING_REVIEW'),
 (SELECT count(*) FROM public.cycles WHERE year=2027 AND status='ABERTO'),
 (SELECT count(*) FROM public.cycle_opening_audit),
 (SELECT count(*) FROM pg_catalog.pg_trigger WHERE tgrelid='public.cycle_contribution_price_audit'::regclass AND tgenabled='O' AND tgname IN ('cycle_price_immutable_row','cycle_price_immutable_truncate')),
 (SELECT count(*) FROM pg_catalog.pg_constraint WHERE conname IN ('policy_minimum_150_new','quota_minimum_150_new'))
"""
GENERAL_AUDIT_SQL="""
SELECT count(*) FROM public.audit_events a
WHERE a.tenant_id IN (SELECT tenant_id FROM public.policies WHERE contribution_per_quota<150)
 AND (
 strpos(coalesce(a.reason,''),'100')>0
 OR strpos(coalesce(a.evidence_ref,''),'100')>0
 OR a.object_id IN (SELECT cycle_id::text FROM public.policies WHERE contribution_per_quota<150)
 OR a.object_id IN (SELECT id::text FROM public.policies WHERE contribution_per_quota<150)
 OR a.object_id IN (SELECT id::text FROM public.contributions WHERE amount_due<150)
)
"""
AFTER_SQL="""
SELECT
 (SELECT count(*) FROM public.cycles),
 (SELECT count(*) FROM public.policies),
 (SELECT count(*) FROM public.quotas),
 (SELECT count(*) FROM public.contributions),
 (SELECT count(*) FROM public.cycle_contribution_price_audit),
 (SELECT count(*) FROM public.users),
 (SELECT count(*) FROM public.tenants),
 (SELECT count(*) FROM public.memberships),
 (SELECT count(*) FROM public.audit_events),
 (SELECT count(*) FROM pg_catalog.pg_trigger WHERE tgrelid='public.cycle_contribution_price_audit'::regclass AND tgenabled='O' AND tgname IN ('cycle_price_immutable_row','cycle_price_immutable_truncate'))
"""
class Blocked(Exception):
    pass

def require(condition,reason):
    if not condition:
        raise Blocked(reason)

def command(argv):
    return subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()

def verify_project(mode):
    require(os.getenv("ENVIRONMENT")!="production","PRODUCTION_DENIED")
    require(os.getenv("GITHUB_ACTIONS")!="true","TERMUX_ONLY")
    require(os.getenv("FR_FINANCE_PIX_REAL")!="ON","PIX_REAL_ENABLED")
    require(os.getenv("FR_FINANCE_REAL_USER_ACTIVATION")!="ON","REAL_USERS_ENABLED")
    require(ROOT.is_dir() and (Path(CLUSTER)/"PG_VERSION").is_file()
      and (Path(CLUSTER)/"PG_VERSION").read_text().strip()=="18","LOCAL_PG18_CLUSTER_REQUIRED")
    require(command(["git","branch","--show-current"])==BRANCH,"WRONG_GIT_BRANCH")
    require(not command(["git","status","--porcelain"]),"GIT_WORKTREE_DIRTY")
    require(CANDIDATE.is_file() and not CANDIDATE.is_symlink(),"CANDIDATE_MISSING")
    command(["git","ls-files","--error-unmatch",str(CANDIDATE.relative_to(ROOT))])
    if mode=="apply":
        require(os.getenv("FR_FINANCE_M37439_ENABLE_APPLY")=="YES","APPLY_NOT_ENABLED")
        approved=os.getenv("FR_FINANCE_APPROVED_SHA","")
        require(len(approved)==40 and all(c in "0123456789abcdef" for c in approved)
                and command(["git","rev-parse","HEAD"])==approved,
                "APPROVED_GIT_SHA_MISMATCH")

def verify_backup():
    require(BACKUP.is_file() and not BACKUP.is_symlink(),"SEALED_BACKUP_MISSING")
    digest=hashlib.sha256()
    with BACKUP.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            digest.update(block)
    require(digest.hexdigest()==BACKUP_SHA256,"ENCRYPTED_BACKUP_SHA_MISMATCH")

def db_connection(password):
    import psycopg
    conn=psycopg.connect(host="127.0.0.1",port=PORT,dbname=DB,
      user=ROLE,password=password,connect_timeout=5,
      options="-c default_transaction_read_only=on -c statement_timeout=15000 -c lock_timeout=3000")
    return conn

def inventory(password):
    with db_connection(password) as conn:
        identity=conn.execute("""
        SELECT current_database(),session_user,current_user,inet_server_port(),
          current_setting('data_directory'),current_setting('server_version_num')::int,
          current_setting('transaction_read_only')
        """).fetchone()
        require(identity is not None and identity[:5]==(DB,ROLE,ROLE,PORT,CLUSTER)
          and 180000<=identity[5]<190000 and identity[6]=="on",
          "ORIGINAL_POSTGRESQL_IDENTITY_MISMATCH")
        counts=conn.execute(BASELINE_SQL).fetchone()
        require(counts==BASELINE,"SYNTHETIC_BASELINE_CHANGED")
        linked=conn.execute(GENERAL_AUDIT_SQL).fetchone()
        require(linked is not None and type(linked[0]) is int
                and 0<=linked[0]<=100000000,"AUDIT_LINK_RESULT_INVALID")
        busy=conn.execute("""
        SELECT count(*) FROM pg_stat_activity
        WHERE datname='frcaixinha_aistudio_dev'
        AND pid<>pg_backend_pid() AND backend_type='client backend'
        """).fetchone()
        return linked[0],busy[0]

def verify_backup_decryption():
    # Stream age directly into pg_restore TOC; no plaintext backup is written.
    age=subprocess.Popen(["age","--decrypt",str(BACKUP)],stdout=subprocess.PIPE)
    try:
        toc=subprocess.run(["pg_restore","--list"],stdin=age.stdout,
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    finally:
        if age.stdout is not None:
            age.stdout.close()
    status=age.wait()
    require(status==0 and toc.returncode==0,"BACKUP_DECRYPT_OR_CATALOG_FAILED")

def stop_api_check():
    try:
        with socket.create_connection(("127.0.0.1",8000),timeout=1):
            pass
    except OSError:
        return
    raise Blocked("FASTAPI_ACTIVE_STOP_BEFORE_APPLY")

def confirm(label):
    # Explicit owner consent was already given; typed confirmations prevent accidental run.
    value=input("Digite "+label+": ").strip()
    require(value==label,"INTERACTIVE_CONFIRMATION_DENIED")

def apply_candidate(password):
    env=os.environ.copy()
    env["PGPASSWORD"]=password
    env["PGOPTIONS"]=(
      "-c frfinance.dev_cleanup_m37437=EXPLICIT_DEV_ONLY_PURGE_APPROVED "
      "-c frfinance.m37437_verified_backup_sha="+BACKUP_SHA256
    )
    result=subprocess.run([
      "psql","-X","-w","-q","-v","ON_ERROR_STOP=1","-h","127.0.0.1",
      "-p",str(PORT),"-U",ROLE,"-d",DB,"-f",str(CANDIDATE),
    ],env=env,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
    require(result.returncode==0,"SQL_TRANSACTION_FAILED_ROLLED_BACK")
    with db_connection(password) as conn:
        after=conn.execute(AFTER_SQL).fetchone()
    require(after==AFTER,"POSTCOMMIT_VERIFICATION_MISMATCH_REVIEW_REQUIRED")

def main():
    mode=sys.argv[1] if len(sys.argv)==2 else "preflight"
    try:
        require(mode in ("preflight","apply") and len(sys.argv)<=2,"MODE_INVALID")
        verify_project(mode)
        verify_backup()
        password=getpass.getpass("Senha PostgreSQL local (oculta): ")
        require(bool(password),"DB_PASSWORD_EMPTY")
        linked,busy=inventory(password)
        print("=== FR FINANCE M37439 — ORIGINAL PG18 ===")
        print("M37439_ORIGINAL_DATABASE=VERIFIED")
        print("M37439_ENCRYPTED_BACKUP_SHA256=PASS")
        print("M37439_LEGACY_FIXTURES=1_POLICY_1_QUOTA_12_UNPAID_1_PRICE_AUDIT")
        print("M37439_RECORDED_FINANCIAL_OPERATIONS=NONE")
        print("M37439_GENERAL_AUDIT_LINKS="+str(linked))
        if mode=="preflight":
            print("M37439_PREFLIGHT=READ_ONLY_PASS")
            print("M37439_MIGRATION=NOT_EXECUTED")
            print("M37439_DB_WRITES=NO")
            print("M37439_NEW_DATABASE=NO")
            return 0
        require(linked==0,"GENERAL_AUDIT_REFS_REQUIRE_MANUAL_REVIEW")
        require(busy==0,"OTHER_DATABASE_CLIENTS_STILL_CONNECTED")
        stop_api_check()
        print("A limpeza atingira apenas os dados sinteticos de 2027.")
        print("A auditoria de preco experimental sera removida em excecao; backup preservado.")
        confirm("AUTORIZO_LIMPEZA_SINTETICA_2027")
        confirm("AUTORIZO_EXCECAO_AUDITORIA_DEV")
        verify_backup_decryption()
        print("M37439_BACKUP_DECRYPTION=PASS")
        # Recheck all current state immediately before the single SQL transaction.
        linked,busy=inventory(password)
        require(linked==0 and busy==0,"STATE_CHANGED_ABORT_APPLY")
        stop_api_check()
        print("M37439_TRANSACTION=EXECUTING")
        apply_candidate(password)
        print("M37439_TRANSACTION=COMMITTED_AND_VERIFIED")
        print("M37439_REMOVED=12_CONTRIBUTIONS_1_QUOTA_1_PRICE_AUDIT_1_POLICY_1_CYCLE")
        print("M37439_IDENTITIES=KEPT")
        print("M37439_GENERAL_AUDIT=PREVIOUS_3_PLUS_1_RESET_EVIDENCE")
        print("M37439_IMMUTABLE_AUDIT_TRIGGERS=RESTORED")
        print("M37439_NEW_DATABASE=NO")
        print("M37439_PIX_REAL=OFF")
        print("M37439_REAL_ACTIVATION=OFF")
        print("M37439_STATUS=DEV_RESET_PASS")
        return 0
    except Blocked as e:
        print("M37439_STATUS=BLOCKED")
        print("M37439_REASON="+str(e))
        return 2
    except (KeyboardInterrupt,EOFError):
        print("M37439_STATUS=CANCELLED")
        return 2
    except Exception:
        print("M37439_STATUS=BLOCKED")
        print("M37439_REASON=ENVIRONMENT_OR_DB_CHECK_FAILED")
        return 2

if __name__=="__main__":
    raise SystemExit(main())
