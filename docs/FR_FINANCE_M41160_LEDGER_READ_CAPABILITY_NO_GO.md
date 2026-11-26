# FR Finance M41160 — capability boundary for ledger reads (NO-GO)

## Scope and traceability

M41160 extends the optional M41150 FastAPI-to-PostgreSQL capability path to the six existing read-only ledger GET endpoints:

- `GET /integrity-preview`
- `GET /accounts/directory`
- `GET /accounts`
- `GET /transactions`
- `GET /accounts/{account_id}/entries`
- `GET /accounts/{account_id}/entries/keyset`

The package maps to CP26-0061 / CTM-07 and CP26-0062 / CTM-08. The matrix keeps its 330 IDs, 2.310 etapas and seven evidence stages; this code and disposable CI do not promote requirement status or independent acceptance.

## Code boundary

Every listed GET receives the same optional read-only database dependency. It first requires the existing verified server session, then checks that the session role is `TENANT_ADMIN` and that its canonical tenant UUID equals the route tenant. When an independently supplied capability provider is present, the dependency issues and binds a one-use `READ_ENTRIES` ticket and opens a PostgreSQL `READ ONLY` transaction. The RLS policies remain responsible for row isolation. The default application still has no provider; its existing M40840 gate remains in force. No write endpoint, SQL migration, role or database object in the authoritative database is changed.

The extension does not remediate the P0 GUC trust-boundary issue M40570, establish independent issuer custody under M40730, attest the production process, replace M40840, or change the M40930 HTTP 503 containment.

## Disposable CI evidence

The M41150 workflow is extended to run the six real FastAPI routes against PostgreSQL 18 in its isolated fixture database. The synthetic schema gives the fixture account, transaction and entry tables with forced RLS and tenant-scoped read policies. Checks cover concurrent successful reads, response shape, capability-scoped cross-table tenant isolation, legacy GUC spoof denial, member/master denial, forged role headers, cross-tenant paths, missing/unverified sessions, ticket replay and revoked-session capability rejection.

The test overrides authentication in an in-process ASGI app and injects a fixture provider. It does not attest the official bearer verifier, key custody, authoritative schema, live FastAPI process, Termux/OCI runtime, staging deployment or external review. CI PASS is not production approval.

## Checkpoint guardrails

```text
M41160_AUTHENTICATION=OVERRIDDEN_SYNTHETIC
M41160_PROVIDER=CUSTODY_NOT_CONFIGURED
M41160_ORIGINAL_DATABASE=NOT_ACCESSED
M41160_MIGRATIONS=NONE
M41160_SERVICE_RESTARTS=NONE
M41160_RUNTIME=NOT_RELOADED_OR_ATTESTED
PIX_REAL=OFF
PAGAMENTOS_REAIS=OFF
ATIVACAO_REAL=OFF
PRODUCTION=BLOCKED
NO-GO
```

Issue #5 remains open until independent SQL, identity, staging, provider, financial, Android, legal and end-to-end evidence is accepted by the designated reviewers.
