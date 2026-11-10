# FR Finance M37433: empty isolated development schema

M37432 proved encrypted backup recoverability. The original local
database, frcaixinha_aistudio_dev, contains 1 user, 1 tenant,
2 memberships, 79 historical sessions, 12 obsolete R$100
contributions, 1 obsolete price policy, 1 quota and 1 immutable
audit row. None is production-ready.

M37433 creates a separate database named frfinance_clean_dev_m37433.
It NEVER renames or drops the original DB and never imports its rows.
Schema-only copy uses a direct pg_dump/pg_restore pipeline with no
plaintext data dump file. The new database has no users, tenants,
memberships, sessions, contributions, policies or old audit rows.
The M043 150 BRL constraints and absent defaults must be present.
PUBLIC database access is revoked, with app/auth technical roles
unable to connect until a future isolated provisioning review.

PRELIGHT only reads cluster and encrypted backup evidence.
BUILD requires matching commit SHA and manual typed authorization.
On failure the procedure removes ONLY the brand-new database that
the current script created; an existing target database is never
overwritten or removed. Any cleanup failure is reported.

**Limitations:** Copying a current schema is not the same as replaying
versioned migrations from zero. Historical legacy functions may
remain present (though restricted); this is not a production release
and not a backend cutover. A later step will review RLS, prepare
synthetic identities and then separately authorize app DSN changes.

No OCI operations, no Pix, no real accounts, no change to original DB.
