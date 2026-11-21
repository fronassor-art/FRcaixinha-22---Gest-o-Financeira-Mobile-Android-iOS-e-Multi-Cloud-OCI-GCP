# FR Finance M37437 — candidate for one-time synthetic cleanup on ORIGINAL PG18

**This candidate is not authorized to run.** It is reviewed and statically
tested in GitHub CI, but it has NOT been applied to the actual Termux
database and has NOT been tested end-to-end as a migration there.

The only proposed target is the EXISTING PostgreSQL 18 database
frcaixinha_aistudio_dev on port 5433, same project and branch.
No other database is created, copied, renamed, or dropped.

M37436 observed: one synthetic 2027 open cycle, one policy at the
obsolete price, one quota, twelve unpaid contributions and one
pending price audit. One of five incoming FK matches points from the
immutable price audit to the policy. The affected tenant has three
general audit events, which the candidate preserves.

The candidate checks exact database and table state, guarantees no
recorded payments/Pix/loans/ledger, and aborts if general audit events
reference an old cycle, contribution, price or policy. It requires an
exact encrypted backup SHA-256 already recovered in M37432, plus
separately documented user consent that is NOT supplied by any
existing script. It requires a privileged owner, exclusive table
locks and a single PostgreSQL transaction.

**Special audit exception:** the single append-only price audit row
cannot be removed through ordinary application DML. The candidate
would momentarily disable only its row immutability trigger *inside
the locked transaction*, remove exactly that synthetic row, and
immediately restore the trigger. Any error rolls back transactionally.
A fresh general immutable audit event records this exceptional cleanup
without introducing new fictional payments. The original record
remains recoverable from the sealed encrypted backup. This exception
must NEVER be enabled for real users, production or operational
financial history. No standard API permission can perform it.

Scope of the proposed cleanup, ONLY after separate explicit consent:
- Delete exactly twelve synthetic, unpaid contributions.
- Delete the one obsolete development quota.
- Delete the one synthetic pending price-audit record under exception.
- Delete the obsolete policy and now-empty 2027 development cycle.
- Preserve tenant, user, two memberships, sessions and prior general
  audit events. Add one general audit event for the exceptional reset.
- Validate both R$150 policy/quota constraints after cleanup.
- Leave the UI requiring the administrator to enter the next-cycle
  price explicitly (no R$150 preset). Do NOT automatically create a
  new cycle or synthetic debt.

**Important limitation:** FK evidence is not a complete record of
every business link. General audit event text and objects are
screened conservatively; any mismatch aborts. A disposable-PostgreSQL
end-to-end rehearsal and independently reviewed local installer
are mandatory BEFORE this candidate can be executed.

Current implementation: SQL candidate only in
backend/scripts/aistudio_dev_price_fixture_reset_candidate.sql.
It requires specific custom PostgreSQL settings, with no existing
Termux installer setting them. There is deliberately **no execution
command** in this document. Migrations applied locally: NONE.
