# FR Finance M37421–M37425: contractual minimum and clean development data

Contract rule: tenant administrator selects the amount at each cycle opening.
Minimum BRL 150.00 per member/quota and cycle; it is NOT a universal fixed
amount. No future cycle may be created with BRL 100.00.

The b1ca278 screenshots depict pre-existing rows in the local 2027 cycle:
12 contributions of BRL 100 and a pending price-review request.
Changing app source does not repair persisted rows.

Updates: mobile parsers and FastAPI refuse current policy/contribution data
below BRL 150; old fixed-price development seed is retired. The administrator
selects a value in the opening preview, and the M044 authenticated opening
API accepts an explicit amount only if FR_FINANCE_CYCLE_OPEN_ENABLED=YES
and the M044 DB function is installed. This feature flag is NOT enabled
by this package, so no cycle is created.

The M042 price audit is append-only and may retain the obsolete review
even when the user interface blocks the data. Never bypass audit triggers
to hide evidence, overwrite debts as if paid, or import dev ledger data
into the future OCI production database.

Run the read-only inventory in Termux after syncing the branch:
PYTHONDONTWRITEBYTECODE=1 python backend/scripts/aistudio_dev_legacy_price_inventory.py

It inspects counts only (no account identities or credentials) and shows
if a clean dev re-seed with verified backup is required. Such reset
must be separately planned and executed, preserving a protected offline
backup, and no historical dev finance rows enter production.
