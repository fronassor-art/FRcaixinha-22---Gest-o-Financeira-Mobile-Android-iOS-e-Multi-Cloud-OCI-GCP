"""
FRcaixinha 2.2 — Rotas Exclusivas do Administrador Master
Contrato Técnico Mestre (Cláusulas 1.3, 2.8, 3.2, 5.4, 11.2 e 16.4)
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from ..dependencies import require_master, AuthenticatedSession

router = APIRouter(prefix="/master", tags=["Governança Master da Plataforma"])

class SupportBreakGlassRequest(BaseModel):
    target_tenant_id: str
    justification: str = Field(..., min_length=15, description="Justificativa formal auditável para acesso emergencial de suporte")
    duration_minutes: int = Field(default=30, le=60, description="Duração máxima do acesso excepcional (máx 60 min)")

@router.get("/licenses")
def get_platform_licenses(session: AuthenticatedSession = Depends(require_master)):
    """
    Gerenciamento de planos SaaS e preços da plataforma.
    Acesso restrito ao Master.
    """
    return {
        "plans": [
            {"tier": "ESSENCIAL", "members_limit": 20, "quotas_limit": 40, "price_monthly": 89.90},
            {"tier": "INTERMEDIARIO", "members_limit": 50, "quotas_limit": 50, "price_monthly": 109.90},
            {"tier": "AMPLIADO", "status": "BLOCKED_PENDING_CEILING"}
        ]
    }

@router.post("/support-session")
def request_support_break_glass(payload: SupportBreakGlassRequest, session: AuthenticatedSession = Depends(require_master)):
    """
    RECURSO BREAK-GLASS: DESABILITADO POR PADRÃO.
    Conformidade Contratual Estrita (Cláusulas 1.3, 2.8, 5.4 e 16.4):
    O Contrato Técnico Mestre estabelece VEDAÇÃO ABSOLUTA DE INGERÊNCIA DO MASTER
    sobre saldos, dados financeiros e operações de membros das caixinhas.
    Como não há autorização explícita nem especificação completa de requisitos de
    consentimento mútuo prévio no Contrato, este endpoint é mantido BLOQUEADO e registrado
    como pendência negocial/jurídica. Não é permitido habilitá-lo por inferência.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "Recurso Desabilitado",
            "code": "BREAK_GLASS_UNAUTHORIZED_BY_CONTRACT",
            "message": (
                "Acesso excepcional de suporte (Break-Glass) está desabilitado. "
                "O Contrato Técnico Mestre (Cláusulas 1.3, 2.8 e 5.4) impõe vedação absoluta de "
                "ingerência do Master sobre caixinhas. Operação mantida como pendência contratual."
            )
        }
    )
