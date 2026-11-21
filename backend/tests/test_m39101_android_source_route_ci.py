"""M39101: Android identity drift and FastAPI live-route *source* smoke.

Offline source verification, not a device/production attestation.
"""
from pathlib import Path
import re

from app.m39100_full_traceability import ROOT
from app.main import app

ROOT=Path(ROOT)


def test_android_base_and_debug_id_are_not_confused():
 capacitor=(ROOT/"capacitor.config.ts").read_text(encoding="utf-8")
 gradle=(ROOT/"android/app/build.gradle").read_text(encoding="utf-8")
 assert "appId: 'com.frcaixinha.app'" in capacitor
 assert 'namespace = "com.frcaixinha.app"' in gradle
 assert 'applicationId "com.frcaixinha.app"' in gradle
 assert 'applicationIdSuffix diagnosticParallel ? ".aistudio.diag" : ".aistudio"' in gradle
 assert 'versionNameSuffix "-AI-STUDIO-TEST"' in gradle
 assert 'releaseKeyFile = System.getenv("FR_FINANCE_ANDROID_RELEASE_KEYSTORE_FILE")' in gradle
 assert "signingConfig signingConfigs.productionRelease" in gradle
 assert "FR_FINANCE_ANDROID_RELEASE_PROFILE" in capacitor
 assert "http://127.0.0.1:8000" in capacitor  # debug only, guarded below
 assert "if (releaseProfile)" in capacitor
 assert "release não aceita Termux" in capacitor
 assert "Release requer HTTPS sem cleartext." in gradle


def test_master_admin_and_special_credit_routes_really_register_in_source():
 paths={
  (route.path,tuple(sorted(route.methods)))
  for route in app.routes
  if hasattr(route,"methods") and route.methods
 }
 assert ("/api/v1/master/exclusive-cashbox",("GET",)) in paths
 assert ("/api/v1/tenants/{tenant_id}/admin-exclusive-cashbox",("GET",)) in paths
 assert ("/api/v1/tenants/{tenant_id}/special-credit/capabilities",("GET",)) in paths
 assert not any(p.endswith("/exclusive-cashbox") and
                methods!=("GET",) for p,methods in paths)
 assert not any(p.endswith("/admin-exclusive-cashbox") and
                methods!=("GET",) for p,methods in paths)


def test_credit_special_is_never_enabled_merely_by_api_route_existence():
 credit=(ROOT/"backend/app/routers/special_credit.py").read_text(encoding="utf-8")
 assert 'FR_FINANCE_SPECIAL_CREDIT_SANDBOX' in credit
 assert 'FRCAIXINHA_TEST_AUTH' in credit
 assert '!= "production"' in credit
 assert 'db.port == 5433' in credit
 assert 'db.path == "/frcaixinha_aistudio_dev"' in credit
 assert 'raise HTTPException(503, "Crédito especial indisponível fora da homologação offline.")' in credit


def test_checkpoint_correction_does_not_rename_android_package():
 executive=(ROOT/"docs/FR_FINANCE_CP20261114_CHECKPOINT_PRODUCAO_NO_GO.md").read_text(encoding="utf-8")
 assert "DR-03 — Android package (RESOLVIDO EM AUDITORIA DE CÓDIGO M39100)" in executive
 assert "applicationIdSuffix" in executive
 assert "Não renomear pacotes" in executive
