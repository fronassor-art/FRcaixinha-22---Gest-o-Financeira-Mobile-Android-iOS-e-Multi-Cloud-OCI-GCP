"""M40940: actual source plan summarized in Master response, fail closed."""
from __future__ import annotations
from pathlib import Path
from unittest.mock import patch
from app.launch_readiness import _supermacro_source_readiness, readiness_manifest
from scripts.frfinance_m40939_release_gate import ROOT, MANIFEST


def test_master_preview_matches_single_manifest_not_fake_completion():
    plan=_supermacro_source_readiness()
    assert plan["status"]=="BLOCKED"
    assert plan["source"]=="SOURCE_ONLY_NOT_RUNTIME_ATTESTED"
    assert plan["plan_available"] is True
    assert plan["total_tasks"]==34
    assert plan["pending_tasks"]==33
    assert [row["id"] for row in plan["phases"]] == [
        "P0","P1","P2","P3","P4","P5",
    ]
    assert all(row["status"].startswith("BLOCKED_") for row in plan["phases"])
    result=readiness_manifest({"FR_FINANCE_FORCE_RELEASE":"true"})
    assert result["supermacropacote"]==plan
    assert result["status"]=="BLOCKED"
    assert result["sql_trust"]["status"]=="NO_GO"
    assert result["real_pix_active"] is False


def test_missing_source_is_not_converted_into_ready():
    with patch.object(Path,"read_text",side_effect=OSError("missing")):
        plan=_supermacro_source_readiness()
    assert plan=={
        "status":"BLOCKED","source":"SOURCE_ONLY_NOT_RUNTIME_ATTESTED",
        "plan_available":False,"total_tasks":0,"pending_tasks":0,
        "phases":[],
    }


def test_no_new_route_secret_exposure_or_system_mutation():
    src=(ROOT/"backend/app/launch_readiness.py").read_text()
    assert '"supermacropacote": _supermacro_source_readiness()' in src
    for forbidden in ("subprocess.", "asyncpg.connect(", "psycopg.connect(",
                      "git merge", "git fetch", "INSERT INTO ", "UPDATE public."):
        assert forbidden not in src
    panel=(ROOT/"src/components/LaunchReadinessPanel.tsx").read_text()
    assert "Supermacropacote — etapas e dependências" in panel
    assert "Nenhuma fase está homologada" in panel
    assert "Produção segue bloqueada" in panel
