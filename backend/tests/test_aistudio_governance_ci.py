"""Pacote de testes PostgreSQL descartável: identidade única, contratos e SaaS.

Nenhuma conexão Termux: valida database, host, porta e papel de CI.
"""
import os
from hashlib import sha256
from uuid import uuid4
from urllib.parse import urlparse

import psycopg
import pytest

from app.account_lifecycle import LifecycleDenied
from app.account_governance_ci import (
    publish_document_ci, record_contract_acceptance_ci,
    link_existing_identity_ci, prepare_saas_license_ci, saas_capacity_snapshot_ci,
)


@pytest.fixture
def ci_accounts():
    if os.getenv("FRCAIXINHA_CI_ISOLATED") != "1":
        pytest.skip("Exclusivamente PostgreSQL efêmero no CI")
    dsn = os.environ["CI_ADMIN_DATABASE_URL"]
    p = urlparse(dsn)
    assert p.hostname in ("localhost","127.0.0.1") and p.port == 5432
    assert p.path == "/frcaixinha_ci" and p.username == "postgres"
    # Transação externa é desfeita: os contratos possuem trigger de imutabilidade.
    with psycopg.connect(dsn) as conn:
        a,b,member,master = (uuid4() for _ in range(4))
        tenant_a,tenant_b = uuid4(),uuid4()
        for uid,name,ismaster in (
            (a,"Admin A",False),(b,"Admin B",False),
            (member,"Membro único",False),(master,"Master",True)
        ):
            conn.execute(
                "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master)"
                "VALUES(%s,%s,%s,%s,'00000000000',%s)",
                (uid, f"{uid}@example.com",name,uid.hex[:14],ismaster)
            )
        for tenant,admin in ((tenant_a,a),(tenant_b,b)):
            conn.execute(
                "INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id)"
                "VALUES(%s,'Tenant sintético',%s,%s)",(tenant,str(uuid4()),admin)
            )
            conn.execute(
                "INSERT INTO public.memberships(tenant_id,user_id,role)"
                "VALUES(%s,%s,'TENANT_ADMIN')",(tenant,admin)
            )
        try:
            yield conn,dict(a=a,b=b,member=member,master=master,
                            tenant_a=tenant_a,tenant_b=tenant_b)
        finally:
            conn.rollback()


def doc(db,kind,version):
    return publish_document_ci(
        db,kind=kind,version=version,
        sha256_hex=sha256(f"{kind}:{version}:synthetic".encode()).hexdigest(),
        reference="Contrato sintético de teste sem valor jurídico"
    )


def test_single_identity_can_hold_multiple_roles_with_acceptances(ci_accounts):
    db,u=ci_accounts
    document=doc(db,'TENANT_MEMBERSHIP','ci-1')
    first=record_contract_acceptance_ci(
        db,user_id=u['member'],document_id=document,tenant_id=u['tenant_a']
    )
    membership=link_existing_identity_ci(
        db,user_id=u['member'],tenant_id=u['tenant_a'],
        role='TENANT_MEMBER',acceptance_id=first,
    )
    assert membership
    with pytest.raises(LifecycleDenied):
        link_existing_identity_ci(
            db,user_id=u['member'],tenant_id=u['tenant_a'],
            role='TENANT_MEMBER',acceptance_id=first,
        )
    # Segunda caixinha: MESMA identidade, outro aceite específico.
    second=record_contract_acceptance_ci(
        db,user_id=u['member'],document_id=document,tenant_id=u['tenant_b']
    )
    role_b=link_existing_identity_ci(
        db,user_id=u['member'],tenant_id=u['tenant_b'],
        role='TENANT_MEMBER',acceptance_id=second,
    )
    # A mesma pessoa pode exercer ADMIN+MEMBER no mesmo tenant, por vínculo explícito.
    admin_accept=record_contract_acceptance_ci(
        db,user_id=u['a'],document_id=document,tenant_id=u['tenant_a']
    )
    member_role=link_existing_identity_ci(
        db,user_id=u['a'],tenant_id=u['tenant_a'],role='TENANT_MEMBER',
        acceptance_id=admin_accept
    )
    assert member_role != membership != role_b
    assert db.execute(
        "SELECT count(*) FROM public.users WHERE id=%s",(u['member'],)
    ).fetchone()[0] == 1
    assert db.execute(
        "SELECT count(*) FROM public.memberships WHERE user_id=%s",
        (u['member'],)
    ).fetchone()[0] == 2
    counts=saas_capacity_snapshot_ci(db,tenant_id=u['tenant_a'])
    assert counts['active_member_identities'] == 2
    assert counts['is_licensing_decision'] is False


def test_acceptance_must_match_user_document_and_tenant(ci_accounts):
    db,u=ci_accounts
    member_doc=doc(db,'TENANT_MEMBERSHIP','ci-members')
    platform_doc=doc(db,'PLATFORM_LICENSE','ci-platform')
    with pytest.raises(LifecycleDenied):
        record_contract_acceptance_ci(
            db,user_id=u['member'],document_id=platform_doc,tenant_id=u['tenant_a']
        )
    good=record_contract_acceptance_ci(
        db,user_id=u['member'],document_id=member_doc,tenant_id=u['tenant_a']
    )
    for kwargs in (
        dict(user_id=u['a'],tenant_id=u['tenant_a']),
        dict(user_id=u['member'],tenant_id=u['tenant_b'])
    ):
        with pytest.raises(LifecycleDenied):
            link_existing_identity_ci(
                db,role='TENANT_MEMBER',acceptance_id=good,**kwargs,
            )
    with pytest.raises(psycopg.errors.UniqueViolation):
        with db.transaction():
            record_contract_acceptance_ci(
                db,user_id=u['member'],document_id=member_doc,tenant_id=u['tenant_a']
            )
    row=db.execute(
        "SELECT evidence_hash,evidence_method FROM public.contract_acceptances "
        "WHERE id=%s",(good,)
    ).fetchone()
    assert len(row[0]) == 64 and row[1]=='CI_VERIFIED_IDENTITY'
    with pytest.raises(psycopg.errors.RaiseException):
        with db.transaction():
            db.execute(
                "DELETE FROM public.contract_acceptances WHERE id=%s",(good,)
            )


def test_saas_preparation_snapshot_never_active_or_paid(ci_accounts):
    db,u=ci_accounts
    platform=doc(db,'PLATFORM_LICENSE','ci-saas-v1')
    acceptance=record_contract_acceptance_ci(
        db,user_id=u['a'],document_id=platform,
    )
    version=db.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()[0]
    ident=prepare_saas_license_ci(
        db,tenant_id=u['tenant_a'],admin_id=u['a'],
        price_version_id=version,billing_period='ANNUAL',
        acceptance_id=acceptance,
    )
    state=db.execute(
        "SELECT s.status,s.billing_period,s.price_version_id,v.annual_price "
        "FROM public.saas_subscription_preparations s "
        "JOIN public.platform_license_price_versions v ON v.id=s.price_version_id "
        "WHERE s.id=%s",(ident,)
    ).fetchone()
    assert state==('PENDING_PAYMENT','ANNUAL',version,899.00)
    assert db.execute(
        "SELECT count(*) FROM public.saas_subscription_preparations WHERE status='ACTIVE'"
    ).fetchone()[0] == 0
    with pytest.raises(psycopg.errors.CheckViolation):
        with db.transaction():
            db.execute(
                "UPDATE public.saas_subscription_preparations SET status='ACTIVE' WHERE id=%s",
                (ident,),
            )
    with pytest.raises(LifecycleDenied):
        prepare_saas_license_ci(
            db,tenant_id=u['tenant_b'],admin_id=u['a'],
            price_version_id=version,billing_period='MONTHLY',
            acceptance_id=acceptance,
        )


def test_rls_contract_and_saas_profiles(ci_accounts):
    db,u=ci_accounts
    contract=doc(db,'PLATFORM_LICENSE','ci-rls')
    acceptance=record_contract_acceptance_ci(
        db,user_id=u['a'],document_id=contract,
    )
    version=db.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' LIMIT 1"
    ).fetchone()[0]
    prepare_saas_license_ci(
        db,tenant_id=u['tenant_a'],admin_id=u['a'],
        price_version_id=version,billing_period='MONTHLY',
        acceptance_id=acceptance,
    )
    def app_read(actor,role,tenant=None):
        db.execute('SAVEPOINT scoped')
        try:
            db.execute("SET LOCAL ROLE frcaixinha_ci")
            db.execute(
                "SELECT set_config('app.current_user_id',%s,true)",(str(actor),)
            )
            db.execute(
                "SELECT set_config('app.current_role',%s,true)",(role,)
            )
            db.execute(
                "SELECT set_config('app.current_tenant_id',%s,true)",
                (str(tenant) if tenant else '',)
            )
            return (
                db.execute("SELECT count(*) FROM public.contract_acceptances").fetchone()[0],
                db.execute("SELECT count(*) FROM public.saas_subscription_preparations").fetchone()[0],
            )
        finally:
            db.execute('ROLLBACK TO SAVEPOINT scoped')
            db.execute('RELEASE SAVEPOINT scoped')
    assert app_read(u['a'],'TENANT_ADMIN',u['tenant_a'])==(1,1)
    assert app_read(u['b'],'TENANT_ADMIN',u['tenant_b'])==(0,0)
    assert app_read(u['member'],'TENANT_MEMBER',u['tenant_a'])==(0,0)
    assert app_read(u['master'],'MASTER')==(0,1)
    assert app_read(u['a'],'MASTER')==(0,0), 'Admin não pode falsificar MASTER'
    assert app_read(u['a'],'TENANT_ADMIN',u['tenant_b'])==(0,0)


def test_governance_functions_refuse_any_non_ci_environment(monkeypatch,ci_accounts):
    db,u=ci_accounts
    monkeypatch.delenv("FRCAIXINHA_CI_ISOLATED",raising=False)
    with pytest.raises(LifecycleDenied):
        publish_document_ci(db,kind='PLATFORM_LICENSE',
          version='deny',sha256_hex='a'*64,reference='Não deve persistir')
    with pytest.raises(LifecycleDenied):
        saas_capacity_snapshot_ci(db,tenant_id=u['tenant_a'])
