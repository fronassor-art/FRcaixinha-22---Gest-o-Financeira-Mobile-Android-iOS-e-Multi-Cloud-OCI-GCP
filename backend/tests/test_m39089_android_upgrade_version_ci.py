"""M39089: reject main Android APK downgrade and certificate rotation in CI.

Source-only tests; do not read private keystores, install APK, access database
or call external services. The actual Gradle/signature checks run in Actions.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
CERT = "ab003bfd9a496e211370ff4dfcc5044ec19e1151b69ad488d7ec1b0f34ce31c7"
LAST_PROVEN_INSTALLED = 3906508
LAST_KNOWN_CANDIDATE = 3906531
PRIMARY = ROOT / ".github/workflows/validacao-atualizacao.yml"
LEGACY = ROOT / ".github/workflows/frfinance-android-debug-m39050.yml"
GRADLE = ROOT / "android/app/build.gradle"


def _android_job() -> str:
    workflow = PRIMARY.read_text()
    return workflow.split("\n  android:\n", 1)[1].split("\n  backend-sem-banco:\n", 1)[0]


def test_main_apk_package_and_fixed_keystore_match_working_m39065():
    android = _android_job()
    legacy = LEGACY.read_text()
    gradle = GRADLE.read_text()
    assert CERT in legacy, "M39089_REFERENCE_CERT_NOT_FOUND"
    assert android.count(CERT) >= 2, "M39089_MUST_PIN_CERT_BEFORE_AND_AFTER_BUILD"
    assert "ORIGINAL_APK_SIGNING_CERT_MISMATCH" in android
    assert "-storepass:env M39089_PRIVATE_STOREPASS" in android
    assert "unset M39089_PRIVATE_STOREPASS" in android
    assert "FRCAIXINHA_ANDROID_KEYSTORE_BASE64" in android
    assert "FRCAIXINHA_ANDROID_REQUIRE_STABLE_SIGNING: '1'" in android
    assert "keytool -genkeypair" not in android
    assert "debug.keystore" not in android
    assert "com.frcaixinha.app.aistudio" in android
    assert 'applicationIdSuffix diagnosticParallel ? ".aistudio.diag" : ".aistudio"' in gradle
    assert "Verified using v2 scheme (APK Signature Scheme v2): true" in android


def test_m39088_regression_cannot_emit_version_lower_than_working_apk():
    android = _android_job()
    base_match = re.search(r"version_code=\$\(\(([0-9]+) \+ GITHUB_RUN_NUMBER\)\)", android)
    assert base_match, "M39089_VERSION_MUST_BE_DERIVED_FROM_INCREASING_RUN_NUMBER"
    base = int(base_match.group(1))
    assert base + 1 > LAST_KNOWN_CANDIDATE > LAST_PROVEN_INSTALLED
    assert base + 1359 > 3906508 > 1359
    assert "ANDROID_VERSION_CODE_DOWNGRADE" in android
    assert "version_code <= 3906531" in android
    assert 'FRCAIXINHA_ANDROID_VERSION_CODE=$version_code' in android
    assert "FRCAIXINHA_ANDROID_VERSION_CODE: ${{ github.run_number }}" not in android
    assert 'grep -F "versionCode=\'${FRCAIXINHA_ANDROID_VERSION_CODE}\'"' in android
    assert 'test "${FRCAIXINHA_ANDROID_VERSION_CODE:-0}" -gt 3906531' in android
    assert 'versionCode androidCiBuildNumber ? Integer.parseInt(androidCiBuildNumber) : 1' in GRADLE.read_text()


def test_does_not_modify_real_finances_or_allow_release():
    android = _android_job()
    workflow = PRIMARY.read_text()
    assert "Compilar APK debug" in android
    assert "assembleDebug" in android
    assert "assembleRelease" not in android
    assert "actions/upload-artifact@v4" in android
    assert "needs: [frontend, backend-sem-banco, postgres-isolado, postgres18-preflight]" in android
    assert "FRCAIXINHA_ANDROID_LOCAL_TEST: '1'" in android
    assert "VITE_API_URL: http://127.0.0.1:8000" in android
    assert "FRCAIXINHA_ANDROID_REQUIRE_STABLE_SIGNING: '1'" in android
    assert "PIX_REAL=ON" not in workflow
    assert "adb install" not in android
    assert "pm install" not in android
