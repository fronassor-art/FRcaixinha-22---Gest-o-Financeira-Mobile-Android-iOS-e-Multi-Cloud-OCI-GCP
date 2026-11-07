"""M25600 — actionable FR Finance AI Studio launch requirements.

This inventory deliberately reports *evidence still missing*, not automatic
production enablement. No DB/network calls, no secret values, no side effects.
"""
from __future__ import annotations

from pathlib import Path
from typing import Mapping

from .config import safe_public_https_origin
from .onboarding_mail_transport import verify_smtp_configuration, MailConfigurationBlocked
from .production_auth_gate import require_production_auth, ProductionAuthBlocked

ROOT = Path(__file__).resolve().parents[2]

REQUIREMENTS = (
    ("AUTH_PRODUCTION", "identidade", "Credenciais seguras, roles segregadas, TLS e teste de login no staging OCI."),
    ("MASTER_MFA", "identidade", "Prova de MFA real para ações sensíveis do Administrador Master."),
    ("DUAL_CONTROL", "identidade", "Aprovação independente de novas contas administrativas."),
    ("TENANT_RLS", "identidade", "Teste adversarial de RLS e privilégios em staging no banco definitivo."),
    ("INVITE_TRANSACTION", "cadastro", "Emissão e aceite atômicos: convite, vínculo, versionamento, auditoria e uso único."),
    ("VERIFIED_EMAIL", "cadastro", "Confirmação real de posse do e-mail e limite distribuído de tentativas."),
    ("CANONICAL_CONTRACT", "cadastro", "Termo jurídico aprovado hospedado e byte a byte conferido com SHA-256 publicado."),
    ("CONTRACT_CONSENT", "cadastro", "Aceite afirmativo da pessoa convidada vinculado a documento e identidade verificados."),
    ("MAIL_OUTBOX", "cadastro", "Worker transacional com deduplicação, retry seguro e webhooks de entrega."),
    ("PASSWORD_RECOVERY", "cadastro", "Recuperação com expiração, uso único, troca de senha e revogação de todas as sessões."),
    ("OCI_PUBLIC_HTTPS", "infra", "Staging OCI público sob HTTPS válido, domínio e firewall restrito."),
    ("OCI_BACKUP_RESTORE", "infra", "Backup restaurado com sucesso em ambiente isolado, RPO e RTO documentados."),
    ("MIGRATION_PARITY", "infra", "Histórico do banco local e staging atestado por SELECT, com versão e hashes das migrações."),
    ("RUNTIME_SHA", "infra", "SHA runtime comprovado e correlacionado à versão do APK implantado."),
    ("ANDROID_RELEASE", "infra", "APK/AAB release assinado, atualizado e testado no dispositivo."),
    ("MP_CONNECT", "pagamentos", "OAuth Connect por administrador, secrets segregados e teste no provedor."),
    ("PIX_INBOUND", "pagamentos", "Orders Pix real, webhook assinado e conciliação idempotente homologados."),
    ("PIX_OUTBOUND", "pagamentos", "Permissão comercial Money Out, PSP_TRANSFER e limites autorizados pelo provedor."),
    ("FINANCIAL_RECONCILIATION", "pagamentos", "Conciliação de três fontes para capital, crédito e Livro-Razão."),
    ("ANNUAL_CLOSING", "pagamentos", "Fechamento anual testado com 15% administrador, 85% membros e restrições de inadimplência."),
)


def _engineering_evidence() -> dict[str, bool]:
    return {
        "AUTH_PRODUCTION": (ROOT / "backend/app/production_auth_gate.py").is_file(),
        "MASTER_MFA": False,
        "DUAL_CONTROL": (ROOT / "backend/app/admin_onboarding_workflow.py").is_file(),
        "TENANT_RLS": (ROOT / "backend/tests/test_rls_isolation_ci.py").is_file(),
        "INVITE_TRANSACTION": (ROOT / "backend/app/account_lifecycle.py").is_file(),
        "VERIFIED_EMAIL": (ROOT / "backend/app/invite_registration_ci.py").is_file(),
        "CANONICAL_CONTRACT": (ROOT / "backend/app/canonical_contract_store.py").is_file(),
        "CONTRACT_CONSENT": (ROOT / "backend/app/account_lifecycle.py").is_file(),
        "MAIL_OUTBOX": (ROOT / "backend/app/onboarding_mail_transport.py").is_file(),
        "PASSWORD_RECOVERY": (ROOT / "backend/app/account_lifecycle.py").is_file(),
        "OCI_PUBLIC_HTTPS": False,
        "OCI_BACKUP_RESTORE": (ROOT / "backend/scripts/aistudio_migration_inventory.py").is_file(),
        "MIGRATION_PARITY": (ROOT / "backend/scripts/aistudio_migration_inventory.py").is_file(),
        "RUNTIME_SHA": False,
        "ANDROID_RELEASE": (ROOT / ".github/workflows/validacao-atualizacao.yml").is_file(),
        "MP_CONNECT": (ROOT / "backend/app/mp_oauth_connect_preflight.py").is_file(),
        "PIX_INBOUND": (ROOT / "backend/app/pix_automation_service.py").is_file(),
        "PIX_OUTBOUND": False,
        "FINANCIAL_RECONCILIATION": (ROOT / "backend/app/financial_three_source_preflight.py").is_file(),
        "ANNUAL_CLOSING": (ROOT / "backend/app/routers/closings.py").is_file(),
    }


def readiness_manifest(env: Mapping[str, str]) -> dict:
    """Master-only read in API. Static config checks are not live attestations."""
    try:
        verify_smtp_configuration(env)
        smtp_syntax = True
    except MailConfigurationBlocked:
        smtp_syntax = False
    try:
        require_production_auth(env)
        production_auth_syntax = True
    except ProductionAuthBlocked:
        production_auth_syntax = False
    origin_syntax = safe_public_https_origin(env.get("APP_URL", "")) is not None
    evidence = _engineering_evidence()
    entries = [
        {
            "id": gate, "category": category,
            "status": "INTEGRATION_AND_ATTESTATION_REQUIRED",
            "engineering_source_present": evidence.get(gate, False),
            "production_verified": False,
            "required_evidence": requirement,
        }
        for gate, category, requirement in REQUIREMENTS
    ]
    return {
        "source": "REPOSITORY_AND_CONFIGURATION_DECLARATIONS",
        "scope": "AI_STUDIO_MASTER_RELEASE_READINESS",
        "mode": "READ_ONLY_NO_ACTIVATION",
        "status": "BLOCKED",
        "workstream": "AI_STUDIO",
        "production_auth_config_syntax_valid": production_auth_syntax,
        "smtp_config_syntax_valid": smtp_syntax,
        "public_https_origin_syntax_valid": origin_syntax,
        "config_valid_is_live_proof": False,
        "real_invites_active": False,
        "password_reset_active": False,
        "real_pix_active": False,
        "financial_closing_authorized": False,
        "writes_performed": False,
        "total_gates": len(entries),
        "unverified_gates": len(entries),
        "requirements": entries,
    }
