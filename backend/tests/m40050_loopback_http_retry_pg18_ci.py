"""FR Finance M40050: loopback-only HTTP reply-loss retry against disposable PG18.

NOT a production application or real identity. Synthetic CI labels map to
NOLOGIN PostgreSQL roles. No FastAPI, provider, money, original DB, or external
network. An HTTP response is dropped *after* an atomic database commit.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import error, request
from urllib.parse import urlsplit
from uuid import UUID

import psycopg

PACKET = "44444444-4444-4444-8444-444444444444"
RECEIPT = "fe111111-1111-4111-8111-111111111111"
SESSION = "fe711111-1111-4111-8111-111111111111"
NONCE = "fe811111-1111-4111-8111-111111111111"
IDEM = "fe911111-1111-4111-8111-111111111111"
REVIEWER_A = "43333333-3333-4333-8333-333333333333"
TENANT_A = "tenant:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
POLICY = "1" * 64
SCOPE = "TENANT_ADMIN_OWN"
TOKENS = {
    "ci-actor-a": "m40010_a_a",
    "ci-actor-b": "m40010_a_b",
    "ci-tenant-b": "m40010_b_a",
    "ci-master": "m40010_m_a",
}
ACTION = "DOCUMENTARY_CHECK_PROPOSED"
PAYLOAD = "test-only-documentary-form-v1"
STALE_PAYLOAD = "altered-documentary-form-v2"
MAX_REQUEST_BYTES = 1024


def fail(message: str) -> None:
    raise RuntimeError("M40050_" + message)


def require_ephemeral_environment() -> None:
    required = {
        "GITHUB_ACTIONS": "true",
        "PGHOST": "127.0.0.1",
        "PGPORT": "5432",
        "PGUSER": "postgres",
        "PGDATABASE": "frcaixinha_ci",
        "CI_M40050_DISPOSABLE": "1",
    }
    for key, expected in required.items():
        if os.getenv(key) != expected:
            fail("BLOCKED_UNSAFE_" + key)
    for flag in ("m40010", "m40020", "m40030", "m40040", "m40050"):
        if f"frfinance.{flag}_ci=DISPOSABLE_ONLY" not in os.getenv("PGOPTIONS", ""):
            fail("BLOCKED_MISSING_" + flag + "_GATE")
    with psycopg.connect(autocommit=True, connect_timeout=3) as conn:
        row = conn.execute(
            "SELECT current_database(), inet_server_port(), session_user,"
            " current_setting('frfinance.m40050_ci',true)"
        ).fetchone()
    if row != ("frcaixinha_ci", 5432, "postgres", "DISPOSABLE_ONLY"):
        fail("BLOCKED_WRONG_DATABASE_IDENTITY")


def fingerprint(action: str, payload: str) -> str:
    body = json.dumps(
        {"action": action, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return hashlib.sha256(body).hexdigest()


class TestServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self) -> None:
        super().__init__(("127.0.0.1", 0), Handler)
        self.drop_first_response = True
        self.guard = threading.Lock()
        self.dropped_count = 0
        self.errors: list[str] = []


class Handler(BaseHTTPRequestHandler):
    server: TestServer
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        # No tokens or sensitive request content in CI logs.
        return

    def respond(self, code: int, state: str) -> None:
        data = json.dumps(
            {"state": state, "real_review_approved": False,
             "payout_enabled": False},
            separators=(",", ":"),
        ).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def actor(self) -> str | None:
        if self.client_address[0] != "127.0.0.1":
            return None
        return TOKENS.get(self.headers.get("X-CI-Token", ""))

    @staticmethod
    def status(role: str, idem: str, digest: str) -> str:
        # Role comes only from a fixed CI token-to-role map on the test server,
        # not from a caller-provided database role / tenant.
        with psycopg.connect(autocommit=True, connect_timeout=3) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE " + role)
                return conn.execute(
                    "SELECT m40040_ci.inspect_uncertain_commit(%s,%s)",
                    (UUID(idem), digest),
                ).fetchone()[0]

    def do_GET(self) -> None:
        role = self.actor()
        if role is None:
            self.respond(403, "CI_TOKEN_REQUIRED")
            return
        path = urlsplit(self.path).path
        if path != "/ci/status/" + IDEM:
            self.respond(404, "NOT_FOUND_OR_NOT_VISIBLE")
            return
        try:
            state = self.status(role, IDEM, fingerprint(ACTION, PAYLOAD))
        except Exception as exc:
            self.server.errors.append(type(exc).__name__)
            self.respond(500, "CI_DB_FAILURE")
            return
        self.respond(200 if state.startswith("EXISTING_") else 404, state)

    def do_POST(self) -> None:
        role = self.actor()
        if role is None:
            self.respond(403, "CI_TOKEN_REQUIRED")
            return
        if urlsplit(self.path).path != "/ci/review-proposal":
            self.respond(404, "INVALID_ROUTE")
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 1 or length > MAX_REQUEST_BYTES:
                raise ValueError("bad length")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict) or set(payload) != {
                "idempotency_key", "action", "payload"
            }:
                raise ValueError("bad fields")
            if (payload["idempotency_key"] != IDEM
                    or payload["action"] != ACTION
                    or payload["payload"] not in (PAYLOAD, STALE_PAYLOAD)):
                raise ValueError("unknown synthetic request")
        except (ValueError, TypeError, json.JSONDecodeError):
            self.respond(400, "INVALID_SYNTHETIC_REQUEST")
            return
        if role != "m40010_a_a":
            self.respond(403, "CI_WRITER_NOT_DESIGNATED")
            return
        digest = fingerprint(payload["action"], payload["payload"])
        try:
            # Explicit transaction: insert receipt + ACK atomically.
            with psycopg.connect(autocommit=True, connect_timeout=3) as conn:
                with conn.transaction():
                    conn.execute("SET LOCAL ROLE m40010_a_a")
                    state = conn.execute(
                        "SELECT m40040_ci.inspect_uncertain_commit(%s,%s)",
                        (UUID(IDEM), digest),
                    ).fetchone()[0]
                    if state == "NOT_FOUND_OR_NOT_VISIBLE":
                        conn.execute(
                            """INSERT INTO m40010_ci.review_receipts(
                               receipt_id,packet_id,scope,cashbox_key,
                               policy_fingerprint,slot,actor_db_role,reviewer_id,
                               claimed_session_id,nonce,idempotency_key,action)
                               VALUES(%s,%s,%s,%s,%s,1,current_user,%s,%s,%s,%s,%s)""",
                            (UUID(RECEIPT), UUID(PACKET), SCOPE, TENANT_A,
                             POLICY, UUID(REVIEWER_A), UUID(SESSION), UUID(NONCE),
                             UUID(IDEM), ACTION),
                        )
                        conn.execute(
                            """INSERT INTO m40040_ci.receipt_ack(
                               receipt_id,packet_id,scope,cashbox_key,
                               actor_db_role,idempotency_key,request_fingerprint)
                               VALUES(%s,%s,%s,%s,current_user,%s,%s)""",
                            (UUID(RECEIPT), UUID(PACKET), SCOPE, TENANT_A,
                             UUID(IDEM), digest),
                        )
                        state = "EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE"
            # IMPORTANT: the context manager already committed.
            with self.server.guard:
                drop = self.server.drop_first_response
                if drop:
                    self.server.drop_first_response = False
                    self.server.dropped_count += 1
            if drop:
                self.close_connection = True
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.connection.close()
                return
        except psycopg.errors.UniqueViolation:
            # Concurrent copy after an already committed insert: read again.
            state = self.status(role, IDEM, digest)
        except Exception as exc:
            self.server.errors.append(type(exc).__name__)
            self.respond(500, "CI_DB_FAILURE")
            return
        if state == "EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE":
            self.respond(200, state)
        elif state == "CONFLICT_DIFFERENT_REQUEST_NO_NEW_WRITE":
            self.respond(409, state)
        else:
            self.respond(409, "CI_UNEXPECTED_UNVERIFIED_STATE")


def call(base: str, method: str, path: str, *, token: str | None,
         payload: str = PAYLOAD) -> tuple[int, dict[str, object]]:
    data = None
    headers = {"Accept": "application/json"}
    if token is not None:
        headers["X-CI-Token"] = token
    if method == "POST":
        data = json.dumps(
            {"idempotency_key": IDEM, "action": ACTION, "payload": payload},
            separators=(",", ":"),
        ).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=6) as response:
            return response.status, json.loads(response.read())
    except error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def check_response(code: int, data: dict[str, object],
                   expected_code: int, expected_state: str) -> None:
    if code != expected_code or data.get("state") != expected_state:
        fail(f"UNEXPECTED_HTTP_REPLY_{code}_{data.get('state')}")
    if data.get("real_review_approved") is not False or data.get("payout_enabled") is not False:
        fail("HTTP_REPLY_CLAIMED_FINANCIAL_AUTHORITY")


def assert_final_db() -> None:
    with psycopg.connect(autocommit=True, connect_timeout=3) as conn:
        count = conn.execute(
            "SELECT (SELECT count(*) FROM m40010_ci.review_receipts WHERE packet_id=%s),"
            " (SELECT count(*) FROM m40040_ci.receipt_ack)",
            (UUID(PACKET),),
        ).fetchone()
        if count != (1, 1):
            fail("SYNTHETIC_DUPLICATE_OR_MISSING_RECEIPT")
        rows = conn.execute(
            """SELECT r.receipt_id, r.nonce, r.idempotency_key,
                      a.request_fingerprint, a.session_authenticated,
                      a.policy_approved, a.payout_enabled,
                      r.human_identity_verified, r.approved, r.payout_enabled
               FROM m40010_ci.review_receipts r
               JOIN m40040_ci.receipt_ack a ON a.receipt_id=r.receipt_id
               WHERE r.packet_id=%s""", (UUID(PACKET),),
        ).fetchall()
        if len(rows) != 1 or rows[0][:4] != (
            UUID(RECEIPT), UUID(NONCE), UUID(IDEM), fingerprint(ACTION, PAYLOAD)
        ) or any(rows[0][4:]):
            fail("DB_FINGERPRINT_OR_FALSE_FINANCIAL_CLAIM")


def main() -> None:
    require_ephemeral_environment()
    server = TestServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = "http://127.0.0.1:" + str(server.server_address[1])
    try:
        try:
            call(base, "POST", "/ci/review-proposal", token="ci-actor-a")
        except (http.client.RemoteDisconnected, ConnectionResetError,
                http.client.BadStatusLine, ConnectionAbortedError):
            pass
        else:
            fail("FIRST_HTTP_REPLY_WAS_NOT_DROPPED_AFTER_COMMIT")
        if server.dropped_count != 1:
            fail("RESPONSE_DROP_NOT_OBSERVED")
        print("M40050_HTTP_REPLY_LOST_AFTER_DATABASE_COMMIT=PASS", flush=True)

        code, body = call(base, "POST", "/ci/review-proposal", token="ci-actor-a")
        check_response(code, body, 200, "EXISTING_UNVERIFIED_RECEIPT_NO_NEW_WRITE")
        print("M40050_HTTP_RETRY_RETURNS_EXISTING_RECEIPT=PASS", flush=True)

        code, body = call(
            base, "POST", "/ci/review-proposal",
            token="ci-actor-a", payload=STALE_PAYLOAD
        )
        check_response(code, body, 409, "CONFLICT_DIFFERENT_REQUEST_NO_NEW_WRITE")
        print("M40050_CHANGED_HTTP_REQUEST_IS_CONFLICT=PASS", flush=True)

        for token in ("ci-actor-b", "ci-tenant-b", "ci-master"):
            code, body = call(base, "GET", "/ci/status/" + IDEM, token=token)
            check_response(code, body, 404, "NOT_FOUND_OR_NOT_VISIBLE")
        print("M40050_CROSS_REVIEWER_TENANT_MASTER_RLS=PASS", flush=True)

        code, body = call(base, "GET", "/ci/status/" + IDEM, token=None)
        check_response(code, body, 403, "CI_TOKEN_REQUIRED")
        code, body = call(base, "POST", "/ci/review-proposal", token="ci-actor-b")
        check_response(code, body, 403, "CI_WRITER_NOT_DESIGNATED")
        print("M40050_UNDESIGNATED_WRITER_AND_MISSING_TOKEN=DENIED", flush=True)

        assert_final_db()
        if server.errors:
            fail("SERVER_SIDE_TEST_FAILURE_" + repr(server.errors))
        print("M40050_ONE_COMMITTED_SYNTHETIC_RECEIPT=PASS", flush=True)
        print("M40050_REAL_HUMAN_AUTHENTICATION=NOT_ATTESTED", flush=True)
        print("M40050_REAL_REVIEW_APPROVAL=FALSE", flush=True)
        print("M40050_ORIGINAL_DB_ACCESS=NONE", flush=True)
        print("M40050_LOCAL_MIGRATIONS=NONE", flush=True)
        print("M40050_REAL_PAYMENTS=OFF", flush=True)
        print("M40050_PRODUCTION=BLOCKED", flush=True)
    finally:
        server.shutdown()
        thread.join(timeout=3)
        server.server_close()


if __name__ == "__main__":
    main()
