# sandbox-offers Specification

## Purpose
Lets staff put published products on sale in a sandbox with mock prices and stock, without implying real prices, real stock or real payment.

## Requirements

### Requirement: Staff-managed sandbox offers
Accounts with the `commerce:offers` capability (catalogue editors and admins) SHALL be able to set, replace and withdraw an offer per product. An offer is a price in whole rupiah between 1 and 100,000,000, the currency `IDR`, and a stock count between 0 and 100,000. Every change SHALL be audited with the acting account.

#### Scenario: Customer cannot set an offer
- **WHEN** a customer submits an offer
- **THEN** the service returns 403, and no offer changes

#### Scenario: Offer for an unknown product
- **WHEN** staff submit an offer for a product id that does not exist
- **THEN** the service returns 404

### Requirement: Public offers are labelled sandbox
`GET /commerce/products/{id}/offer` SHALL return the price, the currency, whether the product is in stock, and `sandbox: true`, but only for published products with an offer. It SHALL NOT reveal the exact stock count. Unpublished, retired or unoffered products SHALL return 404.

#### Scenario: Retired product
- **GIVEN** a product with an offer that is later retired
- **WHEN** anyone reads its offer
- **THEN** the service returns 404
