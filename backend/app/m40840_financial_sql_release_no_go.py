"""M40840: runtime fail-closed gate for financial SQL until trust boundary reviewed.

Production is categorically disallowed. No configuration flag, server proof
or CI success authorizes GUC-based financial access in live mode.
"""
from __future__ import annotations

from typing import Mapping


class FinancialSQLReleaseBlocked(RuntimeError):
    """Generic non-sensitive refusal, never echo environment or DSN."""


_NONPROD = frozenset((
    "development", "dev", "local", "test", "testing", "ci",
    "homologation", "homologacao", "staging",
))
_REAL_FLAGS = ("PIX_REAL", "PAGAMENTOS_REAIS", "ATIVACAO_REAL")


def require_nonproduction_financial_sql(env: Mapping[str, str]) -> str:
    """Only recognizes limited non-production mode with all live flags OFF.

    Deliberately does not support an override or 'approved' boolean.
    Do not infer integrity of SQL context, RLS policies or service identity.
    """
    if not hasattr(env, "get"):
        raise FinancialSQLReleaseBlocked("M40840_FINANCIAL_SQL_NO_GO")
    mode = env.get("ENVIRONMENT", "development")
    if type(mode) is not str or mode not in _NONPROD:
        raise FinancialSQLReleaseBlocked("M40840_FINANCIAL_SQL_NO_GO")
    for flag in _REAL_FLAGS:
        value = env.get(flag, "OFF")
        if type(value) is not str or value != "OFF":
            raise FinancialSQLReleaseBlocked("M40840_FINANCIAL_SQL_NO_GO")
    return "NONPRODUCTION_ONLY_NO_SQL_TRUST_ATTESTATION"
