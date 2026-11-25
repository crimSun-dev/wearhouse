## Purpose

Lets users personalise their public profile beyond the basics, like a Steam profile showcase.

## ADDED Requirements

### Requirement: Showcase settings
A user SHALL be able to set:
- a headline of up to 80 characters;
- an accent preset: `plum`, `ivory`, `blush`, `noir`, `sage` or `sky`;
- up to 3 featured shares, which SHALL be the user's own active shares.

Featuring a share the user does not own, or a revoked share, SHALL be rejected.

#### Scenario: Feature someone else's share
- **WHEN** a user features another user's share id
- **THEN** the service returns 422 `unknown_share`

### Requirement: Showcase reads honour visibility
`GET /profiles/{handle}/showcase` SHALL apply the owner's `profile` visibility: when the viewer cannot see the profile, the service returns 404. When it can, the response SHALL show the headline, the accent, and only the featured shares that the viewer can see under the share rules.

#### Scenario: Friends-only share in a public showcase
- **GIVEN** a public profile featuring one public and one friends-only share
- **WHEN** an anonymous visitor reads the showcase
- **THEN** only the public share is listed
