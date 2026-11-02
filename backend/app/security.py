"""
FRcaixinha 2.2 — Módulo de Segurança Criptográfica do Servidor
Hashing com Argon2id/Bcrypt, Tokens de Sessão Opostos e Prevenção de Força Bruta
Em conformidade estrita com o Contrato Técnico Mestre (Cláusulas 2.3, 11.2 e 16.4)
"""

import hashlib
import hmac
import os
import secrets
import time
from typing import Optional, Tuple

# Tentativa de importação das bibliotecas criptográficas contratuais
try:
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError, InvalidHashError
    _ARGON2_AVAILABLE = True
    _ph = PasswordHasher(
        time_cost=3,          # 3 iterações
        memory_cost=65536,    # 64 MB de memória (resistência a ASICs)
        parallelism=4,        # 4 threads
        hash_len=32,
        salt_len=16
    )
except ImportError:
    _ARGON2_AVAILABLE = False
    _ph = None

try:
    import bcrypt
    _BCRYPT_AVAILABLE = True
except ImportError:
    _BCRYPT_AVAILABLE = False


def hash_password_secure(password: str) -> str:
    """
    Gera hash seguro com Argon2id (padrão principal) ou bcrypt (secundário).
    REGRA ESTRITA: Recusa silenciosa de fallback para PBKDF2 ou algoritmos legados.
    Se nenhuma biblioteca estiver instalada, lança exceção imediata de configuração.
    """
    if _ARGON2_AVAILABLE and _ph is not None:
        return _ph.hash(password)
    
    if _BCRYPT_AVAILABLE:
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    raise RuntimeError(
        "CRITICAL SECURITY CONFIGURATION ERROR: As bibliotecas criptográficas contratuais "
        "('argon2-cffi' ou 'bcrypt') não estão instaladas neste ambiente Python. "
        "O Contrato Técnico Mestre proíbe terminantemente o uso de algoritmos legados ou fallbacks desprovidos de proteção contra hardware dedicado. "
        "Instale as dependências executando: pip install -r backend/requirements.txt"
    )


def verify_password_secure(password: str, stored_hash: str) -> bool:
    """
    Verificação de senha com algoritmo contratual correspondente.
    Suporta Argon2id ($argon2id$) e bcrypt ($2a$, $2b$, $2y$).
    """
    if not stored_hash or not password:
        return False

    # Detecção de hash Argon2
    if stored_hash.startswith('$argon2'):
        if not _ARGON2_AVAILABLE or _ph is None:
            raise RuntimeError(
                "Biblioteca 'argon2-cffi' necessária para verificar credenciais Argon2id. "
                "Execute 'pip install -r backend/requirements.txt'."
            )
        try:
            return _ph.verify(stored_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
        except Exception:
            return False

    # Detecção de hash bcrypt
    if stored_hash.startswith(('$2a$', '$2b$', '$2y$')):
        if not _BCRYPT_AVAILABLE:
            raise RuntimeError(
                "Biblioteca 'bcrypt' necessária para verificar credenciais bcrypt. "
                "Execute 'pip install -r backend/requirements.txt'."
            )
        try:
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        except Exception:
            return False

    return False


def generate_session_token() -> Tuple[str, str]:
    """
    Retorna (raw_token, token_hash_sha256).
    O cliente recebe o raw_token; o banco armazena apenas o hash SHA-256.
    Assim, vazamentos de banco não comprometem sessões ativas.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    return raw_token, token_hash


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode('utf-8')).hexdigest()


def auth_rate_limit_key(identifier: str) -> str:
    """HMAC do identificador de login usando segredo de ambiente, nunca email bruto no SQL."""
    secret = os.getenv('AUTH_RATE_LIMIT_HMAC_KEY', '')
    if len(secret.encode('utf-8')) < 32:
        raise ValueError('AUTH_RATE_LIMIT_HMAC_KEY ausente ou curta')
    normalized = identifier.strip().lower()
    if not normalized or len(normalized)>255:
        raise ValueError('identificador de login invalido')
    return hmac.new(secret.encode('utf-8'),normalized.encode('utf-8'),hashlib.sha256).hexdigest()


# ------------------------------------------------------------------------------
# Rate Limiting em Memória (Contenção Local de Força Bruta)
# LIMITAÇÃO OPERACIONAL NOTIFICADA:
# Este rate limiting opera exclusivamente em processo único (in-memory).
# Em ambientes com múltiplos workers Uvicorn ou múltiplas réplicas de contêineres,
# as tentativas não são sincronizadas entre nós. Para produção horizontal, é
# OBRIGATÓRIA a integração com um armazenamento compartilhado (ex: Redis com sliding-window
# ou PostgreSQL advisory lock).
# ------------------------------------------------------------------------------
_login_rate_limits = {}

def check_rate_limit(identifier: str, max_attempts: int = 5, lock_seconds: int = 60) -> Tuple[bool, Optional[int]]:
    """
    Verifica se o identificador excedeu o limite de tentativas.
    Retorna (is_blocked, remaining_seconds).
    """
    now = time.time()
    record = _login_rate_limits.get(identifier)

    if record:
        attempts, locked_until = record
        if locked_until and now < locked_until:
            return True, int(locked_until - now)
        if locked_until and now >= locked_until:
            _login_rate_limits[identifier] = (1, None)
            return False, None
    return False, None


def record_failed_attempt(identifier: str, max_attempts: int = 5, lock_seconds: int = 60) -> int:
    """
    Registra uma falha de autenticação. Bloqueia se atingir max_attempts.
    """
    now = time.time()
    record = _login_rate_limits.get(identifier)

    if record:
        attempts, locked_until = record
        attempts += 1
        if attempts >= max_attempts:
            locked_until = now + lock_seconds
            _login_rate_limits[identifier] = (attempts, locked_until)
            return attempts
        _login_rate_limits[identifier] = (attempts, None)
        return attempts
    else:
        _login_rate_limits[identifier] = (1, None)
        return 1


def clear_rate_limit(identifier: str):
    """Limpa tentativas após login bem-sucedido."""
    _login_rate_limits.pop(identifier, None)
