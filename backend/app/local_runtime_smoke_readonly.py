"""FR Finance M37381-M37400: deterministic localhost GET smoke, never activate users.

This is a point-in-time read-only E2E contract probe, not a login flow,
tenant isolation proof, notification send test or deployment authorization.
No credentials, cookies, SQL, or payments are sent.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import http.client
import json

HOST="127.0.0.1"
PORT=8000
MAX_BYTES=8192
REQUESTS=(
    ("HEALTH","/api/health"),
    ("READY","/api/health/ready"),
    ("INBOX","/api/health/features/m19000"),
    ("FEATURES","/api/health/features"),
    ("AUTH_STATUS","/api/v1/auth/status"),
    ("ANON_ME","/api/v1/auth/me"),
    ("ANON_NOTIFICATIONS","/api/v1/notifications/capabilities"),
    ("ANON_NOTIFICATION_READINESS","/api/v1/notifications/readiness"),
)
PATHS=frozenset(path for _,path in REQUESTS)

class LocalSmokeBlocked(ValueError):
    """Emit only allowlisted, non-sensitive reason codes."""

def local_get(path:str)->tuple[int,dict]:
    """Explicit localhost target and read-only method, with no redirects/cookies."""
    if type(path) is not str or path not in PATHS:
        raise LocalSmokeBlocked("LOCAL_SMOKE_PATH_DENIED")
    connection=http.client.HTTPConnection(HOST,PORT,timeout=5)
    try:
        connection.request(
            "GET",path,
            headers={"Accept":"application/json","Cache-Control":"no-store",
                     "User-Agent":"FRFinance-M37400-Readonly"},
        )
        response=connection.getresponse()
        status=response.status
        data=response.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:
            raise LocalSmokeBlocked("LOCAL_SMOKE_RESPONSE_TOO_LARGE")
        if type(status) is not int or status<100 or status>599:
            raise LocalSmokeBlocked("LOCAL_SMOKE_HTTP_INVALID")
        if status in (401,403):
            return status,{}
        if status!=200:
            raise LocalSmokeBlocked("LOCAL_SMOKE_UNEXPECTED_HTTP")
        try:
            body=json.loads(data)
        except (UnicodeError,ValueError,TypeError):
            raise LocalSmokeBlocked("LOCAL_SMOKE_JSON_INVALID") from None
        if type(body) is not dict or len(body)>100:
            raise LocalSmokeBlocked("LOCAL_SMOKE_JSON_SCHEMA_INVALID")
        return status,body
    except LocalSmokeBlocked:
        raise
    except (OSError,http.client.HTTPException,TimeoutError):
        raise LocalSmokeBlocked("LOCAL_SMOKE_CONNECTION_FAILED") from None
    finally:
        connection.close()


@dataclass(frozen=True)
class SmokeResult:
    validated_endpoints:int
    identity_ok:bool
    database_roles_ok:bool
    inbox_ok:bool
    feature_gates_ok:bool
    auth_sandbox_ok:bool
    anonymous_me_denied:bool
    anonymous_notifications_denied:bool
    anonymous_notification_readiness_denied:bool
    no_writes_performed:bool=True
    user_activation_authorized:bool=False
    payment_activation_authorized:bool=False
    production_deployment_authorized:bool=False

def check_local_smoke(get:Callable[[str],tuple[int,dict]])->SmokeResult:
    rows={}
    for label,path in REQUESTS:
        try:
            value=get(path)
        except LocalSmokeBlocked:
            raise
        except Exception:
            raise LocalSmokeBlocked("LOCAL_SMOKE_REQUEST_FAILED") from None
        if type(value) not in (tuple,list) or len(value)!=2:
            raise LocalSmokeBlocked("LOCAL_SMOKE_RESPONSE_SCHEMA_INVALID")
        status,body=value
        if type(status) is not int or type(body) is not dict:
            raise LocalSmokeBlocked("LOCAL_SMOKE_RESPONSE_SCHEMA_INVALID")
        if label.startswith("ANON_"):
            if status not in (401,403):
                raise LocalSmokeBlocked("LOCAL_SMOKE_ANONYMOUS_ACCESS_NOT_DENIED")
            rows[label]=True
        else:
            if status!=200:
                raise LocalSmokeBlocked("LOCAL_SMOKE_REQUIRED_ENDPOINT_UNREADY")
            rows[label]=body
    health=rows["HEALTH"]
    ready=rows["READY"]
    inbox=rows["INBOX"]
    features=rows["FEATURES"]
    auth=rows["AUTH_STATUS"]
    if not (health.get("status")=="ONLINE"
            and health.get("app")=="FR Finance"
            and health.get("database_configured") is True):
        raise LocalSmokeBlocked("LOCAL_SMOKE_WRONG_BACKEND")
    if not (ready.get("status")=="READY_FOR_TEST_AUTH"
            and ready.get("scope")=="LOCAL_HOMOLOGATION_ONLY"):
        raise LocalSmokeBlocked("LOCAL_SMOKE_DATABASE_NOT_READY")
    if not (inbox.get("workstream")=="AI_STUDIO"
            and inbox.get("contract")=="AI_STUDIO_M19000_LOCAL_IN_APP_NOTIFICATIONS_V1"
            and all(inbox.get(flag) is True for flag in (
                "local_notification_flag_configured",
                "local_inbox_schema_verified","local_in_app_ready"
            ))
            and all(inbox.get(flag) is False for flag in (
                "external_email_active","external_push_active",
                "external_whatsapp_active","provider_events_authenticated",
                "real_payments_enabled","bank_reconciled","ledger_written",
                "financial_closing_authorized","payout_authorized",
                "oci_staging_deployed",
            ))):
        raise LocalSmokeBlocked("LOCAL_SMOKE_INBOX_NOT_LOCAL_ONLY")
    if not (features.get("product")=="FR Finance"
            and features.get("workstream")=="AI_STUDIO"
            and all(features.get(flag) is False for flag in (
                "real_payments_enabled","bank_reconciled",
                "financial_closing_authorized","master_tenant_ledger_allowed",
            ))):
        raise LocalSmokeBlocked("LOCAL_SMOKE_FINANCIAL_GATES_UNSAFE")
    if not (auth.get("status")=="TEST_MODE"
            and auth.get("configured") is True
            and auth.get("provider")=="POSTGRES_TEST"
            and auth.get("requires_authentication") is True):
        raise LocalSmokeBlocked("LOCAL_SMOKE_AUTH_NOT_SANDBOX")
    return SmokeResult(
        validated_endpoints=len(REQUESTS),
        identity_ok=True,database_roles_ok=True,
        inbox_ok=True,feature_gates_ok=True,auth_sandbox_ok=True,
        anonymous_me_denied=rows["ANON_ME"],
        anonymous_notifications_denied=rows["ANON_NOTIFICATIONS"],
        anonymous_notification_readiness_denied=rows["ANON_NOTIFICATION_READINESS"],
    )

def format_smoke(result:SmokeResult)->tuple[str,...]:
    if not isinstance(result,SmokeResult) or result.validated_endpoints!=len(REQUESTS):
        raise LocalSmokeBlocked("LOCAL_SMOKE_REPORT_INVALID")
    signals=(
        ("BACKEND_IDENTITY",result.identity_ok),
        ("PG_AUTH_READINESS",result.database_roles_ok),
        ("INBOX_LOCAL",result.inbox_ok),
        ("FINANCIAL_GATES",result.feature_gates_ok),
        ("AUTH_SANDBOX",result.auth_sandbox_ok),
        ("UNAUTH_ME_DENIED",result.anonymous_me_denied),
        ("UNAUTH_NOTIFICATIONS_DENIED",result.anonymous_notifications_denied),
        ("UNAUTH_NOTICE_READINESS_DENIED",result.anonymous_notification_readiness_denied),
    )
    if any(value is not True for _,value in signals):
        raise LocalSmokeBlocked("LOCAL_SMOKE_REPORT_INVALID")
    if (result.no_writes_performed is not True or result.user_activation_authorized
            or result.payment_activation_authorized or result.production_deployment_authorized):
        raise LocalSmokeBlocked("LOCAL_SMOKE_REPORT_INVALID")
    return (
        "=== FR FINANCE M37400 LOCAL E2E READ ONLY ===",
        "M37400_SMOKE=PASS",
        "M37400_ENDPOINTS="+str(result.validated_endpoints),
        *(f"M37400_{name}=PASS" for name,_ in signals),
        "M37400_HTTP_METHODS=GET_ONLY",
        "M37400_DB_WRITES=NONE",
        "M37400_USER_ACTIVATION=OFF",
        "M37400_MERCADO_PAGO_REAL=OFF",
        "M37400_PIX_REAL=OFF",
        "M37400_PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED",
        "M37400_REAL_LOGIN_FLOW=NOT_TESTED",
        "M37400_NOTIFICATIONS_SENT=NO",
        "M37400_TENANT_ISOLATION_E2E=NOT_TESTED",
    )
