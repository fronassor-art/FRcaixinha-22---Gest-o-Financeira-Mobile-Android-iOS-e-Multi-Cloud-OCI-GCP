"""FR Finance M37401–M37420 — LOCAL negative session controls, GET only.

Never creates users or tests a real login. Only synthetic invalid Bearer tokens
or role-spoofed headers are sent to localhost. No response body from protected
routes is returned or printed; a 2xx/redirect is treated as unsafe.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import http.client
import json

HOST = "127.0.0.1"
PORT = 8000
MAX_BODY = 4096
SYNTHETIC_UNRECOGNIZED_TOKEN = "frfinance-m37420-never-issued-test-token-000000000000000000000000"
CONTROL_PATHS = (
    "/api/health",
    "/api/health/ready",
    "/api/v1/auth/status",
)
PROTECTED_PATHS = (
    "/api/v1/auth/me",
    "/api/v1/auth/contexts",
    "/api/v1/auth/sessions",
    "/api/v1/notifications/capabilities",
    "/api/v1/notifications/readiness",
    "/api/v1/notifications?limit=1",
)
MODES = ("ROLE_HEADERS_ONLY", "INVALID_BEARER")
ALLOWED = frozenset(CONTROL_PATHS + PROTECTED_PATHS)

class SessionBoundaryBlocked(ValueError):
    """Only constant, sanitized codes, without response or provider details."""


@dataclass(frozen=True)
class SessionBoundaryReport:
    controls: int
    protected_routes: int
    negative_checks: int
    controls_verified: bool = True
    role_headers_denied: bool = True
    forged_bearer_denied: bool = True
    real_login_tested: bool = False
    synthetic_account_created: bool = False
    sql_writes_requested: bool = False
    production_deployment_authorized: bool = False
    real_users_authorized: bool = False
    real_pix_authorized: bool = False


def local_request(path: str, mode: str) -> tuple[int,dict]:
    """One fully fixed local GET with no redirect following or environment secrets."""
    if type(path) is not str or path not in ALLOWED:
        raise SessionBoundaryBlocked("M37420_PATH_DENIED")
    if (mode == "CONTROL" and path not in CONTROL_PATHS) or (
        mode in MODES and path not in PROTECTED_PATHS
    ) or mode not in (*MODES, "CONTROL"):
        raise SessionBoundaryBlocked("M37420_METHOD_SCOPE_DENIED")
    headers = {
        "Accept": "application/json",
        "Cache-Control": "no-store",
        "User-Agent": "FRFinance-M37420-Local-Readonly",
    }
    if mode == "ROLE_HEADERS_ONLY":
        headers.update({
            "X-User-Role": "MASTER",
            "X-Role": "TENANT_ADMIN",
            "X-User-Id": "00000000-0000-4000-8000-000000000001",
            "X-Tenant-Id": "00000000-0000-4000-8000-000000000002",
        })
    elif mode == "INVALID_BEARER":
        headers["Authorization"] = "Bearer " + SYNTHETIC_UNRECOGNIZED_TOKEN
    conn = http.client.HTTPConnection(HOST, PORT, timeout=6)
    try:
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        status = response.status
        payload = response.read(MAX_BODY + 1)
        if len(payload) > MAX_BODY:
            raise SessionBoundaryBlocked("M37420_RESPONSE_TOO_LARGE")
        if type(status) is not int or not 100 <= status <= 599:
            raise SessionBoundaryBlocked("M37420_HTTP_SCHEMA_DENIED")
        if mode != "CONTROL":
            # Ignore all protected-route response content: do not log PII.
            return status, {}
        if status != 200:
            return status, {}
        try:
            data = json.loads(payload)
        except (ValueError,UnicodeError,TypeError):
            raise SessionBoundaryBlocked("M37420_CONTROL_JSON_DENIED") from None
        if type(data) is not dict or len(data) > 100:
            raise SessionBoundaryBlocked("M37420_CONTROL_SCHEMA_DENIED")
        return status, data
    except SessionBoundaryBlocked:
        raise
    except (OSError, TimeoutError, http.client.HTTPException):
        raise SessionBoundaryBlocked("M37420_LOCAL_CONNECTION_FAILED") from None
    finally:
        conn.close()


def assess_session_boundaries(
    request: Callable[[str,str],tuple[int,dict]]
) -> SessionBoundaryReport:
    """Static sequence, no usernames or secrets; require denials for every private path."""
    controls = {}
    for path in CONTROL_PATHS:
        try:
            result = request(path, "CONTROL")
        except SessionBoundaryBlocked:
            raise
        except Exception:
            raise SessionBoundaryBlocked("M37420_CONTROL_READ_FAILED") from None
        if (type(result) not in (tuple,list) or len(result) != 2
                or type(result[0]) is not int or result[0] != 200
                or type(result[1]) is not dict):
            raise SessionBoundaryBlocked("M37420_CONTROL_NOT_READY")
        controls[path] = result[1]
    health, ready, auth = (controls[p] for p in CONTROL_PATHS)
    if (health.get("app") != "FR Finance"
            or health.get("status") != "ONLINE"
            or health.get("database_configured") is not True):
        raise SessionBoundaryBlocked("M37420_WRONG_LOCAL_BACKEND")
    if (ready.get("status") != "READY_FOR_TEST_AUTH"
            or ready.get("scope") != "LOCAL_HOMOLOGATION_ONLY"):
        raise SessionBoundaryBlocked("M37420_LOCAL_DB_AUTH_NOT_READY")
    if (auth.get("status") != "TEST_MODE"
            or auth.get("configured") is not True
            or auth.get("provider") != "POSTGRES_TEST"
            or auth.get("requires_authentication") is not True):
        raise SessionBoundaryBlocked("M37420_NOT_SANDBOX_AUTH")
    for mode in MODES:
        for path in PROTECTED_PATHS:
            try:
                response = request(path,mode)
            except SessionBoundaryBlocked:
                raise
            except Exception:
                raise SessionBoundaryBlocked("M37420_NEGATIVE_READ_FAILED") from None
            if (type(response) not in (tuple,list) or len(response) != 2
                    or type(response[0]) is not int
                    or response[0] != 401
                    or type(response[1]) is not dict
                    or response[1]):
                raise SessionBoundaryBlocked("M37420_UNAUTHORIZED_ACCESS_NOT_DENIED")
    return SessionBoundaryReport(
        controls=len(CONTROL_PATHS),
        protected_routes=len(PROTECTED_PATHS),
        negative_checks=len(PROTECTED_PATHS) * len(MODES),
    )


def format_session_boundary(report: SessionBoundaryReport) -> tuple[str,...]:
    if not isinstance(report,SessionBoundaryReport):
        raise SessionBoundaryBlocked("M37420_REPORT_INVALID")
    if (report.controls != len(CONTROL_PATHS)
            or report.protected_routes != len(PROTECTED_PATHS)
            or report.negative_checks != len(PROTECTED_PATHS) * len(MODES)
            or report.controls_verified is not True
            or report.role_headers_denied is not True
            or report.forged_bearer_denied is not True
            or any((
                report.real_login_tested,report.synthetic_account_created,
                report.sql_writes_requested,report.production_deployment_authorized,
                report.real_users_authorized,report.real_pix_authorized,
            ))):
        raise SessionBoundaryBlocked("M37420_REPORT_INVALID")
    return (
        "=== FR FINANCE M37420 LOCAL SESSION BOUNDARIES ===",
        "M37420_STATUS=READ_ONLY_PASS",
        "M37420_CONTROL_ENDPOINTS=" + str(report.controls),
        "M37420_PROTECTED_ENDPOINTS=" + str(report.protected_routes),
        "M37420_NEGATIVE_GET_CHECKS=" + str(report.negative_checks),
        "M37420_ROLE_HEADER_SPOOF=DENIED",
        "M37420_INVALID_BEARER=DENIED",
        "M37420_HTTP_METHOD=GET_ONLY",
        "M37420_REAL_LOGIN_FLOW=NOT_TESTED",
        "M37420_CROSS_TENANT_SESSION_E2E=NOT_TESTED",
        "M37420_USERS_CREATED=NO",
        "M37420_SQL_WRITES_REQUESTED=NO",
        "M37420_FINANCIAL_EFFECT=NO",
        "M37420_PRODUCTION_DEPLOYMENT=NOT_AUTHORIZED",
        "M37420_REAL_USER_ACTIVATION=OFF",
        "M37420_PIX_REAL=OFF",
    )
