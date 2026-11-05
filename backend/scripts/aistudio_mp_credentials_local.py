#!/usr/bin/env python3
"""M21200: store ONLY a Mercado Pago TEST access token with AGE encryption.

Never connects to Mercado Pago, never stores production credentials, never
modifies PostgreSQL, and never enables payments. No token in logs or arguments.
"""
from __future__ import annotations

import getpass
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path.home() / "frcaixinha-aistudio-mobile"
BASE = Path.home() / ".config/frcaixinha-aistudio-mobile"
DEST = BASE / "mp-sandbox-credentials.json.age"
BRANCH = "atualizacao-ai-studio-9b46a63187"
_APP = re.compile(r"[0-9]{1,40}\Z")
_TOKEN = re.compile(r"APP_USR-[A-Za-z0-9_-]{16,2048}\Z")


def fail(reason: str) -> None:
    print("M21200_BLOQUEADO: " + reason, file=sys.stderr)
    raise SystemExit(2)


def valid_app_id(value: str) -> bool:
    return isinstance(value, str) and _APP.fullmatch(value) is not None


def valid_test_token(value: str) -> bool:
    # Prefix is not cryptographic proof of test environment.
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def ensure_project() -> None:
    expected = os.getenv("AI_STUDIO_APPROVED_SHA", "")
    if not re.fullmatch(r"[0-9a-f]{40}", expected):
        fail("SHA completo obrigatório")
    try:
        if (git("branch", "--show-current") != BRANCH or
                git("rev-parse", "HEAD") != expected or
                git("status", "--porcelain")):
            fail("Git não corresponde ao checkpoint aprovado")
    except (OSError, subprocess.CalledProcessError):
        fail("Git não verificado")
    if os.getenv("REAL_PIX_COLLECTION_ACTIVE") == "YES" or os.getenv("REAL_PIX_PAYOUT_ACTIVE") == "YES":
        fail("Modo financeiro real incompatível")


def ensure_private_dir() -> None:
    if BASE.is_symlink():
        fail("Diretório de configuração é link simbólico")
    BASE.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = BASE.stat()
    if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700:
        fail("Diretório deve pertencer ao usuário e usar chmod 700")


def audit() -> None:
    ensure_private_dir()
    if DEST.is_symlink():
        fail("Arquivo de credenciais é link simbólico")
    if not DEST.exists():
        print("M21200_MP_TEST_TOKEN=NOT_CONFIGURED")
        print("M21200_PAYMENT_NETWORK=OFF")
        return
    st = DEST.stat()
    if (not DEST.is_file() or st.st_uid != os.getuid() or
            stat.S_IMODE(st.st_mode) != 0o600 or
            st.st_size < 100 or st.st_size > 65536):
        fail("Arquivo cifrado ausente, tamanho ou permissão incorreta")
    print("M21200_MP_TEST_TOKEN=ENCRYPTED_FILE_PRESENT_UNVERIFIED")
    print("M21200_PAYMENT_NETWORK=OFF")
    print("M21200_PRODUCTION_TOKEN=NOT_STORED_BY_THIS_SCRIPT")


def store() -> None:
    ensure_private_dir()
    if DEST.exists() or DEST.is_symlink():
        fail("Credencial já presente. Não sobrescrever sem revisão de rotação.")
    if not sys.stdin.isatty():
        fail("É necessário executar no Termux interativo, sem redirecionar stdin")
    app_id = input("Client ID / ID da aplicação (apenas dígitos): ").strip()
    if not valid_app_id(app_id):
        fail("ID de aplicação inválido")
    print("No painel do Mercado Pago escolha o ambiente TESTE antes de copiar.")
    token = getpass.getpass("Access Token de TESTE (entrada oculta): ")
    if not valid_test_token(token):
        fail("Formato do token não reconhecido. Verifique a credencial no painel Teste.")
    answer = input("Confirmar armazenamento cifrado somente de TESTE? Digite CONFIRMO_TESTE_MP: ").strip()
    if answer != "CONFIRMO_TESTE_MP":
        fail("Confirmação recusada")
    payload = json.dumps({
        "environment": "TEST", "provider": "MERCADO_PAGO",
        "app_client_id": app_id, "access_token": token,
        "real_payments_enabled": False,
    }, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    token = ""
    tmp = BASE / ("mp-sandbox-" + str(os.getpid()) + ".partial.age")
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        done = subprocess.run(
            ["age", "--passphrase", "--output", str(tmp)],
            input=payload, stdout=subprocess.DEVNULL, check=False,
        )
        if done.returncode != 0 or tmp.stat().st_size < 100:
            fail("Falha ao criptografar; nenhuma credencial foi instalada")
        # Confirm decryptability, without ever writing the plaintext to disk.
        checked = subprocess.run(
            ["age", "--decrypt", str(tmp)], stdout=subprocess.DEVNULL, check=False
        )
        if checked.returncode != 0:
            fail("Senha AGE não conseguiu verificar o arquivo cifrado")
        os.replace(tmp, DEST)
        os.chmod(DEST, 0o600)
        print("M21200_MP_TEST_TOKEN=ENCRYPTED_AND_RECOVERY_CHECKED")
        print("M21200_PAYMENT_NETWORK=OFF")
        print("M21200_NO_PRODUCTION_CREDENTIALS=PASS")
    finally:
        payload = b""
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) == 2 else ""
    if mode not in ("audit", "store-test"):
        fail("Use audit ou store-test")
    ensure_project()
    if mode == "audit":
        audit()
    else:
        store()


if __name__ == "__main__":
    main()
