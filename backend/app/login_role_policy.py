"""Seleção de perfil após senha e vínculo verificados no PostgreSQL.

Master exige seleção explícita; nunca é concedido por fallback legado.
"""
from fastapi import HTTPException


def select_login_role(*, requested_role, is_master: bool, links, requested_tenant_id=None):
    def deny():
        raise HTTPException(
            status_code=401, detail="Credenciais inválidas ou acesso indisponível."
        )

    if requested_role == "MASTER":
        if not is_master or requested_tenant_id is not None:
            deny()
        return "MASTER", None
    if requested_role in ("TENANT_ADMIN", "TENANT_MEMBER"):
        eligible = [row for row in links if row["role"] == requested_role]
        if requested_tenant_id is not None:
            eligible = [row for row in eligible
                        if str(row["tenant_id"]) == str(requested_tenant_id)]
        if not eligible:
            deny()
        return requested_role, eligible[0]["tenant_id"]

    # Um tenant indicado sem papel nao autoriza fallback implicito.
    if requested_tenant_id is not None:
        deny()

    # Fallback antigo limitado a usuários que NÃO são Master.
    if requested_role is None and not is_master and links:
        row = links[0]
        if row["role"] in ("TENANT_ADMIN", "TENANT_MEMBER"):
            return row["role"], row["tenant_id"]

    deny()
