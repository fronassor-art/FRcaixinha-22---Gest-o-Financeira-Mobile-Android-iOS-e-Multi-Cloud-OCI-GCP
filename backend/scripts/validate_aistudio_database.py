"""Proteção local contra conexão acidental ao PostgreSQL do outro projeto."""
import os
import sys
from urllib.parse import urlsplit

PROJECT_DB = "frcaixinha_aistudio_dev"
PROJECT_PORT = 5433
PROJECT_USERS = {"DATABASE_URL": "frc_ai_app", "AUTH_DATABASE_URL": "frc_ai_auth",
                 "AUTH_VERIFIER_DATABASE_URL": "frc_ai_verifier"}


def check() -> int:
    urls = {name: os.getenv(name, "") for name in PROJECT_USERS}
    if not any(urls.values()):
        print("AI_STUDIO_DATABASE=NOT_CONFIGURED (FastAPI health apenas; autenticação bloqueada)")
        return 0
    if not all(urls.values()):
        print("BLOQUEADO: faltam as tres conexoes segregadas do AI Studio.", file=sys.stderr)
        return 2

    for key, expected_user in PROJECT_USERS.items():
        try:
            parsed = urlsplit(urls[key])
            valid = (
                parsed.scheme in ("postgres", "postgresql")
                and parsed.hostname == "127.0.0.1"
                and parsed.port == PROJECT_PORT
                and parsed.path == f"/{PROJECT_DB}"
                and parsed.username == expected_user
                and bool(parsed.password)
                # No PGOPTIONS/sslmode/service override via URL query.
                # The original localhost DB and its segregated roles are fixed.
                and parsed.query == ""
                and parsed.fragment == ""
            )
        except ValueError:
            valid = False
        if not valid:
            print(
                f"BLOQUEADO: {key} deve apontar exclusivamente ao PostgreSQL "
                f"AI Studio (127.0.0.1:{PROJECT_PORT}/{PROJECT_DB}, "
                f"papel {expected_user}). Sem acesso ao banco antigo.",
                file=sys.stderr,
            )
            return 2

    print("AI_STUDIO_DATABASE=ISOLATED_URLS_VALIDATED (conexão real ainda não testada)")
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
