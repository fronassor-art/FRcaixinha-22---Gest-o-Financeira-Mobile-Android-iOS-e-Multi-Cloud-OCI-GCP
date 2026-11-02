"""Cadastro por convite e cobrança SaaS: PostgreSQL efêmero, não Termux."""
from datetime import datetime,timedelta,timezone
from decimal import Decimal
from hashlib import sha256
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
import pytest

from app.account_lifecycle import (
    LifecycleDenied, prepare_invitation_ci,simulate_invitation_delivery_ci
)
from app.account_governance_ci import (
    publish_document_ci,record_contract_acceptance_ci,prepare_saas_license_ci,
)
from app.invite_registration_ci import (
    _valid_cpf,prepare_invite_email_verification_ci,register_new_invited_identity_ci
)
from app.saas_billing_ci import (
    stage_saas_payment_ci,attach_mp_payment_identifier_ci,
    reconcile_approved_saas_payment_ci,expire_saas_entitlement_ci,
    revoke_after_verified_refund_ci,record_verified_saas_webhook_ci,
    suspend_saas_entitlement_ci,resume_saas_entitlement_ci
)


@pytest.fixture
def base_ci(monkeypatch):
    import os
    if os.getenv("FRCAIXINHA_CI_ISOLATED")!="1":
        pytest.skip("Somente postgres efêmero de GitHub Actions")
    dsn=os.environ["CI_ADMIN_DATABASE_URL"]
    u=urlparse(dsn)
    assert u.hostname in ("localhost","127.0.0.1") and u.port==5432
    assert u.username=="postgres" and u.path=="/frcaixinha_ci"
    with psycopg.connect(dsn) as db:
        master,admin,tenant=uuid4(),uuid4(),uuid4()
        for person,name,is_master in ((master,"Master CI",True),(admin,"Admin CI",False)):
            db.execute(
                "INSERT INTO public.users(id,email,full_name,cpf,phone,is_master)"
                "VALUES(%s,%s,%s,%s,'00000000000',%s)",
                (person,f"{person}@example.com",name,person.hex[:14],is_master),
            )
        db.execute(
            "INSERT INTO public.tenants(id,display_name,contracting_party_id,admin_user_id)"
            "VALUES(%s,'Tenant SaaS CI',%s,%s)",
            (tenant,str(uuid4()),admin),
        )
        db.execute(
            "INSERT INTO public.memberships(tenant_id,user_id,role)"
            "VALUES(%s,%s,'TENANT_ADMIN')",
            (tenant,admin),
        )
        try:
            yield db,dict(master=master,admin=admin,tenant=tenant)
        finally:
            db.rollback()


def _document(db,kind,label):
    return publish_document_ci(
        db,kind=kind,version=label,sha256_hex=sha256(label.encode()).hexdigest(),
        reference="Documento sintético apenas para laboratório CI",
    )


def _billing_fixture(db,u,period="MONTHLY"):
    doc=_document(db,"PLATFORM_LICENSE","ci-billing-"+str(uuid4()))
    acceptance=record_contract_acceptance_ci(db,user_id=u['admin'],document_id=doc)
    pv=db.execute(
        "SELECT id FROM public.platform_license_price_versions "
        "WHERE plan_tier='ESSENCIAL' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()[0]
    prep=prepare_saas_license_ci(
        db,tenant_id=u['tenant'],admin_id=u['admin'],
        price_version_id=pv,billing_period=period,acceptance_id=acceptance,
    )
    return prep


def _payment(id,amount="89.90",status="approved",collector="12345",
             ref=None,live=False,refunded=None):
    payment=dict(id="654321",transaction_amount=amount,status=status,
                currency_id="BRL",collector_id=collector,
                external_reference=ref or f"saas:{id}",live_mode=live)
    if refunded is not None:
        payment["transaction_amount_refunded"]=refunded
    return payment


def test_registration_validates_cpf_and_requires_delivery(base_ci):
    db,u=base_ci
    assert _valid_cpf("52998224725")
    assert not _valid_cpf("11111111111")
    assert not _valid_cpf("52998224720")
    doc=_document(db,"TENANT_MEMBERSHIP","ci-registration-"+str(uuid4()))
    invitation,original=prepare_invitation_ci(
        db,tenant_id=u['tenant'],inviter_id=u['admin'],
        recipient_email="new.member@example.com",target_role="TENANT_MEMBER",
    )
    with pytest.raises(LifecycleDenied):
        prepare_invite_email_verification_ci(db,invitation_id=invitation)
    assert simulate_invitation_delivery_ci(db,invitation)
    verification=prepare_invite_email_verification_ci(db,invitation_id=invitation)
    with pytest.raises(LifecycleDenied):
        register_new_invited_identity_ci(
            db,verification_token=verification,name="Pessoa CI",cpf="11111111111",
            phone="11999999999",password="strong-synthetic-password",document_id=doc,
        )
    person=register_new_invited_identity_ci(
        db,verification_token=verification,name="Pessoa CI",cpf="52998224725",
        phone="11999999999",password="strong-synthetic-password",document_id=doc,
    )
    row=db.execute(
        "SELECT email,is_master,email_verified_at FROM public.users WHERE id=%s",
        (person,),
    ).fetchone()
    assert row[0]=="new.member@example.com" and row[1] is False and row[2] is not None
    assert db.execute(
        "SELECT count(*) FROM public.memberships WHERE user_id=%s "
        "AND tenant_id=%s AND role='TENANT_MEMBER'",(person,u['tenant']),
    ).fetchone()[0]==1
    with pytest.raises(LifecycleDenied):
        register_new_invited_identity_ci(
            db,verification_token=verification,name="Pessoa CI",cpf="52998224725",
            phone="11999999999",password="strong-synthetic-password",document_id=doc,
        )
    assert db.execute(
        "SELECT count(*) FROM public.contract_acceptances WHERE user_id=%s",(person,),
    ).fetchone()[0]==1


def test_registration_disallows_contract_mismatch_and_revoked_sender(base_ci):
    db,u=base_ci
    required=_document(db,"TENANT_MEMBERSHIP","ci-required-"+str(uuid4()))
    different=_document(db,"TENANT_MEMBERSHIP","ci-other-"+str(uuid4()))
    inv,_=prepare_invitation_ci(
        db,tenant_id=u['tenant'],inviter_id=u['admin'],
        recipient_email="another.member@example.com",target_role="TENANT_MEMBER",
    )
    db.execute(
        "UPDATE public.invitations SET required_document_id=%s WHERE id=%s",
        (required,inv),
    )
    assert simulate_invitation_delivery_ci(db,inv)
    token=prepare_invite_email_verification_ci(db,invitation_id=inv)
    with pytest.raises(LifecycleDenied):
        register_new_invited_identity_ci(
            db,verification_token=token,name="Pessoa Dois",cpf="52998224725",
            phone="11999999999",password="strong-synthetic-password",document_id=different,
        )
    db.execute(
        "UPDATE public.memberships SET status='SUSPENSA' WHERE tenant_id=%s "
        "AND user_id=%s AND role='TENANT_ADMIN'",(u['tenant'],u['admin']),
    )
    with pytest.raises(LifecycleDenied):
        register_new_invited_identity_ci(
            db,verification_token=token,name="Pessoa Dois",cpf="52998224725",
            phone="11999999999",password="strong-synthetic-password",document_id=required,
        )
    assert db.execute(
        "SELECT count(*) FROM public.users WHERE cpf='52998224725'"
    ).fetchone()[0]==0


def test_only_reconciled_approved_exact_platform_payment_activates(base_ci):
    db,u=base_ci
    prep=_billing_fixture(db,u)
    intent=stage_saas_payment_ci(
        db,preparation_id=prep,platform_collector_id="12345",live_mode=False,
    )
    row=db.execute(
        "SELECT expected_amount_cents,external_reference,provider_payment_id "
        "FROM public.saas_payment_intents WHERE id=%s",(intent,),
    ).fetchone()
    assert row==(8990,f"saas:{intent}",None)
    with pytest.raises(LifecycleDenied):
        stage_saas_payment_ci(
            db,preparation_id=prep,platform_collector_id="12345",live_mode=False,
        )
    assert attach_mp_payment_identifier_ci(db,intent_id=intent,provider_payment_id="654321")
    assert not attach_mp_payment_identifier_ci(db,intent_id=intent,provider_payment_id="654321")
    for wrong in (
      _payment(intent,amount="89.91"),
      _payment(intent,collector="54321"),
      _payment(intent,live=True),
      _payment(intent,ref="saas:another"),
      _payment(intent,status="pending"),
    ):
        assert reconcile_approved_saas_payment_ci(
            db,intent_id=intent,authoritative_payment=wrong
        ) is None
    start=datetime(2026,11,1,20,tzinfo=timezone.utc)
    entitlement=reconcile_approved_saas_payment_ci(
        db,intent_id=intent,authoritative_payment=_payment(intent),now=start,
    )
    assert entitlement
    saved=db.execute(
        "SELECT status,valid_from,valid_until FROM public.saas_license_entitlements "
        "WHERE id=%s",(entitlement,),
    ).fetchone()
    assert saved==("ACTIVE",start,datetime(2026,12,1,20,tzinfo=timezone.utc))
    assert reconcile_approved_saas_payment_ci(
        db,intent_id=intent,authoritative_payment=_payment(intent),
        now=start+timedelta(days=4)
    )==entitlement
    # Nem uma cobrança já aprovada pode retornar autorização após GET divergente.
    assert reconcile_approved_saas_payment_ci(
        db,intent_id=intent,authoritative_payment=_payment(intent,amount="89.91"),
    ) is None
    assert db.execute(
        "SELECT count(*) FROM public.saas_license_entitlements "
        "WHERE payment_intent_id=%s",(intent,),
    ).fetchone()[0]==1
    assert not expire_saas_entitlement_ci(db,entitlement_id=entitlement,now=start)
    assert expire_saas_entitlement_ci(
        db,entitlement_id=entitlement,now=datetime(2026,12,1,20,tzinfo=timezone.utc)
    )


def test_annual_price_locked_and_verified_refund_revokes(base_ci):
    db,u=base_ci
    prep=_billing_fixture(db,u,period="ANNUAL")
    intent=stage_saas_payment_ci(
        db,preparation_id=prep,platform_collector_id="12345",live_mode=False,
    )
    assert db.execute(
        "SELECT expected_amount_cents FROM public.saas_payment_intents WHERE id=%s",
        (intent,),
    ).fetchone()[0]==89900
    attach_mp_payment_identifier_ci(db,intent_id=intent,provider_payment_id="654321")
    start=datetime(2026,11,1,20,tzinfo=timezone.utc)
    entitlement=reconcile_approved_saas_payment_ci(
        db,intent_id=intent,authoritative_payment=_payment(intent,amount="899.00"),
        now=start,
    )
    assert entitlement
    assert db.execute(
        "SELECT valid_until FROM public.saas_license_entitlements WHERE id=%s",
        (entitlement,),
    ).fetchone()[0]==datetime(2027,11,1,20,tzinfo=timezone.utc)
    assert not revoke_after_verified_refund_ci(
        db,intent_id=intent,
        authoritative_payment=_payment(intent,amount="899.01",status="refunded",refunded="899.01"),
    )
    assert not revoke_after_verified_refund_ci(
        db,intent_id=intent,
        authoritative_payment=_payment(intent,amount="899.00",status="refunded"),
    ), "Reembolso sem montante confirmado não revoga licença"
    assert not revoke_after_verified_refund_ci(
        db,intent_id=intent,
        authoritative_payment=_payment(intent,amount="899.00",status="refunded",refunded="10.00"),
    ), "Estorno parcial não equivale a reembolso integral"
    assert revoke_after_verified_refund_ci(
        db,intent_id=intent,
        authoritative_payment=_payment(intent,amount="899.00",status="refunded",refunded="899.00"),
    )
    assert db.execute(
        "SELECT status FROM public.saas_license_entitlements WHERE id=%s",
        (entitlement,),
    ).fetchone()[0]=="REVOKED"


def test_payment_staging_and_signup_cannot_run_outside_ci(monkeypatch,base_ci):
    db,u=base_ci
    monkeypatch.delenv("FRCAIXINHA_CI_ISOLATED",raising=False)
    with pytest.raises(LifecycleDenied):
        stage_saas_payment_ci(
            db,preparation_id=uuid4(),platform_collector_id="12345",live_mode=False,
        )
    with pytest.raises(LifecycleDenied):
        prepare_invite_email_verification_ci(db,invitation_id=uuid4())



def test_verified_webhook_deduplicates_without_activating_a_license(base_ci):
    db,u=base_ci
    prep=_billing_fixture(db,u)
    intent=stage_saas_payment_ci(
        db,preparation_id=prep,platform_collector_id="12345",live_mode=False,
    )
    assert record_verified_saas_webhook_ci(
        db,provider_payment_id="654321",request_id="req-ci-1",
        timestamp=1793570400,payload=b'{"data":{"id":"654321"}}',
        valid_signature=True,
    )
    assert not record_verified_saas_webhook_ci(
        db,provider_payment_id="654321",request_id="req-ci-1",
        timestamp=1793570400,payload=b'{"data":{"id":"654321"}}',
        valid_signature=True,
    )
    with pytest.raises(LifecycleDenied):
        record_verified_saas_webhook_ci(
            db,provider_payment_id="654321",request_id="req-ci-1",
            timestamp=1793570400,payload=b'{"data":{"id":"654322"}}',
            valid_signature=True,
        )
    with pytest.raises(LifecycleDenied):
        record_verified_saas_webhook_ci(
            db,provider_payment_id="654321",request_id="req-ci-2",
            timestamp=1793570400,payload=b'{}',valid_signature=False,
        )
    assert db.execute(
        "SELECT count(*) FROM public.saas_license_entitlements"
    ).fetchone()[0]==0
    assert db.execute(
        "SELECT status FROM public.saas_payment_intents WHERE id=%s",(intent,),
    ).fetchone()[0]=="PENDING"



def test_saas_master_suspension_resume_and_refund_are_audited(base_ci):
    db,u=base_ci
    prep=_billing_fixture(db,u)
    intent=stage_saas_payment_ci(db,preparation_id=prep,
        platform_collector_id="12345",live_mode=False)
    assert attach_mp_payment_identifier_ci(db,intent_id=intent,
        provider_payment_id="654321")
    start=datetime(2026,11,1,20,tzinfo=timezone.utc)
    license_id=reconcile_approved_saas_payment_ci(
        db,intent_id=intent,authoritative_payment=_payment(intent),now=start)
    assert license_id
    with pytest.raises(LifecycleDenied):
        suspend_saas_entitlement_ci(db,entitlement_id=license_id,
            master_user_id=u['admin'],reason="Teste de seguranca sintetico",
            now=start+timedelta(days=1))
    with pytest.raises(LifecycleDenied):
        suspend_saas_entitlement_ci(db,entitlement_id=license_id,
            master_user_id=u['master'],reason="curto",
            now=start+timedelta(days=1))
    assert suspend_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],reason="Suspensao de auditoria do SaaS",
        now=start+timedelta(days=1))
    assert not suspend_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],reason="Repeticao nao permitida em CI",
        now=start+timedelta(days=1))
    assert db.execute(
        "SELECT status FROM public.saas_license_entitlements WHERE id=%s",
        (license_id,)).fetchone()[0]=="SUSPENDED"
    assert not resume_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],
        authoritative_payment=_payment(intent,status="pending"),
        now=start+timedelta(days=2))
    assert resume_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],authoritative_payment=_payment(intent),
        now=start+timedelta(days=2))
    assert not resume_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],authoritative_payment=_payment(intent),
        now=start+timedelta(days=2))
    saved=db.execute(
        "SELECT status,valid_from,valid_until,suspended_at "
        "FROM public.saas_license_entitlements WHERE id=%s",(license_id,)
    ).fetchone()
    assert saved==("ACTIVE",start,
        datetime(2026,12,1,20,tzinfo=timezone.utc),None)
    assert suspend_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],reason="Suspensao antes do estorno total",
        now=start+timedelta(days=3))
    assert revoke_after_verified_refund_ci(
        db,intent_id=intent,authoritative_payment=_payment(
            intent,status="refunded",refunded="89.90"))
    assert db.execute(
        "SELECT status FROM public.saas_license_entitlements WHERE id=%s",
        (license_id,)).fetchone()[0]=="REVOKED"
    assert not resume_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],authoritative_payment=_payment(intent),
        now=start+timedelta(days=4))
    assert db.execute(
        "SELECT count(*) FROM public.audit_events WHERE object_id=%s "
        "AND action IN ('CI_SAAS_SUSPENDED','CI_SAAS_RESUMED','CI_SAAS_REFUND_REVOKED')",
        (str(license_id),)).fetchone()[0]>=3


def test_suspended_entitlement_expires_without_grace_period(base_ci):
    db,u=base_ci
    prep=_billing_fixture(db,u)
    intent=stage_saas_payment_ci(db,preparation_id=prep,
        platform_collector_id="12345",live_mode=False)
    attach_mp_payment_identifier_ci(db,intent_id=intent,provider_payment_id="654321")
    start=datetime(2026,11,1,20,tzinfo=timezone.utc)
    license_id=reconcile_approved_saas_payment_ci(
        db,intent_id=intent,authoritative_payment=_payment(intent),now=start)
    assert suspend_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],reason="Suspensao por teste de vencimento",
        now=start+timedelta(days=2))
    expires=datetime(2026,12,1,20,tzinfo=timezone.utc)
    assert not resume_saas_entitlement_ci(db,entitlement_id=license_id,
        master_user_id=u['master'],authoritative_payment=_payment(intent),now=expires)
    assert expire_saas_entitlement_ci(db,entitlement_id=license_id,now=expires)
    assert db.execute(
        "SELECT status FROM public.saas_license_entitlements WHERE id=%s",
        (license_id,)).fetchone()[0]=="EXPIRED"
