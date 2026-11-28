"""Macropacote 240: invariantes sintéticos, nenhum banco operacional."""
import hashlib
import re
import subprocess
from pathlib import Path

import pytest
from app.closing_readiness_preview import (
    ClosingReadinessPreview, EVIDENCE_FIELDS, evaluate_closing_readiness_synthetic
)

ROOT = Path(__file__).resolve().parents[2]
BACKUP = ROOT / "backend/scripts/aistudio_240_backup_integrity_readonly.sh"
ROLES = ROOT / "backend/scripts/aistudio_240_roles_readonly.sh"
CLOSINGS = ROOT / "backend/app/routers/closings.py"
AUDIT = ROOT / "backend/app/routers/audit.py"


def evidence(value=False):
    return {name: value for name in EVIDENCE_FIELDS}


def test_zero_evidence_is_not_authorization():
    p=evaluate_closing_readiness_synthetic(evidence())
    assert isinstance(p, ClosingReadinessPreview)
    assert p.state=="SIMULATION_ONLY_NOT_AUTHORIZED"
    assert len(p.evidence_pending)==len(EVIDENCE_FIELDS)
    assert p.evidence_marked==()
    assert not p.bank_reconciled and not p.financial_closing_authorized
    assert not p.cycle_liquidated


def test_all_evidence_marked_remains_unverified_and_not_authorized():
    p=evaluate_closing_readiness_synthetic(evidence(True))
    assert p.state=="SIMULATION_ONLY_NOT_AUTHORIZED"
    assert set(p.evidence_marked)==set(EVIDENCE_FIELDS)
    assert p.evidence_pending==()
    assert not p.bank_reconciled
    assert not p.financial_closing_authorized
    assert not p.cycle_liquidated


@pytest.mark.parametrize("name", EVIDENCE_FIELDS)
def test_each_missing_item_is_explicit(name):
    scenario=evidence(True)
    scenario[name]=False
    p=evaluate_closing_readiness_synthetic(scenario)
    assert p.evidence_pending==(name,)
    assert len(p.evidence_marked)==len(EVIDENCE_FIELDS)-1
    assert not p.financial_closing_authorized


@pytest.mark.parametrize("value", [None, 1, 0, "PASS", [], {}, float("nan")])
def test_nonboolean_evidence_rejected(value):
    scenario=evidence()
    scenario["ledger_balanced"]=value
    with pytest.raises(ValueError):
        evaluate_closing_readiness_synthetic(scenario)


def test_extra_missing_or_non_dict_rejected():
    for invalid in (None, {}, [], {**evidence(), "admin_master":True},
                    {k:v for k,v in evidence().items() if k!="ledger_balanced"}):
        with pytest.raises(ValueError):
            evaluate_closing_readiness_synthetic(invalid)


def test_bank_close_and_manual_audit_remain_blocked():
    closings=CLOSINGS.read_text(encoding="utf-8")
    audit=AUDIT.read_text(encoding="utf-8")
    assert 'Fechamento indisponível até validação' in closings
    # Reject route reopening but tolerate whitespace/reformatting of the guard.
    assert re.search(r"raise\s+HTTPException\s*\(\s*status_code\s*=\s*503\b", closings)
    assert 'Registro manual de auditoria indisponível' in audit
    assert 'raise HTTPException(status_code=503' in audit


def test_role_diagnostic_is_restricted_to_readonly_catalogs():
    src=ROLES.read_text(encoding="utf-8")
    assert "BEGIN READ ONLY;" in src
    assert "default_transaction_read_only=on" in src
    assert "frcaixinha_aistudio_dev" in src
    assert "5433" in src
    assert "frc_ai_owner" in src
    assert "relforcerowsecurity" in src
    assert "frc_ai_app" in src and "frc_ai_auth" in src and "frc_ai_verifier" in src
    assert "BACKUP_RESTORE_OPERACIONAL=PENDENTE" in src
    assert not re.search(r"\b(?:DROP|CREATE|ALTER|TRUNCATE|REVOKE|GRANT)\s+(?:TABLE|DATABASE|ROLE|SCHEMA)", src, re.I)


def _run_backup(path:Path,digest:str):
    return subprocess.run(["bash",str(BACKUP),str(path),digest],
                          text=True,capture_output=True,timeout=10)


def test_ciphertext_header_and_sha256_synthetic_only(tmp_path):
    payload=b"age-encryption.org/v1\n"+b"synthetic-header-not-a-valid-age-payload\n"*5
    source=tmp_path/"aistudio-ci-backup.age"
    source.write_bytes(payload)
    digest=hashlib.sha256(payload).hexdigest()
    result=_run_backup(source,digest)
    assert result.returncode==0,result.stderr+result.stdout
    assert "BACKUP_HASH=PASS" in result.stdout
    assert "BACKUP_DECRYPTION=NOT_TESTED" in result.stdout
    assert "BACKUP_RESTORE=NOT_TESTED" in result.stdout
    assert "DADOS_DO_BANCO_ALTERADOS=NAO" in result.stdout


def test_hash_mismatch_and_modified_header_fail_closed(tmp_path):
    source=tmp_path/"aistudio-ci.age"
    source.write_bytes(b"age-encryption.org/v1\n"+b"a"*180)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    assert _run_backup(source,"0"*64).returncode==2
    source.write_bytes(b"invalid-data"+b"a"*180)
    assert _run_backup(source,digest).returncode==2


def test_symlink_and_legacy_name_rejected(tmp_path):
    source=tmp_path/"aistudio-original.age"
    source.write_bytes(b"age-encryption.org/v1\n"+b"x"*180)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    link=tmp_path/"aistudio-link.age"
    link.symlink_to(source)
    assert _run_backup(link,digest).returncode==2
    legacy=tmp_path/"FRcaixinha_2_2_CI.age"
    legacy.write_bytes(source.read_bytes())
    assert _run_backup(legacy,digest).returncode==2


def test_script_is_inspection_not_restore():
    src=BACKUP.read_text(encoding="utf-8")
    assert "sha256sum" in src
    assert "BACKUP_RESTORE=NOT_TESTED" in src
    assert not re.search(r"\bpg_(?:restore|dump)\b",src)
    assert "age --decrypt" not in src
