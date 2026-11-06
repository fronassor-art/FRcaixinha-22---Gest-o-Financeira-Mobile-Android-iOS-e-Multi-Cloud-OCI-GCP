"""M23400 — OCI Vault secret identifiers must use Oracle's vaultsecret type."""
from pathlib import Path
import pytest
from app.oci_secret_bridge import _OCID as READ_ID
from app.oci_mp_staging_server import _SECRET_OCID as SERVER_ID
from app.mp_oauth_staging_repository import _OCID as PKCE_ID

ROOT=Path(__file__).resolve().parents[1]
VALID="ocid1.vaultsecret.oc1.sa-saopaulo-1.syntheticabcdef123456"
LEGACY="ocid1.secret.oc1.sa-saopaulo-1.syntheticabcdef123456"

@pytest.mark.parametrize("pattern",[READ_ID,SERVER_ID,PKCE_ID])
def test_runtime_accepts_true_vaultsecret_ocid_and_rejects_legacy(pattern):
    assert pattern.fullmatch(VALID) is not None
    assert pattern.fullmatch(LEGACY) is None

@pytest.mark.parametrize("path",[
    "staging_migrations/034_mp_signed_webhook_staging_only.sql",
    "staging_migrations/035_pix_payment_automation_staging_only.sql",
    "staging_migrations/045_mp_oauth_attempts_staging_only.sql",
])
def test_staging_sql_requires_real_secret_type_and_retains_guard(path):
    content=(ROOT/path).read_text(encoding="utf-8")
    assert "ocid1[.]vaultsecret[.]" in content
    assert "ocid1[.]secret[.]" not in content
    assert "frcaixinha_staging" in content
    assert "BEGIN;" in content and "COMMIT;" in content

@pytest.mark.parametrize("path",[
    "ci_migrations/033_staging_orders_fixture_ci_only.sql",
    "ci_migrations/035_staging_webhook_probe_ci_only.sql",
    "ci_migrations/039_oauth_state_atomic_probe_ci_only.sql",
])
def test_disposable_ci_fixtures_are_fake_but_use_realistic_ocid_prefix(path):
    content=(ROOT/path).read_text(encoding="utf-8")
    assert "ocid1.vaultsecret." in content
    assert "ocid1.secret." not in content

def test_staging_chain_still_forbids_local_pg5433_and_real_money():
    script=(ROOT/"scripts/aistudio_staging_chain_ci.sh").read_text()
    assert "FRCAIXINHA_CI_ISOLATED" in script
    assert "GITHUB_ACTIONS" in script
    assert 'PGPORT:-}" = "5432"' in script
    assert "OCI_APPLY=NOT_EXECUTED" in script
    assert "REAL_MONEY=OFF" in script
