"""FR Finance M39086 — keep general CI safety gates during drift rebaseline.

Static checks only: no DB connections, no migrations and no API calls.
The encrypted backup restore itself must still run in the disposable CI DB.
"""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[2]


def test_menu_expectation_is_scoped_not_globally_enabled():
    test = (ROOT / "src/tests/role_scope_ui.test.ts").read_text()
    scope = (ROOT / "src/services/roleScope.ts").read_text()
    assert "'MINHAS_OPORTUNIDADES','MEU_RESULTADO'" in test
    assert "isRoleTabAllowed('MASTER','MINHAS_OPORTUNIDADES'),false" in test
    assert "isRoleTabAllowed('TENANT_ADMIN','MINHAS_OPORTUNIDADES'),false" in test
    assert "isRoleTabAllowed('TENANT_MEMBER','CAMPANHAS_MEMBROS'),false" in test
    assert "isRoleTabAllowed('MASTER','CAMPANHAS_MEMBROS'),false" in test
    assert "'MINHAS_OPORTUNIDADES'" in scope
    assert "'CAMPANHAS_MEMBROS'" in scope


def test_candidates_112_113_count_and_no_local_apply_authority():
    records = json.loads((ROOT / "backend/migration_catalog_ai_studio.json").read_text())["entries"]
    candidates = [r for r in records if r["classification"] == "LOCAL_CANDIDATE_REQUIRES_PROOF"]
    assert len(candidates) == 22
    for entry_id in ("migrations:112", "migrations:113"):
        matching = [r for r in candidates if r["id"] == entry_id]
        assert len(matching) == 1
        assert matching[0]["local_evidence"] is None
    inventory = (ROOT / "backend/tests/test_m19200_migration_inventory_ci.py").read_text()
    assert 'assert c("LOCAL_CANDIDATE_REQUIRES_PROOF")==22' in inventory


def test_pg16_restore_keeps_crypto_integrity_and_strict_error_exit():
    workflow = (ROOT / ".github/workflows/validacao-atualizacao.yml").read_text()
    start = workflow.index("      - name: Backup cifrado age e restauração descartável")
    end = workflow.index("  postgres18-preflight:", start)
    backup = workflow[start:end]
    for required in (
        "docker image inspect postgres:16",
        "docker run --rm -i --network host",
        "postgres:16 \"$command_name\" \"$@\"", 
        "-e PGHOST -e PGPORT -e PGUSER -e PGPASSWORD -e PGDATABASE",
        'export PATH="$RUNNER_TEMP/frfinance-pg16-bin:$PATH"',
        "GITHUB_ACTIONS:-",
        "PGHOST:-",
        "PGPORT:-",
        "PGUSER:-",
        "PGDATABASE:-",
        "frcaixinha_restore_ci",
        "M39087_PG16_CLIENT_WRAPPER=BLOCKED_NONDISPOSABLE_CONTEXT",
        "SHOW server_version_num",
        "age-keygen",
        "backend/scripts/backup_age.sh",
        "backend/scripts/restore_disposable_ci.sh",
        'test "$restored" = "$original"',
    ):
        assert required in backup, required
    assert "postgresql-client-16" not in backup
    assert backup.count("pg_dump --version") == 1
    assert backup.count("pg_restore --version") == 1
    assert 'image: postgres:16' in workflow
    assert 'image: postgres:18' in workflow
    assert "pg_restore --exit-on-error" in (ROOT / "backend/scripts/restore_disposable_ci.sh").read_text()
    assert "pg_dump --format=custom" in (ROOT / "backend/scripts/backup_age.sh").read_text()
    for forbidden in ("--ignore-errors", "|| true", "pg_restore --clean --if-exists"):
        assert forbidden not in backup
