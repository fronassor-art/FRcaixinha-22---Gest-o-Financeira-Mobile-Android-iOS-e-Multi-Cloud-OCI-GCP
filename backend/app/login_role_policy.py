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
        if not eligible or any(row['tenant_id'] is None for row in eligible):
            deny()
        # Nunca escolher silenciosamente o primeiro tenant deste papel.
        # A resposta 409 ocorre somente apos a verificacao da senha.
        if len(eligible) > 1:
            raise HTTPException(
                status_code=409,
                detail='Mais de uma caixinha vinculada. Informe o ID da caixinha para entrar.',
            )
        return requested_role, eligible[0]["tenant_id"]

    # Um tenant indicado sem papel nao autoriza fallback implicito.
    if requested_tenant_id is not None:
        deny()

    # Fallback de cliente legado SOMENTE para exatamente um vínculo.
    # Dois papéis, duas caixinhas ou linhas duplicadas: nunca usar links[0].
    # A senha já foi verificada antes desta seleção no endpoint /login.
    if requested_role is None and not is_master and links:
        if len(links) != 1:
            raise HTTPException(
                status_code=409,
                detail="Mais de um vínculo cadastrado. Escolha perfil e caixinha.",
            )
        row = links[0]
        if row["role"] in ("TENANT_ADMIN", "TENANT_MEMBER") and row["tenant_id"] is not None:
            return row["role"], row["tenant_id"]

    deny()
