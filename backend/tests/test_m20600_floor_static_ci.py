"""M20600: lower-bound correction without modifying legacy obligations."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def test_minimum_is_enforced_on_new_requests_only():
    api=(ROOT/"backend/app/routers/cycle_contribution_price.py").read_text()
    assert "ge=15000" in api
    assert "legacy_below_minimum" in api
    assert "cycle_price_change" in api
    ui=(ROOT/"src/services/cyclePriceBoundary.ts").read_text()
    assert "cents<15000" in ui
    historical=(ROOT/"backend/scripts/aistudio_homologation_cycle.py").read_text()
    assert "script legado R$100 proibido" in historical
    assert "UPDATE public.contributions" not in historical
