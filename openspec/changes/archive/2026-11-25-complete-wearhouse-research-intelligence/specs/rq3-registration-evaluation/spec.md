## Purpose

Answers RQ3: whether the two-code registration scheme places genuine garments correctly and rejects guessed, altered, copied and reused codes (methodology §3.5.3).

## ADDED Requirements

### Requirement: Genuine activations
The RQ3 run SHALL use the real v2 API against a disposable database. It SHALL take [500] published products from the permitted H&M catalogue, issue one unit per product, and redeem each activation code once as a distinct buyer. Every redeemed garment SHALL appear in that buyer's wardrobe with the product's category and slot.

#### Scenario: Correct wardrobe and category
- **WHEN** 500 genuine codes are redeemed by 500 users
- **THEN** 500 owned items exist, each in its redeemer's wardrobe with the expected category; 0 misplacements are reported

### Requirement: False claims at the validation layer
With per-user, per-IP and global admission limits disabled for this part only, the run SHALL submit:
- (a) [100,000] random codes from a CSPRNG in the activation-code format;
- (b) every genuine code with 1, 2 and 3 characters altered;
- (c) every public serial and its discovery URL as if each were an activation code;
- (d) every used code again, by its redeemer and by a different user.

Every attempt SHALL be rejected with the same generic response, and the report SHALL count acceptances per family, which must be 0. Response-body identity across families SHALL be checked.

#### Scenario: Zero false acceptances
- **WHEN** all four families are submitted
- **THEN** the report shows 0 accepted false claims, and identical error bodies across families

### Requirement: Rate limiting tested separately
With limits enabled, the run SHALL submit attempts faster than 10 per user per hour. It SHALL verify that the 11th attempt within the window is refused with 429 and a `Retry-After`, and that an independent user is not affected.

#### Scenario: Eleventh attempt refused
- **WHEN** one user submits 11 attempts within an hour
- **THEN** the 11th returns 429, and another user's attempt still runs

### Requirement: Design checks
The report SHALL compute the serial collision bound (Eq. 10) for 10^9 garments with 128-bit serials, and the guessing bound (Eq. 11) for 80-bit codes at the configured rate limit with [1,000,000] unused codes over one year. Both SHALL be labelled design checks, not findings. Any deviation from the thesis design (for example, no GS1 Digital Link because H&M article ids are not GTINs) SHALL be listed.

#### Scenario: Bounds computed
- **WHEN** the RQ3 report is produced
- **THEN** it contains both bounds with their inputs, and they are below 10^-20 and 10^-10 respectively
