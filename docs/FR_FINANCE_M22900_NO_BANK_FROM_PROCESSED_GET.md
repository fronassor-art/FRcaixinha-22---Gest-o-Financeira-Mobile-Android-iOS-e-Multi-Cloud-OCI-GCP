M22900 — Orders processed is not a bank settlement.

In the operator's M21500/M21800 APRO TEST R$50 case the Orders GET processed status verifies provider processing only. M22900 adds fail-closed checks so provider GET cannot assert bank reconciliation, ledger writes or financial effects. Synthetic tests reject malformed timezone offsets and monetary types before any journal. No bank connector, tenant OAuth, real Pix, API deployment, DB migration or OCI creation has been executed.

pytest.ini fixes pytest-asyncio function loop scope warnings; the existing Starlette/AnyIO deprecation is separate.
