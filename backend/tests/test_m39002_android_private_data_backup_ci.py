"""FR Finance M39002: Android app must not back up or transfer auth/financial state.

Static Android manifest / resource CI. Does not produce a signed release APK,
does not touch real device, provider, OCI, DB, SMTP or Pix.
"""
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ANDROID = ROOT / "android/app/src/main"
NS = "{http://schemas.android.com/apk/res/android}"

DOMAINS = {"root", "file", "database", "sharedpref", "external"}


def _load(path: Path):
    return ET.parse(path).getroot()


def test_android_manifest_disables_backup_and_links_both_rule_sets():
    manifest = _load(ANDROID / "AndroidManifest.xml")
    assert manifest.tag == "manifest"
    application = manifest.find("application")
    assert application is not None
    assert application.get(NS + "allowBackup") == "false"
    assert application.get(NS + "fullBackupContent") == "@xml/full_backup_rules"
    assert application.get(NS + "dataExtractionRules") == "@xml/data_extraction_rules"
    assert application.get(NS + "debuggable") != "true"
    assert application.get(NS + "testOnly") != "true"
    assert [p.get(NS + "name") for p in manifest.findall("uses-permission")].count(
        "android.permission.INTERNET"
    ) == 1


def _assert_excluded(element):
    children = list(element)
    # Explicit deny list without wildcard-like allowances.
    assert children
    assert all(child.tag == "exclude" for child in children)
    actual = {child.get("domain"): child.get("path") for child in children}
    assert set(actual) == DOMAINS
    assert all(value == "." for value in actual.values())
    assert len(children) == len(DOMAINS)


def test_android_12_plus_disallows_cloud_and_device_to_device_transfer():
    rules = _load(ANDROID / "res/xml/data_extraction_rules.xml")
    assert rules.tag == "data-extraction-rules"
    assert {child.tag for child in rules} == {"cloud-backup", "device-transfer"}
    for tag in ("cloud-backup", "device-transfer"):
        group = rules.find(tag)
        assert group is not None
        _assert_excluded(group)
    cloud = rules.find("cloud-backup")
    assert cloud.get("disableIfNoEncryptionCapabilities") == "true"


def test_android_11_and_older_full_backup_excludes_all_common_domains():
    rules = _load(ANDROID / "res/xml/full_backup_rules.xml")
    assert rules.tag == "full-backup-content"
    _assert_excluded(rules)


def test_release_keeps_identical_package_and_requires_private_signing():
    build = (ROOT / "android/app/build.gradle").read_text(encoding="utf-8")
    config = (ROOT / "capacitor.config.ts").read_text(encoding="utf-8")
    assert 'applicationId "com.frcaixinha.app"' in build
    assert 'applicationIdSuffix diagnosticParallel ? ".aistudio.diag" : ".aistudio"' in build
    assert 'System.getenv("FR_FINANCE_ANDROID_PARALLEL_DIAGNOSTIC") == "1"' in build
    assert 'if (releaseRequested && diagnosticParallel)' in build
    assert 'throw new GradleException("M39052: pacote diagnostico nao permite release.")' in build
    assert "FR_FINANCE_ANDROID_RELEASE_KEYSTORE_FILE" in build
    assert "FR_FINANCE_ANDROID_RELEASE_KEY_PASSWORD" in build
    assert "FR_FINANCE_ANDROID_RELEASE_STORE_PASSWORD" in build
    assert "Release requer HTTPS sem cleartext." in build
    assert "FR_FINANCE_ANDROID_RELEASE_PROFILE" in config
    assert "VITE_API_URL" in config
    assert "androidScheme: localAndroidTest ? 'http' : 'https'" in config
    assert "cleartext: false" in config
    assert "appId: 'com.frcaixinha.app'" in config


def test_native_manifest_has_no_auto_verified_unproven_public_domain():
    # Domain ownership + HTTPS assetlinks.json verification are still blocked.
    # Do not advertise app-links on native build based only on registered DNS.
    manifest = _load(ANDROID / "AndroidManifest.xml")
    assert not any(
        item.get(NS + "autoVerify") == "true"
        for item in manifest.iter("intent-filter")
    )
