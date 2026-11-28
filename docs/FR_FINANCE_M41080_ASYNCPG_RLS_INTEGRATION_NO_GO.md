# FR Finance M41080 — asyncpg capability and RLS integration (NO-GO)

## Scope and traceability

M41080 extends the existing M41050/M41060 PostgreSQL 18 disposable fixture.
It exercises the M41070 `install_session_capability` helper with a real
asyncpg connection and the fixture's existing `m41050.protected_entries`
policies. The read capability is tested against forged legacy Master/tenant
GUCs; read-only writes, write-only reads, an authorized Admin insert,
cross-tenant writes, duplicate idempotency keys, and concurrent retries are
checked using synthetic identities and records.

Traceability remains CP26-0061 / CTM-07 and CP26-0062 / CTM-08. The original
330 requirement IDs and 2,310 task IDs stay unchanged; this package does not
promote a requirement, task, E2E stage, external gate, or acceptance state.
It supplies disposable evidence for an engineering slice only.

## Implementation boundary

- The runner reuses the existing PostgreSQL 18 CI fixture and its disposable
  `fr_m40700_disposable_ci` database on loopback port 55439. No new
  authoritative database, schema migration, production route, API contract,
  role, or service is introduced.
- The asyncpg driver is imported only after exact disposable identity and
  real-money OFF preflight. SQL values remain parameterized; the capability
  is installed with `set_config(..., true)` from inside an active
  transaction and is verified to clear after the read transaction.
- Synthetic fixture writes exercise only the existing CI RLS policies. They
  do not prove authorization for a live account, production runtime, provider,
  customer, or real funds.

## Remaining blockers

This test does not fix M40570 GUC spoofing, M40710 pre-use capture, M40730
compromised SQL issuer, M40928/M40929 process identity and credential custody,
staging or independent review. Issue #5 remains open. M40840 remains NO-GO and
M40930 Master writes remain HTTP 503. No migration or operational approval is
implied by code, CI, or this evidence.

## Checkpoint and operational boundary

M41080_ROUTE_INTEGRATION=NONE
M41070_ROUTE_INTEGRATION=NONE
M41080_ORIGINAL_DATABASE=NOT_ACCESSED
M41080_MIGRATIONS=NONE
M41080_DATABASE_WRITES=DISPOSABLE_FIXTURE_ONLY
M41080_SERVICE_RESTARTS=NONE
M41080_RUNTIME=NOT_RELOADED_OR_ATTESTED
PIX_REAL=OFF
PAGAMENTOS_REAIS=OFF
ATIVACAO_REAL=OFF
PRODUCTION=BLOCKED
PENDING_INDEPENDENT_EVIDENCE
