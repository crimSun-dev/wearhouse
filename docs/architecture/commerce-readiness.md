# Sandbox commerce readiness (add-wearhouse-sandbox-commerce)

Recorded on 2026-11-25 against the disposable local PostgreSQL 18 cluster.

**No real money.**
- Every price is a staff-set sandbox value, labelled `sandbox: true` in every response.
- Every order carries a `sandbox-…` payment reference. A CHECK constraint enforces this (`ck_sandbox_order_sandbox_payment`).
- Nothing calls a payment provider.
- Products in the tests are the data-free synthetic fixture (`synthetic_only`).

## Gates

| Gate | Command | Observed |
|---|---|---|
| Migration 0006: upgrade, repeat, `compare_metadata` empty, runtime privileges | `pytest tests/test_migrations.py tests/test_catalogue_migration.py tests/test_accounts_migration.py` | 14 passed |
| Offers, wishlist, cart, checkout, receipts, keys, renewal, cancellation, accounts integration | `pytest tests/test_commerce.py` | 11 passed |
| Last-item race: 4 concurrent checkouts on stock 1 | `test_concurrent_checkouts_for_the_last_item` | exactly one 201, three `OUT_OF_STOCK`; stock 0; 1 order |
| Cancel versus claim race on the same unit (3 rounds) | `test_cancel_versus_claim_race_has_one_winner` | exactly one winner each round; the unit ends `retired` or `claimed` to match |
| Checkout refusals change nothing (`CART_EMPTY`, `PRICE_CHANGED`, `OUT_OF_STOCK`, `NOT_AVAILABLE`) | `test_checkout_refusals_change_nothing` | 0 orders, 0 units, 0 credentials; stock unchanged; cart kept |
| Keys: absent from receipts and checkout; buyer-only reveal, audited; buyer-bound (another user gets the generic 400); renewal revokes the old key | `test_receipt_key_reveal_claim_and_isolation`, `test_renew_key_revokes_old_key` | passed |
| Route allowlist, boundaries (new `commerce` module), contracts | `pytest tests/test_app_factory.py tests/test_boundaries.py`; `python tools/contracts.py check` | passed; "contracts up to date" |
| Full v2 suite | `pytest -q` in `apps/api` | 465 passed, 1 skipped (the source-backed proof that needs the permitted H&M fixture) |
| Pages: typecheck, unit tests, guarded build | `npm run typecheck`, `npm test`, `npm run build` | clean; 7 passed; "build guard OK" |
| Pages e2e: import → publish → offer → wishlist → cart → checkout → receipt → show key → claim → orders | `npx playwright test` | 8 passed (all account, catalogue and commerce flows) |

## Design notes

- **Lock order.** Checkout takes the cart rows, then the offer rows in `product_id` order, so two checkouts on the same products cannot deadlock. Cancellation takes the order row, then the credentials, then the units. Redemption takes the credential, then the unit, so the credential-then-unit order matches and a cancel and a claim cannot deadlock.
- **Accounts integration.** The account export gains a `commerce` section (wishlist, cart and orders, never keys). Deletion clears the wishlist and cart and keeps the orders. Both are injected into `AccountsService` from `bootstrap`, so accounts does not import commerce.
- **Key delivery.** The 24 h key delivery is reused from issuance, with the buyer as both the actor and the audience. After it expires, the buyer can get a new key with "renew key".
