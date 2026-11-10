#!/usr/bin/env python3
"""Ciclo e política reais, apenas no banco DEV exclusivo do AI Studio.

--plan: somente leitura; --apply: confirmação e escrita transacional.
Não cria usuários, empréstimos, pagamentos, saldos ou contas externas.
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

ROOT=Path.home()/"frcaixinha-aistudio-mobile"
REPO="https://github.com/fronassor-art/FRcaixinha-22---Gest-o-Financeira-Mobile-Android-iOS-e-Multi-Cloud-OCI-GCP.git"
BRANCH="atualizacao-ai-studio-9b46a63187"
DATA="/data/data/com.termux/files/usr/var/lib/frcaixinha_aistudio_pg18"
DB="frcaixinha_aistudio_dev"
BEGIN,END,SETTLE=date(2027,1,1),date(2027,12,31),date(2028,1,10)
RATE=Decimal("0.2000")
QUOTA=None  # No implicit amount; historical seed is permanently retired.
FINE=Decimal("10.00")
MORA=Decimal("0.006667")
ADMIN=Decimal("15.00")
MEMBER=Decimal("85.00")

def block(msg):
    raise RuntimeError("BLOQUEADO: "+msg)

def git(*args):
    return subprocess.check_output(
        ["git","-C",str(ROOT),*args],text=True).strip()

def local_guard():
    if ROOT.resolve()!=Path.cwd().resolve():
        block("clone incorreto")
    if git("branch","--show-current")!=BRANCH or git("remote","get-url","origin")!=REPO:
        block("repositório/branch diferente do AI Studio")
    if git("status","--porcelain","--untracked-files=no"):
        block("arquivos rastreados alterados")
    if os.environ.get("ENVIRONMENT")=="production":
        block("produção não permitida")
    if not Path(DATA,"PG_VERSION").is_file() or Path(DATA,"PG_VERSION").read_text().strip()!="18":
        block("cluster AI Studio PostgreSQL 18 não identificado")

def guarded_connection(password):
    return psycopg.connect(host="127.0.0.1",port=5433,dbname=DB,
        user="frc_ai_owner",password=password,connect_timeout=5,row_factory=dict_row)

def verify_connection(cur):
    cur.execute("""SELECT current_database() AS db,current_user AS usr,
       inet_server_port() AS port,current_setting('data_directory') AS dir,
       current_setting('server_version_num')::integer AS version""")
    row=cur.fetchone()
    if (row["db"],row["usr"],row["port"],row["dir"])!=(DB,"frc_ai_owner",5433,DATA) or row["version"]//10000!=18:
        block("a conexão não é com o banco AI Studio exclusivo")
    print("AI_STUDIO_CLUSTER=PASS")

def only_inaugural_tenant(cur):
    cur.execute("""SELECT DISTINCT t.id,t.display_name
      FROM public.tenants t
      JOIN public.users u ON u.id=t.admin_user_id AND u.is_master
      JOIN public.memberships a ON a.tenant_id=t.id AND a.user_id=u.id
        AND a.role='TENANT_ADMIN' AND a.status='ATIVA'
      JOIN public.memberships m ON m.tenant_id=t.id AND m.user_id=u.id
        AND m.role='TENANT_MEMBER' AND m.status='ATIVA'
      WHERE t.is_owner_box AND t.status='ATIVO' ORDER BY t.id""")
    rows=cur.fetchall()
    if len(rows)!=1:
        block("é exigida uma única caixinha inaugural com Master/Admin/Membro; encontradas "+str(len(rows)))
    return rows[0]

def inspect(cur,tenant):
    cur.execute("""SELECT id,start_date,end_date,settlement_date,status
       FROM public.cycles WHERE tenant_id=%s AND year=2027 FOR UPDATE""",(tenant,))
    cycle=cur.fetchone()
    if cycle and (cycle["start_date"],cycle["end_date"],cycle["settlement_date"],cycle["status"])!=(BEGIN,END,SETTLE,"ABERTO"):
        block("ciclo existente diferente; nenhuma alteração autorizada")
    policy=None
    if cycle:
        cur.execute("""SELECT id,monthly_interest_rate,max_installments,
           contribution_per_quota,flat_fine_amount,daily_mora_rate,
           admin_pct,member_pct,status
           FROM public.policies WHERE tenant_id=%s AND cycle_id=%s""",(tenant,cycle["id"]))
        rows=cur.fetchall()
        if len(rows)>1:
            block("há políticas anteriores; requer análise específica")
        policy=rows[0] if rows else None
        if policy and (
            policy["monthly_interest_rate"],policy["max_installments"],
            policy["contribution_per_quota"],policy["flat_fine_amount"],
            policy["daily_mora_rate"],policy["admin_pct"],policy["member_pct"],
            policy["status"])!=(RATE,6,QUOTA,FINE,MORA,ADMIN,MEMBER,"ACTIVE"):
            block("política existente diferente; nenhuma alteração")
    return cycle,policy

def main():
    parser=argparse.ArgumentParser()
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--plan",action="store_true")
    modes.add_argument("--apply",action="store_true")
    args=parser.parse_args()
    # Development-only seed retired: no automatic price/cycle creation.
    block('SEED_LEGADO_DESATIVADO: use abertura autenticada e escolha explicita acima do minimo de R$ 150')
    local_guard()
    pwd=getpass.getpass("Senha SQL AI Studio (oculta): ")
    if not pwd: block("senha vazia")
    with guarded_connection(pwd) as conn:
      del pwd
      with conn.cursor() as cur:
        verify_connection(cur)
        tenant=only_inaugural_tenant(cur)
        cycle,policy=inspect(cur,tenant["id"])
        print("CAIXINHA_HOMOLOGACAO="+tenant["display_name"])
        print("CICLO=2027-01-01 a 2027-12-31; liquidacao=2028-01-10")
        print("POLITICA_TESTE=20% a.m.; 6 parcelas; cota R$ 100; multa R$ 10; mora 0,006667/dia; 15/85")
        print("CICLO="+("EXISTENTE_COMPATIVEL" if cycle else "NOVO"))
        print("POLITICA="+("EXISTENTE_COMPATIVEL" if policy else "NOVA"))
        if args.plan:
            conn.rollback()
            print("HOMOLOG_PREVIEW=PASS; ESCRITAS=0")
            return
        if not cycle or not policy:
            block("script legado R$100 proibido de abrir novos ciclos; exige valor explícito do administrador")
        if input("Confirme somente dados financeiros de TESTE digitando HOMOLOGAR_AI_STUDIO_2027: ").strip()!="HOMOLOGAR_AI_STUDIO_2027":
            conn.rollback()
            block("sem confirmação")
        if not cycle:
            cur.execute("""INSERT INTO public.cycles
              (tenant_id,year,start_date,end_date,settlement_date,status)
              VALUES(%s,2027,%s,%s,%s,'ABERTO') RETURNING id""",
              (tenant["id"],BEGIN,END,SETTLE))
            cycle=cur.fetchone()
        if not policy:
            cur.execute("""INSERT INTO public.policies
               (tenant_id,cycle_id,version,monthly_interest_rate,max_installments,
                contribution_per_quota,flat_fine_amount,daily_mora_rate,
                admin_pct,member_pct,status)
               VALUES(%s,%s,1,%s,6,%s,%s,%s,%s,%s,'ACTIVE')""",
               (tenant["id"],cycle["id"],RATE,QUOTA,FINE,MORA,ADMIN,MEMBER))
        cur.execute("""SELECT
          (SELECT count(*) FROM public.cycles WHERE tenant_id=%s AND year=2027 AND status='ABERTO') AS c,
          (SELECT count(*) FROM public.policies WHERE tenant_id=%s AND cycle_id=%s AND status='ACTIVE') AS p""",
          (tenant["id"],tenant["id"],cycle["id"]))
        counts=cur.fetchone()
        if counts["c"]!=1 or counts["p"]!=1:
            block("verificação final falhou; rollback")
      conn.commit()
    print("HOMOLOG_PRICE_SEED=PASS; CICLOS=1; POLITICAS=1")
    print("USUARIOS=0; EMPRESTIMOS=0; PAGAMENTOS=0; MOVIMENTACOES=0 (criados)")
    print("TESTE_NO_APK=Entre como Membro e simule R$ 500 em 5 parcelas")

if __name__=="__main__":
    try: main()
    except (RuntimeError,psycopg.Error,EOFError,KeyboardInterrupt) as exc:
        print(str(exc) if isinstance(exc,RuntimeError) else "BLOQUEADO: operação não concluída; nenhum sucesso confirmado")
        sys.exit(2)
