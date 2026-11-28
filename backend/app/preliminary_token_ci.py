"""M41450 domain separation for CI-only preliminary credentials.
NUL cannot be represented in PostgreSQL text or the ordinary HTTP bearer grammar.
The marker is not an authentication proof; the separated digest is mandatory.
"""
import re
from .security import hash_token

MARKER="FR_FINANCE_CI_PRELIMINARY_V1"
PREFIX="frp_"
def is_preliminary(token):
    return isinstance(token,str) and token.startswith(PREFIX)
def preliminary_digest(token):
    if not isinstance(token,str) or not re.fullmatch(r"frp_[A-Za-z0-9_-]{43}",token):
        raise ValueError("Credencial preliminar inválida.")
    return hash_token(MARKER+"\x00"+token)
