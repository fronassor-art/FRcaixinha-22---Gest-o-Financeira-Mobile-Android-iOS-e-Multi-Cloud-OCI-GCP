"""Governança contratual e identidade única: APENAS laboratório CI descartável.

NÃO é rota da API, não prova titularidade externa, não cadastra usuário novo.
As evidências são sintéticas. Funções não devem ser ativadas em produção.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid4
import secrets

from .account_lifecycle import _ci_only, LifecycleDenied


def publish_document_ci(conn, *, kind: str, version: str,
                        sha256_hex: str, reference: str) -> UUID:
    _ci_only(conn)
    if kind not in ("PLATFORM_LICENSE", "TENANT_MEMBERSHIP"):
        raise LifecycleDenied("Tipo de documento indisponível.")
    if len(sha256_hex) != 64 or any(c not in "0123456789abcdef" for c in sha256_hex):
        raise LifecycleDenied("Digest do documento inválido.")
    doc_id = uuid4()
    conn.execute(
        "INSERT INTO public.contract_documents"
        "(id,document_kind,version_label,sha256,source_reference,published_at)"
        " VALUES(%s,%s,%s,%s,%s,now())",
        (doc_id,kind,version,sha256_hex,reference),
    )
    return doc_id


def record_contract_acceptance_ci(conn, *, user_id: UUID, document_id: UUID,
                                  tenant_id: UUID | None = None) -> UUID:
    """Aceite sintético: registra hash da prova; não assina em nome de usuário real."""
    _ci_only(conn)
    with conn.transaction():
        doc = conn.execute(
            "SELECT document_kind,published_at FROM public.contract_documents"
            " WHERE id=%s", (document_id,),
        ).fetchone()
        user = conn.execute(
            "SELECT status FROM public.users WHERE id=%s", (user_id,)
        ).fetchone()
        if not doc or doc[1] is None or not user or user[0] != 'ACTIVE':
            raise LifecycleDenied("Identidade ou documento indisponível.")
        if (doc[0] == "PLATFORM_LICENSE") != (tenant_id is None):
            raise LifecycleDenied("Escopo do aceite incompatível com documento.")
        if tenant_id:
            tenant = conn.execute(
                "SELECT status FROM public.tenants WHERE id=%s", (tenant_id,)
            ).fetchone()
            if not tenant or tenant[0] != 'ATIVO':
                raise LifecycleDenied("Caixinha indisponível para aceite.")
        accepted = uuid4()
        evidence = sha256((str(user_id)+":"+str(document_id)+":"+
                           str(tenant_id)+":"+secrets.token_hex(32)).encode()).hexdigest()
        conn.execute(
            "INSERT INTO public.contract_acceptances"
            "(id,document_id,document_kind,user_id,tenant_id,evidence_hash,evidence_method)"
            " VALUES(%s,%s,%s,%s,%s,%s,'CI_VERIFIED_IDENTITY')",
            (accepted,document_id,doc[0],user_id,tenant_id,evidence),
        )
        conn.execute(
            "INSERT INTO public.audit_events"
            "(actor_id,actor_role,tenant_id,action,object_type,object_id,reason,evidence_ref)"
            "VALUES(%s,'SYSTEM',%s,'CI_CONTRACT_ACCEPTANCE','CONTRACT',%s,%s,%s)",
            (user_id,tenant_id,str(accepted),
             "Aceite de laboratório: sem prova externa de identidade",evidence),
        )
        return accepted


def link_existing_identity_ci(conn, *, user_id: UUID, tenant_id: UUID,
                              role: str, acceptance_id: UUID) -> UUID:
    """Só vincula identidade EXISTENTE com aceite explícito para tenant exato."""
    _ci_only(conn)
    if role not in ('TENANT_MEMBER','TENANT_ADMIN'):
        raise LifecycleDenied("Papel inválido.")
    with conn.transaction():
        identity = conn.execute(
            "SELECT status FROM public.users WHERE id=%s FOR UPDATE", (user_id,)
        ).fetchone()
        tenant = conn.execute(
            "SELECT status FROM public.tenants WHERE id=%s FOR UPDATE", (tenant_id,)
        ).fetchone()
        acceptance = conn.execute(
            "SELECT user_id,tenant_id,document_kind FROM public.contract_acceptances"
            " WHERE id=%s", (acceptance_id,),
        ).fetchone()
        if (not identity or identity[0] != 'ACTIVE' or not tenant or tenant[0] != 'ATIVO'
                or not acceptance or acceptance !=
                (user_id,tenant_id,'TENANT_MEMBERSHIP')):
            raise LifecycleDenied("Vínculo sem aceite válido da pessoa e caixinha.")
        if conn.execute(
            "SELECT 1 FROM public.memberships WHERE tenant_id=%s AND user_id=%s"
            " AND role=%s", (tenant_id,user_id,role),
        ).fetchone():
            raise LifecycleDenied("Vínculo existente: nenhuma duplicidade autorizada.")
        membership_id = uuid4()
        conn.execute(
            "INSERT INTO public.memberships(id,tenant_id,user_id,role,status)"
            "VALUES(%s,%s,%s,%s,'ATIVA')",
            (membership_id,tenant_id,user_id,role),
        )
        conn.execute(
            "INSERT INTO public.audit_events(actor_id,actor_role,tenant_id,"
            "action,object_type,object_id,reason,evidence_ref)"
            " VALUES(%s,'SYSTEM',%s,'CI_EXISTING_IDENTITY_LINKED','MEMBERSHIP',%s,%s,%s)",
            (user_id,tenant_id,str(membership_id),
             "Vínculo sintético da identidade única por aceite explícito",str(acceptance_id)),
        )
        return membership_id


def prepare_saas_license_ci(conn, *, tenant_id: UUID, admin_id: UUID,
                            price_version_id: UUID, billing_period: str,
                            acceptance_id: UUID) -> UUID:
    """Prepara oferta sem status ACTIVE, liquidação, reserva ou cobrança."""
    _ci_only(conn)
    if billing_period not in ('MONTHLY','ANNUAL'):
        raise LifecycleDenied("Vigência inválida.")
    with conn.transaction():
        admin = conn.execute(
            "SELECT 1 FROM public.memberships WHERE tenant_id=%s AND user_id=%s"
            " AND role='TENANT_ADMIN' AND status='ATIVA'",
            (tenant_id,admin_id),
        ).fetchone()
        accepted = conn.execute(
            "SELECT 1 FROM public.contract_acceptances"
            " WHERE id=%s AND user_id=%s AND document_kind='PLATFORM_LICENSE'"
            " AND tenant_id IS NULL",
            (acceptance_id,admin_id),
        ).fetchone()
        price = conn.execute(
            "SELECT p.plan_tier,p.monthly_price,plans.status"
            " FROM public.platform_license_price_versions p"
            " JOIN public.platform_license_plans plans ON plans.tier=p.plan_tier"
            " WHERE p.id=%s", (price_version_id,),
        ).fetchone()
        if not admin or not accepted or not price or price[2] != 'ACTIVE':
            raise LifecycleDenied("Oferta não autorizada: plano, vínculo ou aceite ausente.")
        ident=uuid4()
        conn.execute(
            "INSERT INTO public.saas_subscription_preparations"
            "(id,tenant_id,admin_user_id,plan_tier,price_version_id,billing_period,"
            "contract_acceptance_id,status)"
            "VALUES(%s,%s,%s,%s,%s,%s,%s,'PENDING_PAYMENT')",
            (ident,tenant_id,admin_id,price[0],price_version_id,billing_period,
             acceptance_id),
        )
        conn.execute(
            "INSERT INTO public.audit_events(actor_id,actor_role,tenant_id,"
            "action,object_type,object_id,reason,evidence_ref)"
            " VALUES(%s,'TENANT_ADMIN',%s,'CI_SAAS_PREPARED','SUBSCRIPTION',%s,%s,%s)",
            (admin_id,tenant_id,str(ident),
             "Licença sintética aguardando conciliação; nunca ativada",str(price_version_id)),
        )
        return ident


def saas_capacity_snapshot_ci(conn, *, tenant_id: UUID) -> dict:
    """Métrica informativa sem impor limites nem gerar cobrança."""
    _ci_only(conn)
    people = conn.execute(
        "SELECT count(DISTINCT user_id) FROM public.memberships "
        "WHERE tenant_id=%s AND role='TENANT_MEMBER' AND status='ATIVA'",
        (tenant_id,),
    ).fetchone()[0]
    quotas = conn.execute(
        "SELECT count(*) FROM public.quotas "
        "WHERE tenant_id=%s AND status='ATIVA'", (tenant_id,),
    ).fetchone()[0]
    return {"tenant_id":str(tenant_id),"active_member_identities":people,
            "active_quotas":quotas,"source":"CI_DATABASE","is_licensing_decision":False}
