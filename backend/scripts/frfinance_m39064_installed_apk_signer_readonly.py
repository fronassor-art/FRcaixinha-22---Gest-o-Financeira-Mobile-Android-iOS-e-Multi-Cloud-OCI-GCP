#!/usr/bin/env python3
"""FR Finance M39064 — verificar chave EXISTENTE do APK principal, read-only.

Apenas a impressão digital pública é comparada em memória com a assinatura
já observada no telefone. NUNCA cria, regenera, modifica, envia ou mostra a
chave privada ou senha. Nada de ADB, instalação, PG, FastAPI ou login.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import subprocess

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original

SIGNING_DIR = Path(
    "/data/data/com.termux/files/home/.config/frcaixinha-aistudio-mobile/android-signing"
)
KEYSTORE = SIGNING_DIR / "frcaixinha-aistudio-stable.p12"
PASSWORD_FILE = SIGNING_DIR / "frcaixinha-aistudio-password.txt"
ALIAS = "frcaixinha_aistudio"
EXPECTED_MAIN_CERT = "ab003bfd9a496e211370ff4dfcc5044ec19e1151b69ad488d7ec1b0f34ce31c7"


class SignerBlocked(Exception):
    pass


def checked_regular(path: Path, maximum_bytes: int) -> None:
    try:
        if path.is_symlink():
            raise SignerBlocked("UNSAFE_SYMLINK")
        s = path.stat()
    except OSError:
        raise SignerBlocked("KEY_MATERIAL_NOT_PRESENT_OR_UNREADABLE") from None
    if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid():
        raise SignerBlocked("UNSAFE_KEY_MATERIAL_OWNER_OR_TYPE")
    if stat.S_IMODE(s.st_mode) & 0o077:
        raise SignerBlocked("UNSAFE_KEY_MATERIAL_PERMISSIONS")
    if not 0 < s.st_size <= maximum_bytes:
        raise SignerBlocked("UNEXPECTED_KEY_MATERIAL_SIZE")


def validate_paths() -> None:
    try:
        if SIGNING_DIR.is_symlink():
            raise SignerBlocked("UNSAFE_SIGNING_DIRECTORY_SYMLINK")
        st = SIGNING_DIR.stat()
    except OSError:
        raise SignerBlocked("SIGNING_DIRECTORY_NOT_FOUND") from None
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid():
        raise SignerBlocked("SIGNING_DIRECTORY_UNSAFE")
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise SignerBlocked("SIGNING_DIRECTORY_PERMISSIONS_UNSAFE")
    checked_regular(KEYSTORE, 1024 * 1024)
    checked_regular(PASSWORD_FILE, 1024)


def parse_certificate(stdout: str) -> str:
    """keytool -list -v normalmente exibe 'SHA256: AB:CD:...'."""
    results = re.findall(r"(?im)^\s*SHA256:\s*([0-9a-f:]+)\s*$", stdout)
    hashes = {item.replace(":", "").lower() for item in results}
    if len(hashes) != 1:
        raise SignerBlocked("CERTIFICATE_FINGERPRINT_NOT_UNIQUE")
    digest = hashes.pop()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise SignerBlocked("CERTIFICATE_FINGERPRINT_INVALID")
    return digest


def check_existing_signer() -> str:
    validate_paths()
    try:
        password = PASSWORD_FILE.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        raise SignerBlocked("SIGNING_PASSWORD_NOT_READABLE") from None
    if not password or "\n" in password or "\r" in password:
        raise SignerBlocked("SIGNING_PASSWORD_FORMAT_INVALID")
    environment = dict(os.environ)
    environment["FR_FINANCE_READONLY_STOREPASS"] = password
    try:
        result = subprocess.run(
            [
                "keytool", "-list", "-v",
                "-storetype", "PKCS12",
                "-keystore", str(KEYSTORE), "-alias", ALIAS,
                "-storepass:env", "FR_FINANCE_READONLY_STOREPASS",
            ],
            capture_output=True, text=True,
            env=environment, timeout=15, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        raise SignerBlocked("KEYTOOL_NOT_AVAILABLE_OR_FAILED") from None
    finally:
        environment.pop("FR_FINANCE_READONLY_STOREPASS", None)
        password = ""
    if result.returncode != 0:
        raise SignerBlocked("STORED_KEY_ALIAS_OR_PASSWORD_NOT_VERIFIED")
    return parse_certificate(result.stdout)


def main() -> int:
    print("=== FR FINANCE M39064 — ASSINATURA ORIGINAL READ ONLY ===")
    try:
        verify_original()
        digest = check_existing_signer()
    except SignerBlocked as exc:
        print("M39064_LOCAL_SIGNER=BLOCKED_" + str(exc))
        print("M39064_STATUS=BLOCKED")
        return 2
    except Exception:
        print("M39064_STATUS=BLOCKED_ORIGINAL_WORKTREE_OR_RUNTIME")
        return 2
    same = digest == EXPECTED_MAIN_CERT
    print("M39064_INSTALLED_MAIN_CERT=REFERENCE_VERSION_1080")
    print("M39064_LOCAL_KEYSTORE=" + ("MATCH_INSTALLED_MAIN" if same else "DIFFERENT_CERTIFICATE"))
    print("M39064_MAIN_PACKAGE=com.frcaixinha.app.aistudio")
    print("M39064_DIAG_PACKAGE=NOT_FOR_MAIN_UPDATES")
    print("M39064_MIN_NEXT_VERSION_CODE=1081")
    print("M39064_KEYSTORE_MODIFIED=NO")
    print("M39064_PASSWORD_DISPLAYED=NO")
    print("M39064_NEW_KEY_GENERATED=NO")
    print("M39064_APK_INSTALLED=NO")
    print("M39064_DATABASE_WRITES=NONE")
    print("M39064_FASTAPI_CHANGED=NO")
    print("M39064_PIX_REAL=OFF")
    print("M39064_STATUS=" + (
        "PASS_SIGNER_MATCH_READ_ONLY" if same else "BLOCKED_CERTIFICATE_MISMATCH"
    ))
    return 0 if same else 2


if __name__ == "__main__":
    raise SystemExit(main())
