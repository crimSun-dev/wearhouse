# apps/web

The Wearhouse web frontend. It uses the supplied Wearhouse logos (`Assets/`), takes its structure from the Steam references (`Reference/`), and imports API types only from `packages/contracts`.

| Package | What it is |
|---|---|
| [`client/`](client/README.md) (`@wearhouse/web`) | The frontend: the landing page at `/` and the app at `/app/#/…` (catalogue, wardrobe, avatar, community, profile, settings, staff workspace). Built by the OpenSpec change `add-wearhouse-frontend`; design system in the repo-root `DESIGN.md`. |
| `account-pages/` (`@wearhouse/account-pages`) | Temporary Neon Auth account pages from the accounts change. The client replaces them; they stay until cutover because the accounts e2e job in CI still runs against them. |

Neither package contains or copies the legacy renderer (`legacy/web/src/app.js`).

Start with [`client/README.md`](client/README.md) for running, building, environment variables, the test suites, the e2e harness and the recorded quality results.
