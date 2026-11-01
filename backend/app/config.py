"""
FRcaixinha 2.2 — Configurações do Backend FastAPI
Contrato Técnico Mestre (Cláusulas 1.2, 14.1 e 16.2)
"""

import os
from typing import List
from pydantic import BaseModel

class Settings(BaseModel):
    PROJECT_NAME: str = "FRcaixinha 2.2 — API Oficial"
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
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        os.getenv("APP_URL", ""),
        # WebView local só em homologação explícita: não habilitar em produção.
        *(["http://localhost"] if os.getenv("FRCAIXINHA_TERMUX_LOCAL_API") == "1"
          and os.getenv("ENVIRONMENT", "development") != "production" else []),
    ]
    
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
