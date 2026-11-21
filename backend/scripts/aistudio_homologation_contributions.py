#!/usr/bin/env python3
"""Dados REAIS de leitura de cotas e contribuições, exclusivamente DEV AI Studio.

--plan: SELECT + rollback; --apply: confirma e insere 1 cota, 12 pendências.
Nenhum pagamento, baixa, Pix, saldo, crédito, empréstimo ou usuário.
"""
import argparse
from datetime import date
from decimal import Decimal
import getpass
import os
from pathlib import Path
import subprocess
import sys

import psycopg
from psycopg.rows import dict_row

ROOT = Path.home() / "frcaixinha-aistudio-mobile"
REPO = "https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git"
BRANCH = "atualizacao-ai-studio-9b46a63187"
DATA = "/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
DB = "frcaixinha_aistudio_dev"
YEAR = 2027

def stop(message):
    raise RuntimeError("BLOQUEADO: " + message)

def command(*parts):
    return subprocess.check_output(["git","-C",str(ROOT),*parts],text=True).strip()

def verify_local():
    if Path.cwd().resolve() != ROOT.resolve():
        stop("execute somente no clone do AI Studio")
    if command("branch","--show-current") != BRANCH:
        stop("branch não autorizada")
    if command("remote","get-url","origin") != REPO:
        stop("origin não autorizado")
    if command("status","--porcelain","--untracked-files=no"):
        stop("alterações locais rastreadas")
    if os.getenv("ENVIRONMENT") == "production":
        stop("ambiente de produção bloqueado")
    version=Path(DATA,"PG_VERSION")
    if not version.is_file() or version.read_text().strip() != "18":
        stop("diretório do cluster AI Studio PostgreSQL 18 ausente")

def check_database(cur):
    cur.execute("""SELECT current_database() db, current_user rol,
        inet_server_port() port, current_setting('data_directory') pgdata,
        current_setting('server_version_num')::integer version""")
    row=cur.fetchone()
    if (row["db"],row["rol"],row["port"],row["pgdata"]) != (DB,"frc_ai_owner",5433,DATA) or row["version"] // 10000 != 18:
        stop("banco ou cluster diverge do AI Studio")
    print("AI_STUDIO_CLUSTER=PASS")

def find_inaugural(cur):
    cur.execute("""SELECT DISTINCT t.id,t.display_name,
           member.id AS membership_id
        FROM public.tenants t
        JOIN public.users u ON u.id=t.admin_user_id AND u.is_master
        JOIN public.memberships admin ON admin.user_id=u.id
           AND admin.tenant_id=t.id AND admin.role='TENANT_ADMIN'
           AND admin.status='ATIVA'
        JOIN public.memberships member ON member.user_id=u.id
           AND member.tenant_id=t.id AND member.role='TENANT_MEMBER'
           AND member.status='ATIVA'
        WHERE t.status='ATIVO' AND t.is_owner_box
        ORDER BY t.id""")
    found=cur.fetchall()
    if len(found)!=1:
        stop("exige uma caixinha inaugural com Admin/Membro ativos; encontradas "+str(len(found)))
    return found[0]

def inspect(cur,tenant):
    cur.execute("""SELECT c.id AS cycle_id,p.contribution_per_quota
        FROM public.cycles c JOIN public.policies p
          ON p.tenant_id=c.tenant_id AND p.cycle_id=c.id
        WHERE c.tenant_id=%s AND c.year=%s AND c.status='ABERTO'
          AND p.status='ACTIVE'""",(tenant["id"],YEAR))
    policies=cur.fetchall()
    if len(policies)!=1:
        stop("é necessário um único ciclo 2027 ABERTO com política ACTIVE")
    policy=policies[0]
    amount=policy["contribution_per_quota"]
    if not isinstance(amount,Decimal) or amount<Decimal('150.00') or amount.as_tuple().exponent < -2:
        stop("valor por cota não atende à precisão monetária")
    cur.execute("""SELECT id,membership_id,value_brl,status FROM public.quotas
                   WHERE tenant_id=%s AND quota_number=1""",(tenant["id"],))
    quotas=cur.fetchall()
    if len(quotas)>1:
        stop("cota de referência duplicada")
    quota=quotas[0] if quotas else None
    if quota and (quota["membership_id"]!=tenant["membership_id"] or
                  quota["status"]!="ATIVA" or quota["value_brl"]!=amount):
        stop("cota existente não corresponde ao teste; nada será sobrescrito")
    cur.execute("""SELECT competence,cycle_id,due_date,amount_due,amount_paid,
           payment_status,due_status,paid_at
        FROM public.contributions
        WHERE tenant_id=%s AND membership_id=%s AND competence LIKE '2027-%%'
        ORDER BY competence""",(tenant["id"],tenant["membership_id"]))
    rows=cur.fetchall()
    expected={f"{YEAR}-{m:02d}":date(YEAR,m,10) for m in range(1,13)}
    if rows and (
        len(rows)!=12 or set(r["competence"] for r in rows)!=set(expected) or
        any(r["cycle_id"]!=policy["cycle_id"] or
            r["due_date"]!=expected[r["competence"]] or
            r["amount_due"]!=amount or r["amount_paid"]!=Decimal("0") or
            r["payment_status"]!="PENDENTE" or r["due_status"]!="NO_PRAZO" or
            r["paid_at"] is not None for r in rows)
    ):
        stop("contribuições já existentes divergentes; auditoria necessária")
    return policy,quota,rows,amount

def money_counts(cur,tenant_id):
    cur.execute("""SELECT
        (SELECT count(*) FROM public.pix_payment_intents WHERE tenant_id=%s) pix,
        (SELECT count(*) FROM public.ledger_transactions WHERE tenant_id=%s) ledger,
        (SELECT count(*) FROM public.loans WHERE tenant_id=%s) loans
    """,(tenant_id,tenant_id,tenant_id))
    return cur.fetchone()

def run():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan",action="store_true")
    mode.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    verify_local()
    password=getpass.getpass("Senha técnica AI Studio (oculta): ")
    if not password: stop("senha não informada")
    with psycopg.connect(host="127.0.0.1",port=5433,dbname=DB,
        user="frc_ai_owner",password=password,connect_timeout=5,
        row_factory=dict_row) as conn:
      del password
      with conn.cursor() as cur:
        if args.plan:
            cur.execute("SET TRANSACTION READ ONLY")
        else:
            cur.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
        check_database(cur)
        tenant=find_inaugural(cur)
        policy,quota,rows,amount=inspect(cur,tenant)
        before=money_counts(cur,tenant["id"])
        print("CAIXINHA_HOMOLOGACAO="+tenant["display_name"])
        print(f"COTAS_TESTE={'EXISTENTE' if quota else 'CRIAR_1'}")
        print(f"CONTRIBUICOES_TESTE={'EXISTENTES_12' if rows else 'CRIAR_12_PENDENTES'}")
        print(f"VALOR_COTA_TESTE=R$ {amount:.2f}")
        print("COMPETENCIAS_TESTE=2027-01 a 2027-12; vencimentos no dia 10")
        print("BAIXAS_E_PAGAMENTOS=PROIBIDOS")
        if args.plan:
            conn.rollback()
            print("HOMOLOG_COTAS_PLANO=PASS; ESCRITAS=0")
            return
        confirm=input("Para gravar APENAS dados PENDENTES de teste, digite CRIAR_COTAS_TESTE_AI_STUDIO: ").strip()
        if confirm!="CRIAR_COTAS_TESTE_AI_STUDIO":
            conn.rollback()
            stop("confirmação não recebida; sem alteração")
        if not quota:
            cur.execute("""INSERT INTO public.quotas(tenant_id,membership_id,quota_number,value_brl,status)
                VALUES(%s,%s,1,%s,'ATIVA') RETURNING id""",
                (tenant["id"],tenant["membership_id"],amount))
            quota=cur.fetchone()
        if not rows:
            for month in range(1,13):
                competence=f"{YEAR}-{month:02d}"
                cur.execute("""INSERT INTO public.contributions(
                  tenant_id,cycle_id,membership_id,competence,due_date,
                  amount_due,amount_paid,payment_status,due_status)
                  VALUES(%s,%s,%s,%s,%s,%s,0,'PENDENTE','NO_PRAZO')""",
                  (tenant["id"],policy["cycle_id"],tenant["membership_id"],
                   competence,date(YEAR,month,10),amount))
        after=money_counts(cur,tenant["id"])
        if before!=after:
            stop("movimentações financeiras alteradas; rollback")
        _,_,verified,_=inspect(cur,tenant)
        if len(verified)!=12:
            stop("contagem final não confere; rollback")
      conn.commit()
    print("HOMOLOG_COTAS_CONTRIBUICOES=PASS; COTAS=1; PENDENTES=12")
    print("PAGAMENTOS_CRIADOS=0; LANCAMENTOS_CRIADOS=0; EMPRESTIMOS_CRIADOS=0")

if __name__=="__main__":
    try: run()
    except (RuntimeError,psycopg.Error,EOFError,KeyboardInterrupt) as err:
        print(str(err) if isinstance(err,RuntimeError) else
              "BLOQUEADO: operação não concluída; nenhuma gravação confirmada")
        sys.exit(2)
