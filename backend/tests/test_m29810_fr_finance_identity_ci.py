"""M29810: distinctive FR Finance identity without rewriting old legal evidence."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def text(p): return (ROOT/p).read_text()

def test_canonical_caderno_and_contract_independent_from_2_2():
    readme=text("README.md")
    assert "Frente FR Finance AI Studio independente do FR Caixinha 2.2" in readme
    assert "docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md" in readme
    assert "docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md" in readme
    for p in ("docs/CADERNO_MESTRE_FR_FINANCE_AI_STUDIO.md",
              "docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md"):
        body=text(p)
        assert "FR Finance" in body
        assert "FR Caixinha 2.2" in body
        assert "histor" in body.lower()
        assert "produção" in body.lower() or "produção" in body
    assert "$HOME/fr-finance" in readme

def test_visible_metadata_backend_and_package_identity():
    meta=json.loads(text("metadata.json"))
    pkg=json.loads(text("package.json"))
    lock=json.loads(text("package-lock.json"))
    assert meta["name"]=="FR Finance — Gestão Financeira"
    assert pkg["name"]==lock["name"]==lock["packages"][""]["name"]=="fr-finance-aistudio"
    assert 'PROJECT_NAME: str = "FR Finance — API de homologação"' in text("backend/app/config.py")
    main=text("backend/app/main.py")
    assert "FR Caixinha — backend" not in main
    assert '"FR Caixinha"' not in main
    assert '"FR Finance"' in main

def test_legacy_identifiers_and_pdfs_remain_untouched():
    cap=text("capacitor.config.ts")
    cfg=text("backend/app/config.py")
    assert "com.frcaixinha.app" in cap
    assert 'SESSION_COOKIE_NAME: str = "frcaixinha_session"' in cfg
    assert "frcaixinha_aistudio_dev" in text("docs/CONTRATO_TECNICO_MESTRE_FR_FINANCE_AI_STUDIO.md")
    files=list((ROOT/"public/assets/aistudio").glob("FRcaixinha_2.2*.pdf"))
    assert len(files)==2
    assert all(p.stat().st_size > 100_000 for p in files)

def test_renaming_script_is_local_only_and_not_database():
    script=text("backend/scripts/frfinance_rename_termux_directory.sh")
    assert 'OLD="$HOME/frcaixinha-aistudio-mobile"' in script
    assert 'NEW="$HOME/fr-finance"' in script
    for forbidden in ("git clone","git push","DROP DATABASE","psql ","oci compute","rm -rf"):
        assert forbidden not in script
