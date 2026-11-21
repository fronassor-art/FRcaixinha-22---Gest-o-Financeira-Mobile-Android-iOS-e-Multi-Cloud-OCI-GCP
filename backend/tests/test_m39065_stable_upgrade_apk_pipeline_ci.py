"""M39065: compilar APK principal atualizável com assinatura fixa e versão crescente."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = (ROOT / ".github/workflows/frfinance-android-debug-m39050.yml")
GRADLE = (ROOT / "android/app/build.gradle")


def test_android_main_debug_identity_without_diagnostic_suffix():
    gradle = GRADLE.read_text()
    assert 'applicationId "com.frcaixinha.app"' in gradle
    assert 'applicationIdSuffix diagnosticParallel ? ".aistudio.diag" : ".aistudio"' in gradle
    workflow = WORKFLOW.read_text()
    assert 'FR_FINANCE_ANDROID_PARALLEL_DIAGNOSTIC: "0"' in workflow
    assert 'com.frcaixinha.app.aistudio' in workflow
    assert "com.frcaixinha.app.aistudio.diag" not in workflow


def test_requires_existing_stable_signing_no_ephemeral_fallback():
    w = WORKFLOW.read_text()
    assert 'FRCAIXINHA_ANDROID_REQUIRE_STABLE_SIGNING: "1"' in w
    assert 'secrets.FRCAIXINHA_ANDROID_KEYSTORE_BASE64' in w
    assert 'secrets.FRCAIXINHA_ANDROID_STORE_PASSWORD' in w
    assert 'secrets.FRCAIXINHA_ANDROID_KEY_ALIAS' in w
    assert 'secrets.FRCAIXINHA_ANDROID_KEY_PASSWORD' in w
    assert 'FRCAIXINHA_ANDROID_KEYSTORE_FILE' in w
    assert 'FRCAIXINHA_ANDROID_VERSION_CODE' in w
    assert 'NO_EPHEMERAL_DEBUG_KEY' in w
    assert 'keytool -genkeypair' not in w
    assert 'debug.keystore' not in w
    assert 'FR_FINANCE_ANDROID_PARALLEL_DIAGNOSTIC: "1"' not in w


def test_detects_known_installed_main_certificate_and_prohibits_mismatch():
    w = WORKFLOW.read_text()
    assert 'ab003bfd9a496e211370ff4dfcc5044ec19e1151b69ad488d7ec1b0f34ce31c7' in w
    assert 'APK_CERT_MISMATCH' in w
    assert 'KEYSTORE_CERT_MISMATCH' in w
    assert 'apksigner' in w
    assert 'aapt' in w
    assert 'versionCode' in w
    assert 'MIN_INSTALLED_CODE = 1080' in w


def test_m39065_fails_closed_on_external_operations():
    w = WORKFLOW.read_text()
    assert 'FR_FINANCE_PIX_REAL: "OFF"' in w
    assert 'FR_FINANCE_ACCESS_MAIL_ENABLE: "OFF"' in w
    assert 'FR_FINANCE_ACCESS_MAIL_WORKER: "OFF"' in w
    assert 'FR_FINANCE_REAL_USER_ACTIVATION: "OFF"' in w
    for forbidden in (
        "adb install", "pm install", "pip install -e", "ALTER ROLE",
        "pg_ctl start", "git push", "FR_FINANCE_PIX_REAL: \"ON\"",
    ):
        assert forbidden not in w
