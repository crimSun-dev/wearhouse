## Purpose

Provides minimal, explicitly temporary browser pages, so the full account flow can be used and demonstrated end to end against the real broker and the v2 API before the styled frontend rebuild. The flow covers Google sign-in, handle onboarding, profile, privacy, friends, blocks and account settings.

## ADDED Requirements

### Requirement: Sign-in and session handling in the browser
The pages SHALL offer Google sign-in through the broker client, and SHALL restore the session after a reload. Each v2 API call SHALL use a broker access token obtained just before the call. The token SHALL be kept only in memory: never in local storage, session storage, URLs or logs. Signing out SHALL end the broker session and clear all in-memory account data.

#### Scenario: Sign in and reload
- **WHEN** a user signs in with Google and reloads the page
- **THEN** the user is still signed in, and the page shows their Wearhouse account state from `GET /api/v2/me`

#### Scenario: Token storage
- **WHEN** the user is signed in
- **THEN** no access token is present in local storage, session storage or the page URL

### Requirement: Onboarding before social pages
A signed-in account without a handle SHALL be taken to handle selection before it can reach profile, friends or block pages. The pages SHALL show handle validation and availability errors returned by the API.

#### Scenario: First sign-in
- **WHEN** a new user signs in
- **THEN** the handle selection page is shown, and choosing an available handle leads to the profile page

### Requirement: Account pages cover every account operation
The pages SHALL let a signed-in, onboarded user:
- view and edit display name, bio and avatar (preset or provider picture), and change their handle;
- view and change the three visibility settings;
- search handles, send, cancel, accept and decline requests, remove friends, and block and unblock;
- view their public profile as others see it;
- view linked sign-in methods through the broker;
- sign out everywhere;
- download an export;
- delete the account, behind a typed confirmation.

Every operation SHALL show loading, success and error states using the API's error codes.

#### Scenario: Friend flow between two browsers
- **WHEN** user A searches for B's handle and sends a request, and B accepts on their own pages
- **THEN** both friends lists show the other without manual reloads beyond navigating to the list

#### Scenario: API error surfaced
- **WHEN** an operation returns an error such as 409 `HANDLE_UNAVAILABLE` or 429 `RATE_LIMITED`
- **THEN** the page shows a readable message for that code and keeps the user's input

### Requirement: Pages are temporary, isolated and accessible
The pages SHALL be plainly labelled as temporary account pages. They SHALL use only the generated v2 contract types and the broker client, and SHALL NOT import or copy legacy code. They SHALL run from their own development origin, which is registered with the broker and the API's allowed origins. Every control SHALL have a label and SHALL be usable by keyboard alone.

#### Scenario: Keyboard-only use
- **WHEN** a user completes sign-out-everywhere using only the keyboard
- **THEN** every step is reachable, and each focused control has a visible focus indicator and an accessible name
