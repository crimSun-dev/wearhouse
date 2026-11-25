# RQ3 — Garment registration (methodology section 3.5.3)

**Answer: POSITIVE** — {'all_genuine_placed': True, 'zero_false_acceptances': True, 'single_generic_rejection': True, 'rate_limit_enforced': True, 'rq3_positive': True}

Run 2026-11-25T15:09:23.025396+00:00 · commit ea21b056805085f926d8bebc9b9c377e362c3267 (dirty: True) · wall 2023.973 s

## Genuine activations
500 of 500 real H&M products placed in the correct buyer's wardrobe with the correct category and slot.

## False claims (validation layer, admission limits disabled)
| Family | Attempts | Accepted |
|---|---|---|
| a_random_guesses | 100,000 | 0 |
| b_altered_genuine | 1,500 | 0 |
| c_public_qr_contents | 1,000 | 0 |
| d_reused_by_owner | 500 | 0 |
| d_reused_by_other | 500 | 0 |
| d_reused_by_own_redeemer | 500 | 0 |

Total accepted false claims: **0**. Distinct rejection bodies: **1** (`{"code": "INVALID_ACTIVATION_CODE", "message": "This activation code cannot be redeemed."}`).

## Rate limiting (production limits)
11th attempt within the hour: 429 (Retry-After 3600); first 10: [400]; independent user: 400.

## Design checks (not findings)
- Eq. 10 serial collision bound, n = 1e+09, 128 bits: 1.47e-21 (target < 1e-20)
- Eq. 11 one-year guessing bound: 7.25e-14 (target < 1e-10)
- Offline brute force of one 80-bit key at 10^10 guesses/s: ~3,830,563 years

## Declared deviations
- The thesis generates a 500-product test catalogue; this run samples 500 REAL permitted H&M catalogue rows (seeded), which is stronger evidence for category placement.
- The public QR payload is the Wearhouse discovery URL with the 128-bit serial, not a GS1 Digital Link: H&M article ids are not GTINs (foundation design D5), so a GS1 link cannot be formed truthfully.
- False-claim families run with per-user, per-IP and global admission limits disabled so the limiter cannot mask validation failures; the rate limit is tested separately with production limits.
- Category placement is checked against the catalogue facts (product_type_name) and the rule-derived slot (mapping hm-articles@1); products whose group has no slot rule are expected as slot 'unknown'.

## Disclosure
Code for this pipeline was written with AI assistance (Claude Code, Anthropic) under the author's direction; the author designed the study, reviewed the code and is responsible for the results. Disclose this in the thesis as required by the course's GenAI policy.
