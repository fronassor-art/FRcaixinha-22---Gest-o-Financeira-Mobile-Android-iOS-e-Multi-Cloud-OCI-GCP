#!/usr/bin/env python3
"""Provisionamento local seguro do PRIMEIRO MASTER do aplicativo AI Studio.
Reutiliza bootstrap_master.py do mesmo repositorio; nao cria outro painel ou papel.
Nenhuma operacao ocorre sem confirmacao expressa, cluster exclusivo e schema migrado.
"""
import getpass
import os
import secrets
from urllib.parse import quote

import psycopg

EXPECTED_DIR = "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
EXPECTED_DB = "frcaixinha_aistudio_dev"
EXPECTED_USER = "frc_ai_owner"
EXPECTED_PORT = 5433


def main() -> int:
    if os.getenv("AI_STUDIO_ALLOW_MASTER_BOOTSTRAP") != "YES":
        print("BLOQUEADO: requer autorizacao AI_STUDIO_ALLOW_MASTER_BOOTSTRAP=YES.")
        return 2
    confirmation = input("Digite PROVISIONAR_MASTER_AI_STUDIO para autorizar: ").strip()
    if confirmation != "PROVISIONAR_MASTER_AI_STUDIO":
        print("Cancelado sem alteracoes.")
        return 2

    db_password = getpass.getpass("Senha do administrador PostgreSQL AI Studio: ")
    try:
        with psycopg.connect(host="127.0.0.1", port=EXPECTED_PORT,
                             dbname=EXPECTED_DB, user=EXPECTED_USER,
                             password=db_password, connect_timeout=5) as conn:
            row = conn.execute(
                "SELECT current_user,current_database(),inet_server_port(),"
                "current_setting('data_directory'),"
                "to_regclass('public.users') IS NOT NULL,"
                "to_regclass('public.credentials') IS NOT NULL,"
                "to_regclass('public.audit_events') IS NOT NULL"
            ).fetchone()
            if row != (EXPECTED_USER, EXPECTED_DB, EXPECTED_PORT, EXPECTED_DIR,
                       True, True, True):
                print("BLOQUEADO: cluster incorreto ou migracoes ausentes.")
                return 2
            if conn.execute("SELECT count(*) FROM public.users WHERE is_master").fetchone()[0] != 0:
                print("BLOQUEADO: o MASTER ja existe; nao criar outra conta.")
                return 3
    except psycopg.Error:
        print("BLOQUEADO: nao foi possivel validar o cluster exclusivo do AI Studio.")
        return 2

    print("Dados do primeiro MASTER: digite somente no seu Termux, nunca no chat.")
    email = input("E-mail: ").strip()
    name = input("Nome completo: ").strip()
    cpf = input("CPF: ").strip()
    phone = input("Telefone: ").strip()
    password = getpass.getpass("Senha do aplicativo (minimo 12 caracteres): ")
    check = getpass.getpass("Confirme a senha do aplicativo: ")
    if password != check:
        print("Senhas diferentes; cancelado.")
        return 2

    from bootstrap_master import main as existing_bootstrap

    # Variaveis apenas na memoria deste processo; nenhuma senha no historico do shell.
    temporary = {
        "DATABASE_URL": "postgresql://" + EXPECTED_USER + ":" + quote(db_password, safe="")
                        + "@127.0.0.1:5433/" + EXPECTED_DB,
        "CONFIRM_MASTER_PROVISIONING": "YES",
        "MASTER_BOOTSTRAP_SECRET": secrets.token_urlsafe(48),
        "MASTER_EMAIL": email,
        "MASTER_NAME": name,
        "MASTER_CPF": cpf,
        "MASTER_PHONE": phone,
        "MASTER_PASSWORD": password,
    }
    previous = {key: os.environ.get(key) for key in temporary}
    try:
        os.environ.update(temporary)
        try:
            existing_bootstrap()
        except SystemExit as exc:
            return int(exc.code or 0)
    finally:
        for key, old in previous.items():
            if old is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
