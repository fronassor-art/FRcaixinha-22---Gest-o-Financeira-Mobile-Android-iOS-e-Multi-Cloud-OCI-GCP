"""M37500 CLI: no provider access, deterministic output, explicit OFF."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "backend/scripts/aistudio_m37500_megapack_offline.py"


def load():
    spec = importlib.util.spec_from_file_location("m37500_cli", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_summary(capsys):
    assert load().main([]) == 0
    s = capsys.readouterr().out
    assert "M37500_TASKS_PLANNED=192" in s
    assert "M37500_WORKSTREAMS=16" in s
    assert "M37500_LIVE_GATES_VERIFIED=0/20" in s
    assert "M37500_REAL_PIX=OFF" in s
    assert "M37500_SQL_APPLY=NOT_EXECUTED" in s


def test_json_summary(capsys):
    assert load().main(["json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert len(d["tasks"]) == 192
    assert d["provider_gates_verified_by_this_tool"] == 0
    assert not d["cloud_mutations_authorized"]
