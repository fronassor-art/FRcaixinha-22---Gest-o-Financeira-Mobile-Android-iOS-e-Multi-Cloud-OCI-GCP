#!/usr/bin/env python3
"""Wizard local (Termux) para 1 caixinha + Admin + Membro; sem dados no Git."""
import getpass
import os
from pathlib import Path
import subprocess
import sys

import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.aistudio_onboarding import OnboardingDenied, onboard_tenant_with_roles

ORIGIN = ("https://github.com/fronassor-art/"
          "FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git")
BRANCH = "atualizacao-ai-studio-9b46a63187"


def git(*args):
    return subprocess.check_output(
        ["git", "-C", str(ROOT), *args], text=True, stderr=subprocess.DEVNULL
    ).strip()


def collect_account(label, master_email, master_password):
    print("\n" + label + " — selecione NOVA, EXISTENTE ou MASTER.")
    print("MASTER reutiliza o mesmo e-mail, senha e identidade ja autorizados.")
    mode = input("Digite NOVA, EXISTENTE ou MASTER: ").strip().upper()
    if mode == "MASTER":
        return {"mode": "existing", "email": master_email,
                "password": master_password}
    if mode not in ("NOVA", "EXISTENTE"):
        raise OnboardingDenied("Tipo de conta invalido")
    email = input("E-mail pessoal da conta: ").strip()
    if mode == "EXISTENTE":
        return {"mode": "existing", "email": email,
                "password": getpass.getpass("Senha ATUAL dessa identidade: ")}
    return {
        "mode": "new", "email": email,
        "full_name": input("Nome completo: ").strip(),
        "cpf": getpass.getpass("CPF (sem exibir): "),
        "phone": input("Telefone: ").strip(),
        "password": new_password(),
    }


def new_password():
    password = getpass.getpass("Nova senha do aplicativo (min. 12): ")
    again = getpass.getpass("Confirme a nova senha: ")
    if password != again:
        raise OnboardingDenied("Senhas divergentes; nada gravado")
    return password


def main():
    if os.getenv("AI_STUDIO_ALLOW_ROLE_ONBOARDING") != "YES":
        print("BLOQUEADO: falta AI_STUDIO_ALLOW_ROLE_ONBOARDING=YES")
        return 2
    try:
        if (ROOT != Path.home() / "frcaixinha-aistudio-mobile"
                or git("remote", "get-url", "origin") != ORIGIN
                or git("branch", "--show-current") != BRANCH
                or git("status", "--porcelain")):
            print("BLOQUEADO: repositorio, branch ou arvore divergente")
            return 2
    except (OSError, subprocess.CalledProcessError):
        print("BLOQUEADO: nao foi possivel validar o Git")
        return 2
    if os.getenv("ENVIRONMENT") == "production":
        print("BLOQUEADO: ferramenta apenas de homologacao local")
        return 2

    print("AI STUDIO: homologacao local, sem convites/e-mails e sem operacoes financeiras.")
    try:
        master_email = input("E-mail do Master existente: ").strip()
        master_password = getpass.getpass("Senha atual do Master (autorizacao): ")
        tenant_name = input("Nome da caixinha de homologacao: ").strip()
        party = getpass.getpass("Identificador do contratante (sigiloso): ")
        admin = collect_account("Administrador de Caixinha",
                                master_email, master_password)
        member = collect_account("Membro", master_email, master_password)
        owner_input = input(
            "Marcar como caixinha INAUGURAL do proprietario? Digite SIM ou NAO: "
        ).strip().upper()
        if owner_input not in ("SIM", "NAO"):
            raise OnboardingDenied("Responda SIM ou NAO para caixinha inaugural")
        owner_box = owner_input == "SIM"
        if owner_box and not (
            admin["email"].strip().lower() == master_email.strip().lower()
            and member["email"].strip().lower() == master_email.strip().lower()
        ):
            raise OnboardingDenied(
                "Caixinha inaugural exige o Master como Admin e Membro"
            )
        print("\nREVISAO: sera criada UMA caixinha e DOIS vinculos (Admin e Membro).")
        if owner_box:
            print("CAIXINHA INAUGURAL: SIM; mesma identidade nos tres papeis.")
        print("Se informou NOVA, uma nova identidade sera criada; EXISTENTE preserva a identidade.")
        if input("Digite CADASTRAR_ADMIN_E_MEMBRO_AI_STUDIO para confirmar: ").strip() != (
                "CADASTRAR_ADMIN_E_MEMBRO_AI_STUDIO"):
            print("CANCELADO: nenhum registro criado.")
            return 2
        owner_password = getpass.getpass("Senha SQL frc_ai_owner: ")
        with psycopg.connect(host="127.0.0.1", port=5433,
                             dbname="frcaixinha_aistudio_dev", user="frc_ai_owner",
                             password=owner_password, connect_timeout=5,
                             autocommit=True) as conn:
            result = onboard_tenant_with_roles(
                conn, master_email=master_email, master_password=master_password,
                tenant_name=tenant_name, contracting_party_id=party,
                admin=admin, member=member, owner_box=owner_box,
            )
        print("CADASTRO_LOCAL_3_PERFIS=PASS")
        print("CAIXINHA_INAUGURAL=", "SIM" if result["is_owner_box"] else "NAO")
        print("IDENTIDADE_UNICA_TRES_PAPEIS=",
              "PASS" if result["is_owner_box"] and
              result["admin_id"] == result["member_id"] else "NAO_APLICAVEL")
        print("TENANT_ID=", result["tenant_id"])
        print("ADMIN_ID=", result["admin_id"])
        print("MEMBRO_ID=", result["member_id"])
        print("NENHUMA CREDENCIAL EXIBIDA; EMAILS NAO VERIFICADOS (HOMOLOGACAO).")
        return 0
    except (OnboardingDenied, psycopg.Error, EOFError, KeyboardInterrupt):
        print("\nBLOQUEADO: falha/cancelamento; nao repetir sem checar estado do banco.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
