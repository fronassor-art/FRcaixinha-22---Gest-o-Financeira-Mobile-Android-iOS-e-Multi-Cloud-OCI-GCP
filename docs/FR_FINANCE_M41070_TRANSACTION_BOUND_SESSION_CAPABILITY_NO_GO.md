# FR Finance M41070 — transaction-bound session capability (NO-GO)

## Scope and traceability

This package hardens the M41050 prototype helper only. It validates the
opaque capability shape, requires the asyncpg connection to already be in
an active transaction, sets the capability with a parameterized transaction
local set_config, then checks that PostgreSQL returned the same value and
that the transaction remains active.

Traceability: evidence contributes to CP26-0061 / CTM-07 and CP26-0062 /
CTM-08. The 330 requirement IDs and 2,310 task IDs remain stable. No matrix
acceptance state, production verification, historical clause, or sign-off is
promoted. These checks cover an engineering slice of stages 02_CODE,
03_UNIT, and 04_SECURITY; E2E, external review, and independent sign-off
remain pending.

## Evidence limits

- Offline tests exercise transaction-state checks, parameter binding, a
  mismatched PostgreSQL result, transaction loss during binding, invalid
  capabilities, and a non-awaitable driver adapter.
- A disposable PostgreSQL 18 workflow proves the setting is visible inside
  the transaction and that both commit and rollback restore the prior value.
- The helper is still not called by get_rls_db_connection, no API route is
  wired to this prototype, and no production migration or runtime change is
  included.
- This does not remediate M40570 GUC spoofing, M40710 pre-use capture,
  M40730 compromised SQL issuer, or M40928/M40929 process-identity and
  credential-custody gaps.
- The M40840 production SQL gate and M40930 HTTP 503 remain unchanged.

## Operational boundary

The disposable runner first verifies its GitHub Actions marker, isolated-run
marker, dedicated database URL, exact loopback host/port/database/user, and
all three real-money flags OFF before importing asyncpg or connecting. It
does not create tables or run DDL.

M41070_ROUTE_INTEGRATION=NONE
M41070_ORIGINAL_DATABASE=NOT_ACCESSED
M41070_MIGRATIONS=NONE
M41070_DATABASE_WRITES=NONE
M41070_SERVICE_RESTARTS=NONE
M41070_RUNTIME=NOT_RELOADED_OR_ATTESTED
PIX_REAL=OFF
PAGAMENTOS_REAIS=OFF
ATIVACAO_REAL=OFF
PRODUCTION=BLOCKED
PENDING_INDEPENDENT_EVIDENCE
