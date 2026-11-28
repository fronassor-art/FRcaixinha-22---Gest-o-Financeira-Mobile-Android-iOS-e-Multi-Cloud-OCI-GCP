"""FR Finance M37500–M37692: 192 independently identifiable review tasks.

A planned task is NOT a deployed capability, an approved migration, a
verified user consent, a tested provider or an authorization to go live.
This immutable dependency plan never invokes external services.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

WORKSTREAMS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("OCI_CAPACITY", (
        "Ler quota A1 e disponibilidade", "Correlacionar erro OUT_OF_HOST_CAPACITY",
        "Revalidar compartimento staging", "Confirmar regiao GRU",
        "Confirmar saldo Always Free", "Avaliar VM E2 Micro sem cobranca",
        "Registrar custo maximo zero", "Proibir criacao sem autorizacao",
        "Auditar instancia por SDK", "Distinguir provisioning de running",
        "Reconciliar observador GitHub", "Emitir prova de ciclo de vida",
    )),
    ("OCI_NETWORK", (
        "Inventariar VCN e subnet", "Auditar rota Internet Gateway",
        "Auditar TCP 80", "Auditar TCP 443", "Revisar SSH publico",
        "Bloquear PostgreSQL publico", "Planejar NSG de menor privilegio",
        "Planejar firewall no sistema", "Preparar DNS sem alterar zona",
        "Definir validacao de certificado", "Preparar monitor de HTTPS",
        "Revisar exposicao final",
    )),
    ("OCI_IAM_VAULT", (
        "Listar policy IAM raiz", "Listar policy staging",
        "Revisar grupo dinamico", "Definir instance principal",
        "Planejar vault dedicado", "Isolar segredos por finalidade",
        "Proteger refresh OAuth", "Proteger SMTP secret",
        "Proteger chave de assinatura", "Definir rotacao de segredos",
        "Provar negativa cross tenant", "Auditar menor privilegio",
    )),
    ("POSTGRES_STAGE", (
        "Congelar catalogo SQL", "Validar hashes SQL", "Separar SQL staging de local",
        "Planejar backup cifrado", "Provar restore em banco descartavel",
        "Revisar roles sem BYPASSRLS", "Revisar FORCE ROW LEVEL SECURITY",
        "Planejar parity de schema", "Testar duas tenants adversariais",
        "Checar TLS verify-full", "Validar integridade de ledger",
        "Bloquear migracao original nao autorizada",
    )),
    ("AUTH_SESSIONS", (
        "Revisar segredo HMAC", "Revisar Argon2id", "Revisar expiracao",
        "Revisar logout", "Revisar revogacao em familia", "Revisar rate limiting",
        "Revisar sessao unica por identidade", "Revisar sessao por tenant",
        "Revisar CSRF e cookies", "Testar recuperacao de senha",
        "Testar impossibilidade de replay", "Atestar E2E staging",
    )),
    ("ACCESS_MASTER_ADMIN_MEMBER", (
        "Mapear papeis Master Admin Membro", "Revisar matriz de permissoes",
        "Revisar acesso unico", "Revisar escopo da caixinha",
        "Revisar leitura de saldos", "Revisar negacao cross tenant",
        "Exigir MFA Master", "Exigir segunda aprovacao",
        "Revisar concorrencia de login", "Revisar suspensao 90 dias",
        "Testar troca de perfil", "Revisar trilha de auditoria",
    )),
    ("CONTRACTS", (
        "Congelar texto juridico", "Publicar hash SHA256",
        "Vincular hash a convite", "Vincular hash a identidade",
        "Exigir aceite afirmativo", "Rejeitar aceite pre-marcado",
        "Rejeitar versao divergente", "Revisar fuso e carimbo",
        "Preservar recibo imutavel", "Revisar revogacao",
        "Revisar saida voluntaria", "Atestar consentimento real E2E",
    )),
    ("INVITATIONS", (
        "Revisar convite single use", "Revisar nonce aleatorio",
        "Revisar tenant no convite", "Revisar destinatario",
        "Revisar validade", "Revisar prova de posse email",
        "Revisar limite tentativas", "Revisar reenvio",
        "Revisar concorrencia", "Revisar claim de capacidade",
        "Revisar cadastro atomico", "Atestar admissao staging",
    )),
    ("BREVO_NOTIFICATIONS", (
        "Revisar dominio do remetente", "Revisar SPF",
        "Revisar DKIM", "Revisar DMARC", "Revisar STARTTLS",
        "Revisar sender verificado", "Revisar outbox transacional",
        "Revisar lease e retry", "Revisar bounce",
        "Revisar deduplicacao", "Revisar webhook assinado",
        "Atestar entrega e posse em caixa teste",
    )),
    ("MP_OAUTH", (
        "Revisar client ID", "Revisar redirect HTTPS",
        "Revisar PKCE", "Revisar state single use",
        "Revisar consentimento por vendedor", "Revisar tenant binding",
        "Revisar offline access", "Revisar rotacao refresh",
        "Revisar expiração do token", "Revisar reconnect",
        "Revisar Vault", "Atestar sandbox por administrador",
    )),
    ("PIX_INBOUND", (
        "Definir transacao sandbox", "Revisar Orders API",
        "Revisar idempotency key", "Revisar referencia externa",
        "Revisar webhook x signature", "Revisar janela replay",
        "Revisar tenant imutavel", "Revisar leitura GET provedor",
        "Revisar confirmacao ledger", "Revisar divergencia de centavos",
        "Revisar reversao e disputa", "Atestar conciliação de tres fontes",
    )),
    ("PIX_OUTBOUND", (
        "Verificar habilitacao comercial", "Revisar escopo Money Out",
        "Revisar limites de saque", "Revisar destinatario",
        "Exigir aprovacao multipla", "Revisar saldo disponivel",
        "Revisar reserva contabil", "Revisar chave idempotente",
        "Revisar assinatura do provedor", "Revisar hold por divergencia",
        "Revisar conciliacao pos envio", "Bloquear dinheiro real sem licenca",
    )),
    ("RECONCILIATION", (
        "Definir identidade do lancamento", "Revisar numeracao unica",
        "Revisar ledger DR CR", "Revisar tres fontes",
        "Revisar duplicidade de webhook", "Revisar processamento fora de ordem",
        "Revisar reversao", "Revisar estorno", "Revisar tarifas",
        "Revisar discrepancia", "Revisar fechamento de incidente",
        "Revisar trilha imutavel",
    )),
    ("FINANCIAL_RULES", (
        "Garantir minimo R$150 por membro ciclo", "Garantir valor definido pelo admin",
        "Revisar teto de participantes", "Revisar inadimplencia 90 dias",
        "Revisar exclusao do rateio inadimplente", "Revisar saida voluntaria",
        "Revisar rendimento real anual", "Calcular 15 por cento admin",
        "Calcular 85 por cento membros", "Tratar centavos residuais",
        "Testar dois tenants", "Bloquear distribuicao sem fonte real",
    )),
    ("ANDROID_DELIVERY", (
        "Revisar API URL HTTPS", "Revisar cleartext false",
        "Revisar identidade de cada perfil", "Revisar navegacao sem mock",
        "Revisar notificacoes em aparelho", "Revisar login logout em aparelho",
        "Revisar fingerprint de build", "Revisar SHA API versus APK",
        "Revisar assinatura de release", "Revisar atualizacao instalada",
        "Revisar crash recovery", "Atestar AT01 a AT50",
    )),
    ("RELEASE_CONTROL", (
        "Enumerar 20 gates live", "Enumerar 7 gates provider",
        "Congelar estado de flags", "Revisar proibicao Pix real",
        "Revisar proibicao licenca real", "Revisar proibicao de usuarios reais",
        "Revisar telemetria sem segredos", "Revisar logs imutaveis",
        "Revisar rollback", "Solicitar aprovacao juridica independente",
        "Solicitar aprovacao operacional independente", "Documentar decisao go no go",
    )),
)

LIVE_GATES = (
    "AUTH_PRODUCTION", "MASTER_MFA", "DUAL_CONTROL", "TENANT_RLS",
    "INVITE_TRANSACTION", "VERIFIED_EMAIL", "CANONICAL_CONTRACT",
    "CONTRACT_CONSENT", "MAIL_OUTBOX", "PASSWORD_RECOVERY",
    "OCI_PUBLIC_HTTPS", "OCI_BACKUP_RESTORE", "MIGRATION_PARITY",
    "RUNTIME_SHA", "ANDROID_RELEASE", "MP_CONNECT", "PIX_INBOUND",
    "PIX_OUTBOUND", "FINANCIAL_RECONCILIATION", "ANNUAL_CLOSING",
)
PROVIDER_GATES = (
    "OCI_HOSTING", "OCI_VAULT_IAM", "MAIL_PROVIDER",
    "USER_ACTIVATION", "MP_CONNECT", "PIX_INBOUND", "PIX_OUTBOUND",
)

@dataclass(frozen=True)
class ReleaseTask:
    task_id: str
    stream: str
    step: int
    description: str
    depends_on: tuple[str, ...]
    status: str = "PLANNED_NOT_REAL_VERIFIED"
    cloud_mutation_authorized: bool = False
    local_sql_apply_authorized: bool = False
    real_user_activation_authorized: bool = False
    real_pix_authorized: bool = False


def workplan() -> tuple[ReleaseTask, ...]:
    if (len(WORKSTREAMS) != 16
            or len({name for name, _ in WORKSTREAMS}) != 16
            or len(LIVE_GATES) != 20 or len(PROVIDER_GATES) != 7):
        raise ValueError("M37500_PLAN_DEFINITION_DRIFT")
    tasks: list[ReleaseTask] = []
    ids: set[str] = set()
    for stream, actions in WORKSTREAMS:
        if len(actions) != 12 or len(set(actions)) != 12:
            raise ValueError("M37500_STREAM_DEFINITION_DRIFT")
        predecessor: str | None = None
        for step, action in enumerate(actions, 1):
            task_id = "M" + str(37501 + len(tasks))
            if task_id in ids or not action.strip():
                raise ValueError("M37500_DUPLICATE_OR_EMPTY_TASK")
            tasks.append(ReleaseTask(
                task_id=task_id, stream=stream, step=step,
                description=action, depends_on=(predecessor,) if predecessor else (),
            ))
            ids.add(task_id)
            predecessor = task_id
    if len(tasks) != 192:
        raise ValueError("M37500_TASK_COUNT_DRIFT")
    return tuple(tasks)


def plan_summary(*, evidence: Mapping[str, object] | None = None) -> dict:
    """All observations are explicitly operator-supplied and never self-attested."""
    if evidence is not None and type(evidence) is not dict:
        raise ValueError("M37500_EVIDENCE_MAPPING_REQUIRED")
    tasks = workplan()
    return {
        "project": "FR_FINANCE_AI_STUDIO",
        "package": "M37500_M37692",
        "scope": "OFFLINE_ENGINEERING_PLAN_NO_LIVE_ATTESTATION",
        "tasks_total": len(tasks),
        "workstreams_total": len(WORKSTREAMS),
        "tasks_real_verified_by_this_tool": 0,
        "live_gates_total": len(LIVE_GATES),
        "live_gates_verified_by_this_tool": 0,
        "provider_gates_total": len(PROVIDER_GATES),
        "provider_gates_verified_by_this_tool": 0,
        "operator_supplied_evidence_is_live_proof": False,
        "real_activation_authorized": False,
        "pix_real_authorized": False,
        "payments_real_authorized": False,
        "cloud_mutations_authorized": False,
        "postgres_original_migration_authorized": False,
        "staging_only_sql_apply_authorized": False,
        "tasks": [
            {
                "id": t.task_id, "stream": t.stream, "step": t.step,
                "action": t.description, "depends_on": list(t.depends_on),
                "status": t.status,
                "real_authorized": False,
            }
            for t in tasks
        ],
    }
