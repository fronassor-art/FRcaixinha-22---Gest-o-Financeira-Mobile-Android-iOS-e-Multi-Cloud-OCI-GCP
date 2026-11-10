"""M37439 local installer is gated and cannot execute automatically."""
from pathlib import Path
import ast,subprocess,os
ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"backend/scripts/aistudio_dev_price_fixture_reset_guarded.py"
def test_python_syntax_and_bad_mode_fail_closed():
    ast.parse(SCRIPT.read_text())
    r=subprocess.run(["python",str(SCRIPT),"unsafe-mode"],cwd=ROOT,
       capture_output=True,text=True,timeout=8)
    assert r.returncode==2 and "M37439_REASON=MODE_INVALID" in r.stdout
def test_original_pg18_only_backup_and_double_consent():
    s=SCRIPT.read_text()
    for term in (
      'DB="frcaixinha_aistudio_dev"', 'ROLE="frc_ai_owner"',
      'frcaixinha_aistudio_pg18', 'BACKUP_SHA256',
      'FR_FINANCE_M37439_ENABLE_APPLY','FR_FINANCE_APPROVED_SHA',
      'SYNTHETIC_BASELINE_CHANGED','GENERAL_AUDIT_SQL',
      'FASTAPI_ACTIVE_STOP_BEFORE_APPLY',
      'OTHER_DATABASE_CLIENTS_STILL_CONNECTED',
      'AUTORIZO_LIMPEZA_SINTETICA_2027',
      'AUTORIZO_EXCECAO_AUDITORIA_DEV',
      'verify_backup_decryption()','pg_restore","--list',
      'M37439_PREFLIGHT=READ_ONLY_PASS',
      'M37439_DB_WRITES=NO',
      'M37439_IMMUTABLE_AUDIT_TRIGGERS=RESTORED',
    ):assert term in s,term
    assert s.index('if mode=="preflight":')<s.index('confirm("AUTORIZO_LIMPEZA_SINTETICA_2027")')
def test_no_new_database_no_auto_apply():
    s=SCRIPT.read_text()
    for forbidden in ("createdb","dropdb","CREATE DATABASE","DROP DATABASE",
                      "DELETE FROM public.","UPDATE public.","TRUNCATE ","ALTER TABLE "):
        assert forbidden not in s
    assert "default_transaction_read_only=on" in s
    wf=(ROOT/".github/workflows/validacao-atualizacao.yml").read_text()
    assert "M37439 — aplicador local" in wf
    assert "aistudio_dev_price_fixture_reset_guarded.py apply" not in wf
