#!/usr/bin/env python3
"""Ferramenta local de provisionamento; senha solicitada sem eco no terminal."""
import argparse
import getpass
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from app.provisioning import create_tenant_account


def main():
    parser = argparse.ArgumentParser(description="Cria uma conta de administrador ou membro para uma caixinha existente.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--role", required=True, choices=("TENANT_ADMIN", "TENANT_MEMBER"))
    args = parser.parse_args()
    if os.getenv("CONFIRM_TENANT_PROVISIONING") != "YES" or not os.getenv("DATABASE_URL", "").startswith("postgres"):
        print("Configuração ausente: defina DATABASE_URL e CONFIRM_TENANT_PROVISIONING=YES em ambiente protegido.")
        return 2
    email = input("E-mail: ").strip()
    name = input("Nome completo: ").strip()
    cpf = input("CPF: ").strip()
    phone = input("Telefone: ").strip()
    password = getpass.getpass("Senha (mínimo 12 caracteres): ")
    confirmation = getpass.getpass("Confirme a senha: ")
    if password != confirmation:
        print("Senhas não conferem; nenhuma alteração efetuada.")
        return 1
    try:
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            create_tenant_account(conn, email=email, full_name=name, cpf=cpf, phone=phone,
                                  password=password, tenant_id=args.tenant_id, role=args.role)
    except ValueError as exc:
        print(f"Cadastro cancelado: {exc}")
        return 1
    except psycopg.Error:
        print("Cadastro cancelado por erro de banco; nenhuma alteração confirmada.")
        return 1
    print("Conta e vínculo criados. A ativação do login depende da conclusão da API de autenticação.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
