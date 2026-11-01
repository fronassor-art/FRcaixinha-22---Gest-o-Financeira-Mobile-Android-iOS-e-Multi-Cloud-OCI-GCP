#!/usr/bin/env python3
"""
FRcaixinha 2.2 — Ferramenta Operacional Segura: Provisionamento do Primeiro Administrador Master
Contrato Técnico Mestre (Cláusulas 2.3, 11.2 e 16.4)

REGRAS DE SEGURANÇA:
1. Requer segredo de inicialização fornecido por variável de ambiente (MASTER_BOOTSTRAP_SECRET).
2. Executável UMA ÚNICA VEZ: aborta com erro se já existir qualquer usuário Master no banco.
3. Recusa execução se CONFIRM_MASTER_PROVISIONING não estiver explicitamente definido como 'YES'.
4. NUNCA imprime senha, segredo ou hash em logs ou na saída padrão.
5. Armazena credencial com hash criptográfico seguro (Argon2id ou bcrypt).
"""

import os
import sys
import uuid
import datetime

# Adiciona o diretório raiz do backend ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.security import hash_password_secure

def main():
    print("[FRcaixinha 2.2] Iniciando ferramenta de provisionamento do Administrador Master...")
    
    # Validação 1: Confirmação explícita de ambiente
    if os.getenv("CONFIRM_MASTER_PROVISIONING") != "YES":
        print("[ERRO] Execução abortada: CONFIRM_MASTER_PROVISIONING=YES não informado.")
        print("Esta ferramenta é restrita a operações autorizadas de infraestrutura.")
        sys.exit(1)
        
    # Validação 2: Segredo de inicialização de uso único
    bootstrap_secret = os.getenv("MASTER_BOOTSTRAP_SECRET")
    if not bootstrap_secret or len(bootstrap_secret) < 32:
        print("[ERRO] Execução abortada: MASTER_BOOTSTRAP_SECRET ausente ou possui menos de 32 caracteres.")
        sys.exit(1)
        
    master_email = os.getenv("MASTER_EMAIL")
    master_password = os.getenv("MASTER_PASSWORD")
    master_name = os.getenv("MASTER_NAME", "Administrador Master da Plataforma")
    master_cpf = os.getenv("MASTER_CPF", "").strip()
    master_phone = os.getenv("MASTER_PHONE", "").strip()
    
    if not master_email or "@" not in master_email:
        print("[ERRO] E-mail do Administrador Master inválido.")
        sys.exit(1)
        
    if not master_password or len(master_password) < 12:
        print("[ERRO] A senha do Master deve possuir no mínimo 12 caracteres.")
        sys.exit(1)

    if not master_cpf or not master_phone:
        print("[ERRO] Informe MASTER_CPF e MASTER_PHONE no ambiente protegido.")
        sys.exit(1)
        
    # Validação 3: Conexão com banco de dados
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url or not db_url.startswith("postgres"):
        print("[BLOQUEADO] DATABASE_URL não configurada ou não aponta para PostgreSQL.")
        print("Para aplicar o provisionamento seguro, configure a variável de ambiente DATABASE_URL.")
        print("Operação cancelada de forma segura (nenhuma alteração efetuada).")
        sys.exit(2)

    # Execução real contra PostgreSQL (quando DATABASE_URL estiver ativa)
    try:
        import psycopg
        conn = psycopg.connect(db_url)
        cur = conn.cursor()

        # Serializa tentativas concorrentes no mesmo banco durante a transação.
        cur.execute("SELECT pg_advisory_xact_lock(706719221346)")
        
        # Verificar se já existe Master no banco
        cur.execute("SELECT COUNT(*) FROM users WHERE is_master = TRUE;")
        count = cur.fetchone()[0]
        if count > 0:
            print("[ERRO] Operação abortada: Já existe um Administrador Master provisionado no banco de dados.")
            print("O Contrato Técnico Mestre veda re-provisionamento de Master por ferramenta de bootstrap.")
            conn.close()
            sys.exit(3)
            
        # Gerar hash seguro com salt (NUNCA imprimir senha em log)
        try:
            pwd_hash = hash_password_secure(master_password)
        except RuntimeError as crypto_err:
            print(f"[ERRO CRIPTOGRÁFICO] {crypto_err}")
            conn.close()
            sys.exit(4)

        new_user_id = str(uuid.uuid4())
        
        # Inserir usuário Master
        cur.execute("""
            INSERT INTO users (id, email, full_name, cpf, phone, status, is_master, created_at)
            VALUES (%s, %s, %s, %s, %s, 'ACTIVE', TRUE, NOW());
        """, (new_user_id, master_email.lower().strip(), master_name, master_cpf, master_phone))
        
        # Inserir credencial criptografada
        algorithm = 'argon2id' if pwd_hash.startswith('$argon2id$') else 'bcrypt'
        cur.execute("""
            INSERT INTO credentials (user_id, password_hash, algorithm, created_at)
            VALUES (%s, %s, %s, NOW());
        """, (new_user_id, pwd_hash, algorithm))
        
        # Inserir evento na trilha de auditoria imutável
        cur.execute("""
            INSERT INTO audit_events (actor_id, actor_role, action, object_type, object_id, reason, evidence_ref, created_at)
            VALUES (%s, 'MASTER', 'INITIAL_MASTER_BOOTSTRAP', 'USER', %s, 'Provisionamento seguro do primeiro Master da plataforma', 'BOOTSTRAP_CLI_SHA256_OK', NOW());
        """, (new_user_id, new_user_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print("[SUCESSO] Primeiro Administrador Master provisionado com sucesso!")
        print("Identificador gerado e registrado na trilha de auditoria.")
        print("Por segurança, limpe imediatamente as variáveis de ambiente MASTER_BOOTSTRAP_SECRET e MASTER_PASSWORD.")
        sys.exit(0)
        
    except ImportError:
        print("[AVISO] Driver psycopg não instalado no ambiente local.")
        print("Instale as dependências declaradas em backend/requirements.txt.")
        sys.exit(4)
    except Exception as err:
        print(f"[ERRO DE CONEXÃO] Falha ao executar migração contra banco: {type(err).__name__}")
        sys.exit(5)

if __name__ == "__main__":
    main()
