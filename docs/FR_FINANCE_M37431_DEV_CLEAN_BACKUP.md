# FR Finance M37431 — encrypted backup before clean development reset

Only backup preparation; NO database reset, DELETE, INSERT, migration, or
real payment. The M37425 Termux inventory found 1 obsolete policy, 1
obsolete quota, 12 dev-only contributions and 1 append-only price audit.
Zero payments, Pix intents, loan records and ledger postings were observed.

The legacy audit is append-only: never disable triggers or rewrite
historical debts simply to make the old records disappear. An encrypted
backup is mandatory before replacing test data with a fresh development
database. This backup contains local identities, hashes and other sensitive
data. Never import it into production.

Commands after synchronizing:
1. bash backend/scripts/aistudio_dev_clean_backup.sh audit
2. FR_FINANCE_APPROVED_SHA="$(git rev-parse HEAD)" bash \
   backend/scripts/aistudio_dev_clean_backup.sh backup

The backup stream is encrypted with age --passphrase without writing a
plaintext dump file. It prompts for the PostgreSQL password and later
for an independent, strong encryption passphrase. The second passphrase
prompt verifies decryption and the pg_restore TOC. This does NOT verify
a complete restoration; that is a separate step.

The full development schema has identity tables and sessions; a whole-DB
reset without an identity re-provisioning plan would break local login.
Subsequent clean rebuild needs to decide whether to recreate isolated
test accounts or independently migrate only allowed identity data.
Do not move test contributions or append-only financial audit to the
clean database.

No OCI infrastructure was modified; Pix real and real-user activation
stay OFF.
