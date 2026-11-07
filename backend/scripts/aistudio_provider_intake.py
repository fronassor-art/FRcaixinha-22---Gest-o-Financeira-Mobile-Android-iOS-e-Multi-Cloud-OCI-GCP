#!/usr/bin/env python3
"""M27800 — safe operator intake in Termux, public metadata ONLY.

Stores file outside Git checkout, chmod 0600; never requests, accepts,
stores, echoes or prints credentials. No database/network/OCI/SMTP/MP calls.

Usage:
 PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py init
 PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py fields
 PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py set KEY VALUE
 PYTHONPATH=backend python3 backend/scripts/aistudio_provider_intake.py audit
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import stat
import sys

from app.provider_intake_schema import (
    FIELDS, FIELD_BY_KEY, IntakeBlocked, intake_audit,
    new_manifest, validate_field, validate_manifest,
)


ROOT_DIR = ".config/frfinance-aistudio"
FILENAME = "provider-public-inputs.json"
MAX_LENGTH = 16384


def _deny() -> IntakeBlocked:
    return IntakeBlocked("M27800_PRIVATE_PUBLIC_INTAKE_BLOCKED")


def _default_file() -> Path:
    return Path.home() / ROOT_DIR / FILENAME


def _check_location(path: Path, *, create_dir: bool) -> None:
    parent = path.parent
    if parent.is_symlink() or (path.exists() and path.is_symlink()):
        raise _deny()
    if create_dir:
        parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not parent.is_dir():
        raise _deny()
    if (stat.S_IMODE(parent.stat().st_mode) & 0o077) != 0:
        raise _deny()
    if path.exists():
        info = path.stat()
        if not stat.S_ISREG(info.st_mode) or (stat.S_IMODE(info.st_mode) & 0o177) != 0:
            raise _deny()
        if info.st_uid != os.getuid():
            raise _deny()


def _reject_duplicates(pairs):
    result = {}
    for k,v in pairs:
        if k in result:
            raise _deny()
        result[k] = v
    return result


def read_file(path: Path) -> dict:
    _check_location(path,create_dir=False)
    if not path.is_file() or path.stat().st_size > MAX_LENGTH:
        raise _deny()
    try:
        data = json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_reject_duplicates)
        return validate_manifest(data)
    except (UnicodeError,ValueError,TypeError,OSError):
        raise _deny() from None


def _atomic_save(path: Path, data: dict, *, must_be_new=False) -> None:
    _check_location(path,create_dir=True)
    if must_be_new and path.exists():
        raise _deny()
    payload=(json.dumps(validate_manifest(data),indent=2,sort_keys=True)
             + "\n").encode("utf-8")
    if len(payload)>MAX_LENGTH:
        raise _deny()
    tmp=path.parent / (".provider-intake-"+secrets.token_hex(12)+".tmp")
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL
    if hasattr(os,"O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd=None
    try:
        fd=os.open(tmp,flags,0o600)
        with os.fdopen(fd,"wb") as handle:
            fd=None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if must_be_new and path.exists():
            raise _deny()
        os.replace(tmp,path)
    finally:
        if fd is not None:
            os.close(fd)
        tmp.unlink(missing_ok=True)


def initialize(path: Path) -> None:
    _atomic_save(path,new_manifest(),must_be_new=True)


def save_public_field(path: Path,key: str,value: str) -> None:
    # Reject KEY first, before parsing any potential secret value.
    approved=validate_field(key,value)
    saved=read_file(path)
    saved["public_inputs"][key]=approved
    _atomic_save(path,saved)


def remove_public_field(path: Path,key: str) -> None:
    if key not in FIELD_BY_KEY:
        raise _deny()
    saved=read_file(path)
    saved["public_inputs"].pop(key,None)
    _atomic_save(path,saved)


def _print_audit(path: Path) -> None:
    data=read_file(path)
    report=intake_audit(data)
    print("FR_FINANCE_INTAKE=READ_ONLY")
    print("FR_FINANCE_SECRET_VALUES=NEVER_COLLECTED")
    print("FR_FINANCE_REAL_MAIL=OFF")
    print("FR_FINANCE_REAL_USER_ACTIVATION=OFF")
    print("FR_FINANCE_PIX_INBOUND=OFF")
    print("FR_FINANCE_PIX_OUTBOUND=OFF")
    print("FR_FINANCE_EXTERNAL_ATTESTATION=REQUIRED")
    for gate in report["gates"]:
        print("GATE_"+gate["gate"]+"="+gate["status"])
        for key in gate["missing_public_fields"]:
            print("MISSING_"+gate["gate"]+"="+key)
    print("PUBLIC_FIELDS_PRESENT_COUNT="+str(len(report["public_fields_present"])))
    print("PUBLIC_FIELDS_MISSING_COUNT="+str(len(report["public_fields_absent"])))
    print("FR_FINANCE_PUBLIC_INTAKE_AUDIT=PASS")


def main(argv=None) -> int:
    parser=argparse.ArgumentParser(
        description="FR Finance AI Studio — somente identificadores públicos; NUNCA insira senhas, tokens, secrets ou DSNs."
    )
    parser.add_argument("action",choices=("init","fields","set","unset","audit"))
    parser.add_argument("key",nargs="?")
    parser.add_argument("value",nargs="?")
    args=parser.parse_args(argv)
    path=_default_file()
    try:
        if args.action=="fields":
            if args.key is not None or args.value is not None:
                raise _deny()
            for field in FIELDS:
                print(field.key+": "+field.description)
        elif args.action=="init":
            if args.key is not None or args.value is not None:
                raise _deny()
            initialize(path)
            print("FR_FINANCE_PUBLIC_INTAKE_INITIALIZED=PASS")
        elif args.action=="set":
            if args.key is None or args.value is None:
                raise _deny()
            save_public_field(path,args.key,args.value)
            print("FR_FINANCE_PUBLIC_FIELD_SAVED=PASS")
        elif args.action=="unset":
            if args.key is None or args.value is not None:
                raise _deny()
            remove_public_field(path,args.key)
            print("FR_FINANCE_PUBLIC_FIELD_UNSET=PASS")
        elif args.action=="audit":
            if args.key is not None or args.value is not None:
                raise _deny()
            _print_audit(path)
        return 0
    except (IntakeBlocked,OSError):
        print("FR_FINANCE_PUBLIC_INTAKE=BLOCKED_INVALID_OR_MISSING_INPUT",file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
