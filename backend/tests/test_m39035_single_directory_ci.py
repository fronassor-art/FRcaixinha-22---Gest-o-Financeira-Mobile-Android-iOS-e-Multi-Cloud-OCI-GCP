"""FR Finance M39035 — regression proof of the SINGLE Termux checkout.

Tests inspect instructions and source; do not clone, migrate, delete or connect.
"""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
SCRIPTS=ROOT/"backend"/"scripts"
CANONICAL="/data/data/com.termux/files/home/fr-finance"


def test_sql_auditors_never_assume_debian_root_is_a_checkout():
    script=(SCRIPTS/"frfinance_m39026_credit_only_preflight.py").read_text()
    assert f'PROJECT = Path("{CANONICAL}")' in script
    assert 'Path.home() / "fr-finance"' not in script
    assert "TERMUX_CANONICAL_REPOSITORY_NOT_FOUND_DO_NOT_CLONE" in script
    for src in ("frfinance_m39032_post_migration_readonly.py",
                "frfinance_m39034_rls_api_offline.py"):
        assert "verify_repo()" in (SCRIPTS/src).read_text()


def test_old_sql_installers_never_reapply_in_original_pg18():
    pre=(SCRIPTS/"frfinance_m39020_termux_preflight.sh").read_text()
    apply=(SCRIPTS/"frfinance_m39020_termux_apply_guarded.sh").read_text()
    assert "PRE_MIGRATION_PREFLIGHT_OBSOLETE_USE_M39032_POST_MIGRATION" in pre
    assert "LEGACY_INSTALLER_DISABLED_SQL110_111_ALREADY_APPLIED_DO_NOT_REPEAT" in apply
    assert CANONICAL in pre and CANONICAL in apply
    assert 'cd "$HOME/fr-finance"' not in apply


def test_native_reconciliation_only_fast_forward_and_no_destroy():
    script=(SCRIPTS/"frfinance_m39035_single_directory_termux.sh").read_text()
    assert 'MODE="${1:-audit}"' in script
    assert '[[ "${HOME:-}" == "/data/data/com.termux/files/home" ]]' in script
    assert 'git -C "$ROOT" fetch --no-tags origin "$BRANCH"' in script
    assert 'git -C "$ROOT" merge-base --is-ancestor HEAD FETCH_HEAD' in script
    assert 'git -C "$ROOT" merge --ff-only FETCH_HEAD' in script
    assert 'status --porcelain --untracked-files=all' in script
    assert 'FR_FINANCE_APPROVED_SHA' in script
    assert 'M39035_DATABASE_MIGRATIONS=NONE' in script
    for forbidden in ("git clone", "git reset", "git clean", "git stash push",
                      "rm -rf", "psql -f", "pg_dump", "createdb"):
        assert forbidden not in script
    subprocess.run(["bash","-n",str(SCRIPTS/"frfinance_m39035_single_directory_termux.sh")],
                   check=True,capture_output=True,text=True)


def test_debian_duplicate_audit_is_read_only_and_does_not_remove():
    script=(SCRIPTS/"frfinance_m39036_debian_clone_audit_only.sh").read_text()
    assert f'CANON="{CANONICAL}"' in script
    assert 'EXTRA="/root/fr-finance"' in script
    assert 'stat -Lc' in script
    assert 'ls-files --others --ignored --exclude-standard' in script
    assert 'stash list' in script
    assert 'rev-list --count --all --not --remotes' in script
    assert 'M39036_FILES_DELETED=NONE' in script
    for forbidden in ("rm -rf", "git clone", "git fetch", "git merge",
                      "git reset", "git clean", "dropdb", "pg_dump"):
        assert forbidden not in script
    subprocess.run(["bash","-n",str(SCRIPTS/"frfinance_m39036_debian_clone_audit_only.sh")],
                   check=True,capture_output=True,text=True)


def test_reconciliation_document_preserves_postgres_and_backups():
    doc=(ROOT/"docs"/"FR_FINANCE_M39035_DIRETORIO_UNICO_RECUPERACAO.md").read_text()
    for phrase in (CANONICAL, "frcaixinha_aistudio_dev", "5433",
                   "SQL 110/111 JÁ EXECUTADAS", "frfinance-backups",
                   "/root/fr-finance", "M39034", "M39031"):
        assert phrase in doc



def test_duplicate_delete_requires_exact_head_clean_backup_and_interactive_approval():
    src=(SCRIPTS/"frfinance_m39037_delete_verified_duplicate_debian.sh").read_text()
    assert f'CANON="{CANONICAL}"' in src
    assert 'EXTRA="/root/fr-finance"' in src
    assert "M39037_SECONDARY_CLONE_DELETED=PASS" in src
    assert '[[ -t 0 ]]' in src
    assert 'FR_FINANCE_APPROVED_SHA' in src
    assert 'status --porcelain --untracked-files=all' in src
    assert 'ls-files --others --ignored --exclude-standard' in src
    assert 'rev-list --count --all --not --remotes' in src
    assert 'stash list' in src
    assert 'sha256sum --check --status' in src
    assert 'stat -Lc' in src
    assert 'realpath -e' in src
    assert 'EXCLUIR_SOMENTE_CLONE_DEBIAN' in src
    assert 'rm --one-file-system -rf -- /root/fr-finance' in src
    assert 'rm --one-file-system -rf -- "$CANON"' not in src
    assert 'rm -rf "$HOME/fr-finance"' not in src
    assert "pg_dump" not in src
    assert "dropdb" not in src
    assert "git reset" not in src
    subprocess.run(["bash","-n",str(SCRIPTS/"frfinance_m39037_delete_verified_duplicate_debian.sh")],
                   check=True,capture_output=True,text=True)



def test_old_backup_cannot_assume_the_pre_migration_47_table_schema():
    src=(SCRIPTS/"frfinance_m39030_pg18_backup_restore_only.sh").read_text()
    assert 'LEGACY_PRE_MIGRATION_BACKUP_OBSOLETE_USE_VERIFIED_POST_MIGRATION_BACKUP' in src
    assert f'ROOT="{CANONICAL}"' in src
    assert "pg_dump" in src  # archival, but installer exits before calling it
    subprocess.run(["bash","-n",str(SCRIPTS/"frfinance_m39030_pg18_backup_restore_only.sh")],
                   check=True,capture_output=True,text=True)
