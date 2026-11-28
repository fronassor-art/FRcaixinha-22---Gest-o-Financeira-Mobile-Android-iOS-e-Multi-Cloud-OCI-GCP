"""M41450: restricted preliminary credential and resumable contracting journey.
Only the existing isolated CI adapter may invoke this module. No runtime
executor; no new schema, roles, provider traffic or ordinary auth issuance.
"""
from datetime import datetime,timezone
from hashlib import sha256
import hmac,secrets
from .account_lifecycle import LifecycleDenied,_email
from .cycle_identity_registration_ci import _guard
from .admin_license_onboarding_ci import _session
from .preliminary_token_ci import MARKER,PREFIX,preliminary_digest,is_preliminary
from .security import verify_password_secure

def _rate_key(email):
    # Fixed synthetic CI domain; production needs the existing secret custodian.
    return hmac.new(b"FR_FINANCE_M41450_SYNTHETIC_FIXTURE_ONLY",email.encode(),sha256).hexdigest()

def _binding(conn,actor,tenant):
    rows=conn.execute(
        "SELECT a.id,t.status FROM public.tenants t "
        "JOIN public.invitations i ON i.tenant_id=t.id AND i.accepted_user_id=t.admin_user_id "
        "JOIN public.fr_v23_admin_invite_bindings b ON b.invitation_id=i.id "
        "JOIN public.contract_acceptances a ON a.document_id=b.document_id AND a.user_id=t.admin_user_id "
        "JOIN public.contract_documents d ON d.id=a.document_id AND d.sha256=b.document_hash "
        "JOIN public.users u ON u.id=t.admin_user_id "
        "JOIN public.memberships m ON m.id=i.accepted_membership_id AND m.tenant_id=t.id AND m.user_id=u.id "
        "WHERE t.id=%s AND t.admin_user_id=%s AND t.status IN ('RASCUNHO_INATIVO','ATIVO') "
        "AND i.target_role='TENANT_ADMIN' AND i.accepted_at IS NOT NULL AND i.revoked_at IS NULL "
        "AND lower(i.target_email)=lower(u.email) AND u.status='ACTIVE' AND NOT u.is_master "
        "AND u.email_verified_at IS NOT NULL AND m.role='TENANT_ADMIN' AND m.status='ATIVA' "
        "AND a.tenant_id IS NULL AND a.document_kind='PLATFORM_LICENSE' "
        "AND d.document_kind='PLATFORM_LICENSE' AND d.published_at IS NOT NULL "
        "AND a.accepted_at>=d.published_at FOR SHARE OF t,i,b,a,d,u,m",(tenant,actor)).fetchall()
    if len(rows)!=1:raise LifecycleDenied("Jornada indisponível.")
    return rows[0]

def _journey(conn,actor,tenant):
    acceptance,status=_binding(conn,actor,tenant)
    rows=conn.execute(
        "SELECT p.id,p.status,p.live_mode,p.expected_amount_cents,s.billing_period "
        "FROM public.saas_subscription_preparations s JOIN public.saas_payment_intents p ON p.preparation_id=s.id "
        "WHERE s.tenant_id=%s AND s.admin_user_id=%s AND s.contract_acceptance_id=%s AND s.renewal_request_id IS NULL "
        "AND p.tenant_id=s.tenant_id AND p.admin_user_id=s.admin_user_id AND p.price_version_id=s.price_version_id "
        "FOR SHARE OF s,p",(tenant,actor,acceptance)).fetchall()
    if len(rows)>1:raise LifecycleDenied("Jornada ambígua.")
    if status=="RASCUNHO_INATIVO" and not rows:
        state="SELECT_OFFER";intent=cents=period=None
    elif len(rows)==1 and rows[0][2] is False:
        intent,payment,_,cents,period=rows[0]
        if status=="RASCUNHO_INATIVO" and payment=="PENDING":
            state="PAYMENT_PENDING"
        elif status=="ATIVO" and payment=="APPROVED":
            conn.execute("SELECT * FROM public.fr_v23_license(%s,%s)",(tenant,actor)).fetchone()
            state="REAUTH_REQUIRED"
        else:raise LifecycleDenied("Jornada inconsistente.")
    else:raise LifecycleDenied("Jornada inconsistente.")
    return dict(user_id=actor,tenant_id=tenant,role="TENANT_ADMIN",state=state,
                intent_id=intent,cents=cents,period=period,ci_only=True,operational_access=False)

def login_preliminary_ci(conn,*,email,password):
    _guard(conn)
    email=_email(email)
    if not email.endswith("@example.invalid") or type(password) is not str or not 12<=len(password)<=256:
        raise LifecycleDenied("Credenciais indisponíveis.")
    key=_rate_key(email)
    result=None
    with conn.transaction():
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,41450))",(key,))
        if conn.execute("SELECT public.auth_login_rate_check(%s)",(key,)).fetchone()[0]!=0:
            raise LifecycleDenied("Credenciais indisponíveis.")
        rows=conn.execute(
            "SELECT u.id,t.id,c.password_hash,c.locked_until FROM public.users u "
            "JOIN public.credentials c ON c.user_id=u.id JOIN public.tenants t ON t.admin_user_id=u.id "
            "WHERE lower(u.email)=%s AND u.status='ACTIVE' AND NOT u.is_master "
            "AND u.email_verified_at IS NOT NULL AND t.status IN ('RASCUNHO_INATIVO','ATIVO') "
            "FOR SHARE OF u,c,t",(email,)).fetchall()
        row=rows[0] if len(rows)==1 else None
        if not row or (row[3] is not None and row[3]>datetime.now(timezone.utc)) or not verify_password_secure(password,row[2]):
            conn.execute("SELECT public.auth_login_rate_failure(%s)",(key,)).fetchone()
        else:
            actor,tenant=row[:2]
            journey=_journey(conn,actor,tenant)
            raw=PREFIX+secrets.token_urlsafe(32)
            # Only supersede prior preliminary CI rows, never normal sessions.
            conn.execute("UPDATE public.sessions SET revoked_at=now() WHERE user_id=%s AND active_tenant_id=%s "
                         "AND user_agent=%s AND revoked_at IS NULL",(actor,tenant,MARKER))
            expires=conn.execute("INSERT INTO public.sessions(token_hash,user_id,active_role,active_tenant_id,expires_at,user_agent) "
                         "VALUES(%s,%s,'TENANT_ADMIN',%s,now()+interval '10 minutes',%s) RETURNING expires_at",
                         (preliminary_digest(raw),actor,tenant,MARKER)).fetchone()[0]
            if not conn.execute("SELECT public.auth_login_rate_success(%s)",(key,)).fetchone()[0]:
                raise LifecycleDenied("Credenciais indisponíveis.")
            result=dict(preliminary_token=raw,expires_at=expires,journey=journey)
    # Commit failed-attempt evidence before rejecting the login.
    if result is None:raise LifecycleDenied("Credenciais indisponíveis.")
    return result

def journey_ci(conn,token,tenant):
    _guard(conn)
    if not is_preliminary(token):raise LifecycleDenied("Sessão preliminar necessária.")
    with conn.transaction():
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant,draft=True,preliminary_reconciled=True)
        return _journey(conn,actor,tenant)

def logout_preliminary_ci(conn,token,tenant):
    _guard(conn)
    if not is_preliminary(token):raise LifecycleDenied("Sessão preliminar necessária.")
    with conn.transaction():
        # Avoid SHARE -> UPDATE conversion race on concurrent logout.
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,41451))",(token,))
        actor,_=_session(conn,token,"TENANT_ADMIN",tenant,draft=True,preliminary_reconciled=True)
        row=conn.execute("UPDATE public.sessions SET revoked_at=now() WHERE token_hash=%s AND user_id=%s "
                         "AND active_tenant_id=%s AND user_agent=%s AND revoked_at IS NULL RETURNING id",
                         (preliminary_digest(token),actor,tenant,MARKER)).fetchone()
        if not row:raise LifecycleDenied("Sessão preliminar indisponível.")
        return dict(revoked=True,ci_only=True)
