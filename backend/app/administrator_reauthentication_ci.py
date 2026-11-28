"""M41460: segregated verifier/issuer for the canonical disposable CI only.
Uses existing SQL 023/026/027 and PG18 test logins. The owner connection
attests the synthetic entitlement, never verifies a password or issues a
session. The cross-connection guard is a CI composition, not a production
authorization boundary or a substitute for independent key custody.
"""
from datetime import datetime,timezone
from hashlib import sha256
import psycopg
from .account_lifecycle import LifecycleDenied,_email
from .cycle_identity_registration_ci import _guard
from .preliminary_onboarding_ci import _binding,_rate_key
from .admin_license_onboarding_ci import _session
from .onboarding_readback_ci import _document
from .preliminary_token_ci import is_preliminary
from .security import generate_session_token,verify_password_secure

def _role_connection(owner,role):
    _guard(owner)
    if role not in ("frcaixinha_pg18_auth","frcaixinha_pg18_verifier"):
        raise LifecycleDenied("Papel CI incompatível.")
    c=psycopg.connect(host="127.0.0.1",port=5432,dbname="frcaixinha_ci",user=role,
                      password="ci-test-only",autocommit=True)
    try:
        row=c.execute("SELECT current_database(),current_user,inet_server_port(),"
                      "current_setting('server_version_num')::int BETWEEN 180000 AND 189999,"
                      "rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user").fetchone()
        if row!=("frcaixinha_ci",role,5432,True,False,False):
            raise LifecycleDenied("Identidade técnica CI incompatível.")
        return c
    except BaseException:
        c.close()
        raise

def _verified_identity(verifier,email,password):
    row=verifier.execute("SELECT u.id,u.status,u.is_master,c.password_hash FROM public.users u "
                         "JOIN public.credentials c ON c.user_id=u.id WHERE lower(u.email)=%s",(email,)).fetchone()
    if not row or row[1]!="ACTIVE" or row[2] or not verify_password_secure(password,row[3]):
        return None
    return row[0],sha256(row[3].encode()).hexdigest()

def _proof(verifier,actor,fingerprint):
    raw,digest=generate_session_token()
    verifier.execute("INSERT INTO public.auth_login_proofs(proof_hash,user_id,credential_fingerprint,expires_at) "
                     "VALUES(%s,%s,%s,now()+interval '60 seconds')",(digest,actor,fingerprint))
    return raw

def _issue(issuer,actor,tenant,proof,key):
    raw,_=generate_session_token()
    with issuer.transaction():
        if not issuer.execute("SELECT public.auth_issue_pending_session(%s,%s,%s)",(actor,raw,proof)).fetchone()[0]:
            raise LifecycleDenied("Prova de autenticação indisponível.")
        links=issuer.execute("SELECT tenant_id,role FROM public.auth_active_memberships(%s)",(raw,)).fetchall()
        if links.count((tenant,"TENANT_ADMIN"))!=1:
            raise LifecycleDenied("Vínculo indisponível.")
        expiry=issuer.execute("SELECT public.auth_promote_pending_session(%s,'TENANT_ADMIN'::varchar,%s)",(raw,tenant)).fetchone()[0]
        if expiry is None or not issuer.execute("SELECT public.auth_login_rate_success(%s)",(key,)).fetchone()[0]:
            raise LifecycleDenied("Emissão indisponível.")
    return raw,expiry

def _license_access(owner,actor,tenant):
    """CI-only continuity login: exact historical paid A, never a new entitlement.

    The savepoint is necessary because the existing SQL function deliberately
    raises 42501 for missing/ambiguous entitlement. Never suppress other errors.
    A current but inconsistent entitlement does not fall back to continuity.
    """
    acceptance,status=_binding(owner,actor,tenant)
    if status!="ATIVO":
        raise LifecycleDenied("Licença inicial não conciliada.")
    try:
        with owner.transaction():
            owner.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()
        return "CURRENT"
    except psycopg.errors.InsufficientPrivilege:
        pass
    current=owner.execute(
        "SELECT e.id FROM public.saas_license_entitlements e WHERE e.tenant_id=%s "
        "AND e.status='ACTIVE' AND e.valid_from<=clock_timestamp() AND e.valid_until>clock_timestamp() FOR SHARE",
        (tenant,)).fetchall()
    if current:
        raise LifecycleDenied("Licença atual inconsistente.")
    history=owner.execute(
        "SELECT e.id FROM public.saas_license_entitlements e "
        "JOIN public.saas_subscription_preparations s ON s.id=e.preparation_id "
        "JOIN public.saas_payment_intents p ON p.id=e.payment_intent_id AND p.preparation_id=s.id "
        "JOIN public.platform_license_price_versions v ON v.id=s.price_version_id AND v.plan_tier=s.plan_tier "
        "WHERE e.tenant_id=%s AND s.tenant_id=e.tenant_id AND p.tenant_id=e.tenant_id "
        "AND s.admin_user_id=%s AND p.admin_user_id=s.admin_user_id AND s.contract_acceptance_id=%s "
        "AND e.plan_tier=s.plan_tier AND p.price_version_id=v.id "
        "AND p.provider='MERCADO_PAGO' AND p.currency='BRL' AND p.live_mode=false "
        "AND (p.status='APPROVED' OR (p.status='REFUNDED' AND e.status='REVOKED' AND EXISTS("
        "SELECT 1 FROM public.audit_events au WHERE au.tenant_id=e.tenant_id AND au.object_id=p.id::text "
        "AND au.action='CI_SAAS_REFUND_REVOKED' AND au.evidence_ref=p.provider_payment_id))) "
        "AND p.provider_payment_id IS NOT NULL AND p.paid_at IS NOT NULL "
        "AND p.reconciled_at>=p.paid_at AND p.reconciled_at<=clock_timestamp() "
        "AND p.expected_amount_cents=(CASE s.billing_period WHEN 'MONTHLY' THEN v.monthly_price ELSE v.annual_price END)*100 "
        "AND e.valid_from<=clock_timestamp() AND (e.status='SUSPENDED' OR e.status='REVOKED' "
        "OR (e.status IN ('ACTIVE','EXPIRED') AND e.valid_until<=clock_timestamp())) "
        "FOR SHARE OF e,s,p,v",(tenant,actor,acceptance)).fetchall()
    if not history:
        raise LifecycleDenied("Histórico conciliado indisponível.")
    return "CONTINUITY_ONLY"

def reauthenticate_admin_ci(owner,*,email,password,tenant):
    _guard(owner)
    email=_email(email)
    if not email.endswith("@example.invalid") or type(password) is not str or not 12<=len(password)<=256:
        raise LifecycleDenied("Credenciais indisponíveis.")
    key=_rate_key(email)
    with _role_connection(owner,"frcaixinha_pg18_auth") as issuer, _role_connection(owner,"frcaixinha_pg18_verifier") as verifier:
        with owner.transaction():
            # Reuse M41450 shared rate namespace and serialization.
            owner.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,41450))",(key,))
            if issuer.execute("SELECT public.auth_login_rate_check(%s)",(key,)).fetchone()[0]!=0:
                raise LifecycleDenied("Credenciais indisponíveis.")
            identity=_verified_identity(verifier,email,password)
            if identity is None:
                issuer.execute("SELECT public.auth_login_rate_failure(%s)",(key,)).fetchone()
                raise LifecycleDenied("Credenciais indisponíveis.")
            actor,fingerprint=identity
            # Protect lock state and credential rotation until issuer commit.
            cred=owner.execute("SELECT locked_until FROM public.credentials WHERE user_id=%s FOR SHARE",(actor,)).fetchone()
            if not cred or (cred[0] is not None and cred[0]>datetime.now(timezone.utc)):
                raise LifecycleDenied("Credenciais indisponíveis.")
            # Exact invitation, A, payer, preparation, reconciled entitlement and
            # current tenant/membership. SHARE locks held through issuance.
            _license_access(owner,actor,tenant)
            proof=_proof(verifier,actor,fingerprint)
            raw,expiry=_issue(issuer,actor,tenant,proof,key)
            return dict(session_token=raw,expires_at=expiry,user_id=actor,tenant_id=tenant,
                        role="TENANT_ADMIN",ci_only=True,production_authorized=False)

def administrator_readiness_ci(owner,token,tenant,document_id):
    _guard(owner)
    if is_preliminary(token):
        raise LifecycleDenied("Nova autenticação necessária.")
    with owner.transaction():
        actor,_=_session(owner,token,"TENANT_ADMIN",tenant)
        access=_license_access(owner,actor,tenant)
        doc=_document(owner,document_id,"TENANT_MEMBERSHIP")
        accepted=owner.execute("SELECT a.id FROM public.contract_acceptances a JOIN public.contract_documents d "
                               "ON d.id=a.document_id WHERE a.user_id=%s AND a.tenant_id=%s AND a.document_id=%s "
                               "AND a.document_kind='TENANT_MEMBERSHIP' AND a.accepted_at>=d.published_at FOR SHARE OF a,d",
                               (actor,tenant,document_id)).fetchall()
        if len(accepted)>1:raise LifecycleDenied("Aceite ambíguo.")
        if access=="CONTINUITY_ONLY" and not accepted:
            raise LifecycleDenied("Novo aceite B exige licença vigente.")
        state="CONTINUITY_ONLY" if access=="CONTINUITY_ONLY" else ("CYCLE_CONFIGURATION" if accepted else "CONTRACT_B_REQUIRED")
        return dict(user_id=actor,tenant_id=tenant,role="TENANT_ADMIN",
                    state=state,
                    document=doc,acceptance_id=accepted[0][0] if accepted else None,
                    ci_only=True,production_authorized=False)

def administrator_logout_ci(owner,token,tenant):
    _guard(owner)
    if is_preliminary(token):raise LifecycleDenied("Sessão incompatível.")
    with _role_connection(owner,"frcaixinha_pg18_auth") as issuer:
        # Scope and expiry check via owner transaction, then exact token revoke.
        # Do not retain a session SHARE lock across the issuer UPDATE.
        with owner.transaction():
            _session(owner,token,"TENANT_ADMIN",tenant)
        if not issuer.execute("SELECT public.auth_revoke_session(%s)",(token,)).fetchone()[0]:
            raise LifecycleDenied("Sessão indisponível.")
    return dict(revoked=True,ci_only=True)
