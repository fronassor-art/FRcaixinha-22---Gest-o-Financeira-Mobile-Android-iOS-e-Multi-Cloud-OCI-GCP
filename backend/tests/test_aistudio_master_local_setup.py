"""Guarda do setup MASTER no projeto AI Studio. Testes sem conexao ao PostgreSQL local."""
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "backend" / "scripts"


def test_migration_script_is_valid_shell_and_has_explicit_write_gate():
    script = SCRIPTS / "aistudio_db_local.sh"
    result = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    body = script.read_text(encoding="utf-8")
    assert "AI_STUDIO_APPLY_MIGRATIONS" in body
    assert "MIGRAR_SOMENTE_AI_STUDIO" in body
    assert "--single-transaction" in body
    assert 'aistudio_migration_guard.sql' in body
    assert 'aistudio_post_migration_roles.sql' in body
    assert "5433" in body
    assert "frcaixinha_aistudio_dev" in body
    assert "frcaixinha_2_2_dev" not in body


def test_migration_guard_rejects_wrong_cluster_and_nonempty_database():
    sql = (SCRIPTS / "aistudio_migration_guard.sql").read_text(encoding="utf-8")
    assert "current_setting('data_directory')" in sql
    assert "frcaixinha_aistudio_pg18" in sql
    assert "inet_server_port() <> 5433" in sql
    assert "table_count <> 0" in sql
    assert "rolbypassrls" in sql
    assert "RAISE EXCEPTION" in sql


def test_master_bootstrap_is_disabled_by_default_without_db_access():
    script = SCRIPTS / "bootstrap_aistudio_master.py"
    env = os.environ.copy()
    env.pop("AI_STUDIO_ALLOW_MASTER_BOOTSTRAP", None)
    result = subprocess.run([sys.executable, str(script)], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 2, result.stderr
    assert "BLOQUEADO" in result.stdout
    content = script.read_text(encoding="utf-8")
    assert "PROVISIONAR_MASTER_AI_STUDIO" in content
    assert "frcaixinha_aistudio_pg18" in content
    assert "from bootstrap_master import main as existing_bootstrap" in content


def test_app_roles_are_separate_and_non_superuser():
    sql = (SCRIPTS / "aistudio_post_migration_roles.sql").read_text(encoding="utf-8")
    assert "GRANT frcaixinha_app_role TO frc_ai_app;" in sql
    assert "GRANT frcaixinha_auth_role TO frc_ai_auth;" in sql
    assert "rolsuper" in sql and "rolbypassrls" in sql
    assert "public.sessions" in sql



def test_p0_01j_migration_wrapper_only_explicitly_applies_with_backup():
    script = SCRIPTS / "aistudio_local_migration.sh"
    result = subprocess.run(["bash","-n",str(script)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    content=script.read_text(encoding="utf-8")
    for flag in ("AI_STUDIO_APPROVED_SHA","AI_STUDIO_LOCAL_MIGRATION",
                 "AUTORIZO_MIGRACAO_AI_STUDIO","--passphrase","--decrypt",
                 "pg_restore --list","aistudio_db_local.sh",
                 'read -r -s -p', 'db_password </dev/tty',
                 'export PGPASSWORD="$db_password"', 'frc_ai_owner -w'):
        assert flag in content
    assert "frc_ai_owner -W" not in content, "Nao permitir dois prompts de senha simultaneos"


def test_p0_01j_verifier_setup_requires_explicit_consent_and_no_secrets_in_git():
    script=SCRIPTS/"aistudio_local_api_setup.py"
    result=subprocess.run([sys.executable,str(script)],capture_output=True,
                          text=True,timeout=10)
    assert result.returncode==2
    assert "BLOQUEADO" in result.stderr
    content=script.read_text(encoding="utf-8")
    for flag in ("AI_STUDIO_LOCAL_API_SETUP","CONFIGURAR_VERIFICADOR_AI_STUDIO",
                 "frc_ai_verifier","AUTH_VERIFIER_DATABASE_URL","0o600",
                 "getpass.getpass"):
        assert flag in content
