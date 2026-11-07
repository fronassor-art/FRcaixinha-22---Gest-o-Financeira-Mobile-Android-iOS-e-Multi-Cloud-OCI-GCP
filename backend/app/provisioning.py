"""Provisionamento explícito de contas locais; nunca executado pela API pública."""
from uuid import UUID, uuid4
import re

from .security import hash_password_secure


def create_tenant_account(conn, *, email, full_name, cpf, phone, password, tenant_id, role):
    """Cria usuário, hash e vínculo numa transação; não altera usuários existentes."""
    email = email.strip().lower()
    full_name, cpf, phone = full_name.strip(), cpf.strip(), phone.strip()
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(email) > 255:
        raise ValueError("E-mail inválido")
    if not full_name or not cpf or not phone:
        raise ValueError("Nome, CPF e telefone são obrigatórios")
    if not password or len(password) < 12:
        raise ValueError("A senha deve ter pelo menos 12 caracteres")
    if role not in ("TENANT_ADMIN", "TENANT_MEMBER"):
        raise ValueError("Perfil inválido")
    tenant_id = UUID(str(tenant_id))
    # Hash antes da transação para não manter lock durante Argon2.
    password_hash = hash_password_secure(password)
    algorithm = "argon2id" if password_hash.startswith("$argon2id$") else "bcrypt"
    user_id, membership_id = uuid4(), uuid4()
    with conn.transaction():
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM tenants WHERE id = %s FOR UPDATE", (tenant_id,))
            if cur.fetchone() is None:
                raise ValueError("Caixinha não encontrada")
            cur.execute("SELECT 1 FROM users WHERE lower(email) = %s OR cpf = %s", (email, cpf))
            if cur.fetchone():
                raise ValueError("Conta ou CPF já cadastrado; não foi feita alteração")
            cur.execute(
                "INSERT INTO users (id,email,full_name,cpf,phone) VALUES (%s,%s,%s,%s,%s)",
                (user_id, email, full_name, cpf, phone),
            )
            cur.execute(
                "INSERT INTO credentials (user_id,password_hash,algorithm) VALUES (%s,%s,%s)",
                (user_id, password_hash, algorithm),
            )
            cur.execute(
                "INSERT INTO memberships (id,tenant_id,user_id,role) VALUES (%s,%s,%s,%s)",
                (membership_id, tenant_id, user_id, role),
            )
            # O comando é executado por operador de banco; não inventa identidade autenticada.
            cur.execute(
                "INSERT INTO audit_events (actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref) "
                "VALUES (NULL,'SYSTEM',%s,'LOCAL_ACCOUNT_PROVISIONED','MEMBERSHIP',%s,%s,%s)",
                (tenant_id, str(membership_id), "Provisionamento local por operador do banco", "LOCAL_OPERATOR_UNIDENTIFIED"),
            )
    return user_id, membership_id
