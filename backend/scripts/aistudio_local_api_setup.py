#!/usr/bin/env python3
"""Habilita role verifier e configura API de homologacao EXCLUSIVA do AI Studio.

Nunca cria Master/usuario humano, licencia, Pix, pagamentos ou tenant.
Solicita senhas via getpass; arquivo de ambiente fica fora do Git (0600).
"""
import getpass
import os
from pathlib import Path
import secrets
import shlex
import sys
from urllib.parse import quote

import psycopg
from psycopg import sql

DB = "frcaixinha_aistudio_dev"
HOST = "127.0.0.1"
PORT = 5433
OWNER = "frc_ai_owner"
APP = "frc_ai_app"
AUTH = "frc_ai_auth"
VERIFIER = "frc_ai_verifier"
CLUSTER = "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
CONFIG = Path.home() / ".config" / "frcaixinha-aistudio-mobile" / "api.env"
EXPECTED_ORIGIN = ("https://github.com/fronassor-art/"
    "FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git")


def deny(reason):
    print("BLOQUEADO: " + reason, file=sys.stderr)
    return 2


def conn_as(username, password):
    return psycopg.connect(host=HOST,port=PORT,dbname=DB,user=username,
                           password=password,connect_timeout=5)


def dsn(username, password):
    return f"postgresql://{username}:{quote(password, safe='')}@{HOST}:{PORT}/{DB}"


def write_env_exclusively(env):
    """Criacao exclusiva com O_EXCL: funciona no Android mesmo sem os.link."""
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if CONFIG.parent.is_symlink():
        raise ValueError("pasta de configuracao nao pode ser symlink")
    CONFIG.parent.chmod(0o700)
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            os.fchmod(output.fileno(), 0o600)
            for key, value in env.items():
                output.write(f"{key}={shlex.quote(value)}\n")
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        # Exclusivo: so apaga o arquivo criado por esta chamada.
        CONFIG.unlink(missing_ok=True)
        raise


def main():
    if os.getenv("AI_STUDIO_LOCAL_API_SETUP") != "YES":
        return deny("AI_STUDIO_LOCAL_API_SETUP=YES necessario")
    import subprocess
    root=Path(__file__).resolve().parents[2]
    def git(*args):
        return subprocess.run(["git","-C",str(root),*args],capture_output=True,
                              text=True,check=True).stdout.strip()
    try:
        if (root != Path.home()/"frcaixinha-aistudio-mobile"
            or git("remote","get-url","origin") != EXPECTED_ORIGIN
            or git("branch","--show-current") != "atualizacao-ai-studio-9b46a63187"
            or git("status","--porcelain")):
            return deny("repo, branch ou arvore local incorretos")
    except (OSError,subprocess.CalledProcessError):
        return deny("nao foi possivel validar Git")

    if CONFIG.exists() or CONFIG.is_symlink() or CONFIG.parent.is_symlink():
        return deny("api.env ja existe ou symlink; nunca sobrescrever")
    recovery = os.getenv("AI_STUDIO_LOCAL_API_RECOVER") == "YES"
    phrase = ("RECUPERAR_VERIFICADOR_AI_STUDIO" if recovery
              else "CONFIGURAR_VERIFICADOR_AI_STUDIO")
    confirmation = input(f"Digite {phrase}: ").strip()
    if confirmation != phrase:
        return deny("sem confirmacao")

    owner_password=getpass.getpass("Senha PostgreSQL frc_ai_owner: ")
    app_password=getpass.getpass("Senha existente frc_ai_app: ")
    auth_password=getpass.getpass("Senha existente frc_ai_auth: ")
    if min(map(len,(owner_password,app_password,auth_password)))<12:
        return deny("senha tecnica com menos de 12 caracteres; revisar sem enviar no chat")

    try:
        # Todas as conexoes e permissoes existentes verificadas antes do DDL.
        with conn_as(OWNER,owner_password) as admin:
            identity=admin.execute("SELECT current_user,current_database(),inet_server_port(),"
                                   "current_setting('data_directory')").fetchone()
            if identity!=(OWNER,DB,PORT,CLUSTER):
                return deny("PostgreSQL nao corresponde ao cluster exclusivo AI Studio")
            schema=admin.execute(
                "SELECT to_regclass('public.users') IS NOT NULL,"
                "to_regclass('public.sessions') IS NOT NULL,"
                "to_regclass('public.auth_login_proofs') IS NOT NULL,"
                "to_regclass('public.auth_login_rate_limits') IS NOT NULL,"
                "pg_has_role(%s,'frcaixinha_app_role','member'),"
                "pg_has_role(%s,'frcaixinha_auth_role','member')",
                (APP,AUTH)).fetchone()
            if not all(schema):
                return deny("schema 001-027 ou grants nao preparados")
            role_attrs = admin.execute(
                "SELECT rolcanlogin,rolsuper,rolbypassrls,rolcreatedb,"
                "rolcreaterole,rolreplication FROM pg_roles WHERE rolname=%s",
                (VERIFIER,)).fetchone()
            if role_attrs is not None and not recovery:
                return deny("verificador existente; nao repetir setup; use recuperação explícita")
            if role_attrs is None and recovery:
                return deny("recuperacao exige role verifier existente e api.env ausente")
            if recovery and role_attrs != (True,False,False,False,False,False):
                return deny("verificador tem atributos inesperados; recuperacao negada")

            for role,password in ((APP,app_password),(AUTH,auth_password)):
                with conn_as(role,password) as check:
                    info=check.execute(
                        "SELECT current_user,(SELECT rolsuper OR rolbypassrls "
                        "FROM pg_roles WHERE rolname=current_user)").fetchone()
                    if info!=(role,False):
                        return deny("role de API com privilegio incorreto")

            verifier_password=secrets.token_urlsafe(48)
            with admin.transaction():
                if recovery:
                    # A senha antiga aleatoria se perdeu antes de escrever api.env.
                    # Verificar isolamento da role antes de qualquer ALTER ROLE.
                    member = admin.execute(
                        "SELECT pg_has_role(%s,'frcaixinha_verifier_role','member')",
                        (VERIFIER,)).fetchone()[0]
                    if not member:
                        raise ValueError("papel verifier existente sem membership esperado")
                else:
                    admin.execute(sql.SQL(
                        "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOBYPASSRLS "
                        "NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD {}"
                    ).format(sql.Identifier(VERIFIER),sql.Literal(verifier_password)))
                    admin.execute(sql.SQL("GRANT frcaixinha_verifier_role TO {}").format(
                        sql.Identifier(VERIFIER)))
                    admin.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                        sql.Identifier(DB),sql.Identifier(VERIFIER)))
                can=admin.execute(
                    "SELECT has_column_privilege(%s,'public.credentials','password_hash','SELECT'),"
                    "has_table_privilege(%s,'public.sessions','INSERT'),"
                    "has_function_privilege(%s,"
                    "'public.auth_issue_pending_session(uuid,text,text)','EXECUTE')",
                    (VERIFIER,VERIFIER,VERIFIER)).fetchone()
                if can != (True,False,False):
                    raise ValueError("verificador nao segregado")
                if recovery:
                    # Atualiza somente a credencial tecnica existente e aprovada.
                    admin.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                        sql.Identifier(VERIFIER), sql.Literal(verifier_password)))

        with conn_as(VERIFIER,verifier_password) as check:
            if check.execute("SELECT current_user").fetchone()[0] != VERIFIER:
                return deny("verificador nao autenticou")

        env = {
            "ENVIRONMENT": "homologation",
            "FRCAIXINHA_TEST_AUTH": "1",
            "FRCAIXINHA_TERMUX_LOCAL_API": "1",
            "DATABASE_URL": dsn(APP,app_password),
            "AUTH_DATABASE_URL": dsn(AUTH,auth_password),
            "AUTH_VERIFIER_DATABASE_URL": dsn(VERIFIER,verifier_password),
            "AUTH_RATE_LIMIT_HMAC_KEY": secrets.token_urlsafe(48),
            "AUTH_SECRET": secrets.token_urlsafe(48),
        }
        # Nao sobrescreve nenhum arquivo existente. O_EXCL impede race/symlink.
        write_env_exclusively(env)
        print("VERIFIER=ISOLATED; API_ENV=CREATED_0600; nenhum segredo exibido.")
        if recovery:
            print("VERIFIER_RECOVERY=PASS; senha anterior invalidada.")
        print("Conta Master nao criada. Proximo passo: validar FastAPI readiness.")
        return 0
    except (psycopg.Error,ValueError,OSError):
        return deny("setup incompleto; revisar sem expor dados ou repetir DDL cegamente")


if __name__ == "__main__":
    raise SystemExit(main())
