"""M37440 report actual vs expected safe PG count mismatches; block all apply."""
from pathlib import Path
import ast
import sys
import pytest
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"backend/scripts"))
import aistudio_dev_price_fixture_reset_guarded as guard

def test_exact_preflight_baseline_is_still_accepted():
 assert len(guard.BASELINE)==len(guard.BASELINE_LABELS)==18
 guard.require_baseline(guard.BASELINE)

def test_missing_minimum_contract_constraint_diagnosed_but_not_ignored(capsys):
 actual=guard.BASELINE[:-1]+(0,)
 with pytest.raises(guard.Blocked,match="SYNTHETIC_BASELINE_CHANGED"):
  guard.require_baseline(actual)
 out=capsys.readouterr().out
 assert "M37440_SQL_MINIMUM_150_CONSTRAINTS_EXPECTED=2" in out
 assert "M37440_SQL_MINIMUM_150_CONSTRAINTS_OBSERVED=0" in out
 assert "M37440_APPLY=BLOCKED_UNTIL_REVIEW" in out
 assert "M37440_DB_WRITES=NONE" in out

def test_unexpected_ledger_entry_reports_count_and_blocks(capsys):
 values=list(guard.BASELINE);values[7]=3
 with pytest.raises(guard.Blocked,match="SYNTHETIC_BASELINE_CHANGED"):
  guard.require_baseline(tuple(values))
 out=capsys.readouterr().out
 assert "M37440_LEDGER_ENTRIES_EXPECTED=0" in out
 assert "M37440_LEDGER_ENTRIES_OBSERVED=3" in out
 assert "M37440_SQL_MINIMUM_150_CONSTRAINTS_OBSERVED" not in out

@pytest.mark.parametrize("bad",[None,0,[],(1,)*17,tuple([-1]*18),tuple([1.0]*18)])
def test_malformed_baseline_fails_closed_without_printing_raw_data(bad,capsys):
 with pytest.raises(guard.Blocked,match="SYNTHETIC_BASELINE_UNREADABLE"):
  guard.require_baseline(bad)
 assert "M37440_" not in capsys.readouterr().out

def test_original_db_readonly_preflight_unchanged():
 src=(ROOT/"backend/scripts/aistudio_dev_price_fixture_reset_guarded.py").read_text()
 ast.parse(src)
 assert 'DB="frcaixinha_aistudio_dev"' in src
 assert 'PORT=5433' in src
 assert "default_transaction_read_only=on" in src
 assert "require_baseline(counts)" in src
 assert 'if mode=="preflight":' in src
 assert 'FR_FINANCE_M37439_ENABLE_APPLY' in src
 assert 'SYNTHETIC_BASELINE_CHANGED' in src
 for forbidden in ("CREATE DATABASE","DROP DATABASE","dropdb","createdb"):
  assert forbidden not in src
