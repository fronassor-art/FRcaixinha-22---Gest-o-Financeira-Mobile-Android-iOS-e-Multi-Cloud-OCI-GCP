"""
FR Finance — configuracoes da aplicativo FR Finance
Referencias: Caderno Mestre e Contrato Tecnico Mestre FR Finance, exclusivos desta frente.
"""

import ipaddress
import os
import re
from typing import List, Mapping
from urllib.parse import urlsplit
from pydantic import BaseModel


# M40960: restrict public origins to unambiguous ASCII DNS authorities.
_PUBLIC_DNS_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


def safe_public_https_origin(value: str) -> str | None:
    """Allow only a public HTTPS origin, not a URL with paths or credentials.

    Static syntax gate; does NOT prove domain ownership, DNS, TLS deployment
    or a production-ready server. Invalid values fail closed.
    """
    if (type(value) is not str or not 8 < len(value) <= 253
            or not value.isascii() or not value.lower().startswith("https://")
            or any(ord(ch) <= 32 or ord(ch) == 127 for ch in value)
            or "?" in value or "#" in value or "\\" in value):
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme != "https" or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")
            or port not in (None, 443) or not host or "." not in host
            or any(ch.isspace() for ch in host)
            or host.endswith((".localhost", ".local", ".invalid", ".test",
                              ".example", ".internal"))):
        return None
    if host in {"localhost", "127.0.0.1", "::1"}:
        return None
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return None
    labels = host.split(".")
    if (any(not _PUBLIC_DNS_LABEL.fullmatch(label) for label in labels)
            or not labels[-1][0].isalpha()
            or parsed.netloc.lower() not in (host, host + ":443")):
        return None
    # A numeric final label can make browsers interpret a DNS-looking
    # authority as IPv4, including octal, hexadecimal and shortened forms.
    return "https://" + host


def cors_origins_for(env: Mapping[str, str]) -> list[str]:
    """Never allow a loopback/browser origin to access a production API."""
    public = safe_public_https_origin(env.get("APP_URL", ""))
    if env.get("ENVIRONMENT") == "production":
        return [public] if public else []
    allowed = ["http://localhost:3000", "http://localhost:8080"]
    if public:
        allowed.append(public)
    if (env.get("FRCAIXINHA_TERMUX_LOCAL_API") == "1"
            and env.get("ENVIRONMENT", "development") != "production"):
        allowed.append("http://localhost")
    return allowed

class Settings(BaseModel):
    PROJECT_NAME: str = "FR Finance — API de homologação"
    VERSION: str = "2.2.0"
    API_V1_STR: str = "/api/v1"
    
    # Conexão com banco relacional seguro (PostgreSQL)
    # Por padrão em dev, se não informada, mantém a aplicação em modo BLOCKED informativo
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    
    # Segredo do servidor para assinatura de sessões e tokens (HMAC / JWT)
    # Deve ser injetado por variável de ambiente segura no ambiente de execução
    SECRET_KEY: str = os.getenv("AUTH_SECRET", "")
    
    # Algoritmo de Hashing de Senhas (Argon2id ou Bcrypt com salt)
    PASSWORD_HASH_ALGO: str = "argon2id"
    
    # TTL da Sessão: 15 minutos (900 segundos) de inatividade máxima
    SESSION_EXPIRE_SECONDS: int = 900
    
    # Configuração de Cookies de Sessão Seguros
    SESSION_COOKIE_NAME: str = "frcaixinha_session"
    COOKIE_SECURE: bool = os.getenv("ENVIRONMENT", "development") == "production"
    COOKIE_SAMESITE: str = "lax"
    
    # CORS: produção aceita apenas a origem pública HTTPS autorizada.
    BACKEND_CORS_ORIGINS: List[str] = cors_origins_for(os.environ)

    # Provedor de envio de e-mails para recuperação de senha (SMTP / SendGrid)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    
    @property
    def is_database_configured(self) -> bool:
        return bool(self.DATABASE_URL and self.DATABASE_URL.startswith("postgres"))
    
    @property
    def is_email_provider_configured(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)

settings = Settings()
