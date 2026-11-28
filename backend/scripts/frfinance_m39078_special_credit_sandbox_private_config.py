#!/usr/bin/env python3
"""FR Finance M39078: ativar/desativar SOMENTE o sandbox local de campanhas.

--inspect: lê configuração privada e estado da API, sem escrita.
--enable: após backup e confirmação, prepara api.env para reboot MANUAL
          da FastAPI existente. Nenhum processo é parado/reiniciado.
--disable: grava NO com backup/confirmacao. Requer reboot manual.
Não conecta PostgreSQL, não executa empréstimo, Pix, webhooks ou marketing.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shlex
import sys
import tempfile

from backend.scripts.frfinance_m39054_auth_pg18_preflight import verify_original
from backend.scripts.frfinance_m39057_stored_verifier_readonly import ENV_PATH, GuardBlocked
from backend.scripts.frfinance_m39058_three_roles_from_private_env import collect_urls
from backend.scripts.frfinance_m39063_manual_api_handoff_preflight import (
    api_state, check_private_homologation, read_private_flags,
)

KEY = "FR_FINANCE_SPECIAL_CREDIT_SANDBOX"
LINE = re.compile(r"^\s*(?:export\s+)?FR_FINANCE_SPECIAL_CREDIT_SANDBOX\s*=")
OFF = frozenset(("NO", "OFF", "0", "FALSE", ""))


def existing_value(raw: str) -> tuple[str, int | None]:
    index = None
    current = "UNSET"
    for number, item in enumerate(raw.splitlines()):
        if not LINE.match(item):
            continue
        if index is not None:
            raise GuardBlocked("DUPLICATE_SANDBOX_FLAG")
        index = number
        value = item.split("=", 1)[1].strip()
        try:
            tokens = shlex.split(value, posix=True)
        except ValueError:
            raise GuardBlocked("MALFORMED_SANDBOX_FLAG") from None
        if len(tokens) != 1 or tokens[0] not in (*OFF, "YES"):
            raise GuardBlocked("UNSUPPORTED_SANDBOX_FLAG")
        current = "YES" if tokens[0] == "YES" else "NO"
    return current, index


def replace_flag(raw: str, value: str) -> str:
    if value not in ("YES", "NO"):
        raise GuardBlocked("INVALID_SANDBOX_REQUEST")
    _, index = existing_value(raw)
    lines = raw.splitlines()
    if index is None:
        lines.append(KEY + "=" + value)
    else:
        lines[index] = KEY + "=" + value
    return "\n".join(lines) + "\n"


def private_config_read() -> tuple[str, str]:
    # collect_urls valida dono, permissoes, caminho original e symlinks
    # ANTES de ler a configuracao completa ou expor qualquer estado.
    collect_urls()
    flags = read_private_flags()
    check_private_homologation(flags)
    if ENV_PATH.is_symlink() or not ENV_PATH.is_file():
        raise GuardBlocked("PRIVATE_CONFIG_NOT_REGULAR")
    if ENV_PATH.stat().st_size > 262144:
        raise GuardBlocked("PRIVATE_CONFIG_OVERSIZE")
    original = ENV_PATH.read_text(encoding="utf-8")
    current, _ = existing_value(original)
    return original, current


def write_private_config(previous: str, replacement: str) -> None:
    if previous == replacement:
        return
    folder = ENV_PATH.parent
    marker = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = folder / (".api.env.m39078." + marker + "." + str(os.getpid()) + ".bak")
    data = previous.encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(backup, flags, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        backup.unlink(missing_ok=True)
        raise
    fd2, temporary = tempfile.mkstemp(prefix=".api.env.m39078.", dir=folder)
    try:
        with os.fdopen(fd2, "wb") as stream:
            stream.write(replacement.encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        # Nao substituir se outro processo/operador alterou o arquivo.
        if ENV_PATH.is_symlink() or ENV_PATH.read_text(encoding="utf-8") != previous:
            raise GuardBlocked("PRIVATE_CONFIG_CHANGED_CONCURRENTLY")
        os.replace(temporary, ENV_PATH)
        os.chmod(ENV_PATH, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print("M39078_PRIVATE_BACKUP=PASS_0600_NO_PATH_DISCLOSURE")
    print("M39078_PRIVATE_CONFIG_ATOMIC_UPDATE=PASS")


def main() -> int:
    parser=argparse.ArgumentParser()
    option=parser.add_mutually_exclusive_group(required=True)
    option.add_argument("--inspect",action="store_true")
    option.add_argument("--enable",action="store_true")
    option.add_argument("--disable",action="store_true")
    args=parser.parse_args()
    print("=== FR FINANCE M39078 — CREDITO ESPECIAL LOCAL SANDBOX ===")
    try:
        verify_original()
        raw,current=private_config_read()
        active=api_state()
        if active != "AUTH_TEST_MODE_ALREADY_ACTIVE_CHECK_READINESS":
            raise GuardBlocked("FASTAPI_AUTH_MODE_NOT_ATTESTED")
        print("M39078_THREE_PRIVATE_DATABASE_ROLES=FR_FINANCE_PG18_5433_PASS")
        print("M39078_LOCAL_AUTH_MODE=TEST_MODE_PASS")
        print("M39078_EXTERNAL_SERVICES=OFF_PASS")
        print("M39078_CONFIG_SANDBOX=" + current)
        if args.inspect:
            print("M39078_STATUS=PASS_READ_ONLY")
            return 0
        target="YES" if args.enable else "NO"
        if current==target:
            print("M39078_CONFIG=ALREADY_" + target + "_NO_WRITE")
            print("M39078_STATUS=PASS_NO_CHANGE")
            return 0
        if not sys.stdin.isatty():
            raise GuardBlocked("INTERACTIVE_OPERATOR_REQUIRED")
        phrase=("ATIVAR_CREDITO_ESPECIAL_SOMENTE_HOMOLOGACAO"
                if args.enable else "DESATIVAR_CREDITO_ESPECIAL_SOMENTE_HOMOLOGACAO")
        print("M39078_SCOPE=ONLY_PRIVATE_API_ENV_NO_DATABASE_WRITES")
        print("M39078_AFTER_CONFIG=MANUAL_FASTAPI_RESTART_REQUIRED")
        confirmation=input("Digite " + phrase + " para confirmar: ").strip()
        if confirmation != phrase:
            raise GuardBlocked("OPERATOR_CANCELLED")
        write_private_config(raw,replace_flag(raw,target))
        print("M39078_CONFIG_SANDBOX_STAGED=" + target)
        print("M39078_ACTIVE_API_UNCHANGED_UNTIL_RESTART=TRUE")
        print("M39078_STATUS=PASS_STAGED_MANUAL_FASTAPI_RESTART_REQUIRED")
        return 0
    except (GuardBlocked, RuntimeError) as error:
        print("M39078_STATUS=BLOCKED_" + str(error))
        return 2
    except Exception as error:
        print("M39078_STATUS=BLOCKED_" + type(error).__name__)
        return 2
    finally:
        print("M39078_PG18_DATABASE_WRITES=NONE")
        print("M39078_MIGRATIONS=NONE")
        print("M39078_PROCESS_START_STOP=NONE")
        print("M39078_REAL_CREDIT=OFF")
        print("M39078_PIX_REAL=OFF")
        print("M39078_EXTERNAL_DELIVERY=OFF")
        print("M39078_SECRETS_EXPOSED=NONE")


if __name__ == "__main__":
    raise SystemExit(main())
