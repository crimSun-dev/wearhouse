# @wearhouse/web

The Wearhouse web frontend: the landing page at `/` and the app at `/app/#/…`. It is a Vite 7 multi-page build with React 19, TypeScript (strict), TanStack Query, React Router (hash routes), Motion and a lazy Three.js avatar. API types come only from `@wearhouse/contracts` (`packages/contracts`). The OpenSpec change is `openspec/changes/add-wearhouse-frontend`; design decisions are in the repo-root `DESIGN.md`.

## Run

```sh
npm ci
cp .env.example .env.local        # then edit if your API is not on 127.0.0.1:8100
npm run dev                       # http://127.0.0.1:5174/ (landing) and /app/ (app)
```

The app needs the v2 API (`apps/api`). Without it, public screens show their offline state and the landing page renders with no live tiles.

| Variable | Meaning |
|---|---|
| `VITE_BASE` | Base path, e.g. `/wearhouse/` for GitHub Pages. Default `/`. |
| `VITE_WEARHOUSE_API_BASE` | API root including `/api/v2`. Default `http://127.0.0.1:8100/api/v2`. |
| `VITE_NEON_AUTH_URL` | Neon Auth URL. Empty: sign-in is unavailable and the app is browse-only. |
| `VITE_E2E_TOKEN_URL` | e2e builds only: the harness token endpoint used by the fake auth port. |

## Build

```sh
npm run build          # dist/ (index.html + app/index.html), then the build guard (no e2e fake, no legacy code)
npm run check:size     # the app entry and its static imports must stay under 200 KiB gzip
npm run preview        # serves dist/ on 127.0.0.1:4174
```

GitHub Pages builds this package from `.github/workflows/pages.yml` with the repository variables `WEARHOUSE_API_BASE` and `WEARHOUSE_NEON_AUTH_URL`.

## Tests

| Command | What it runs |
|---|---|
| `npm run typecheck` | `tsc --noEmit` over `src/`, `e2e/` and `scripts/` |
| `npm test` | Vitest unit tests (`tests/`, `src/**/*.test.ts`), then the strict endpoint coverage check |
| `npm run check:coverage` | every one of the API's operations must be referenced by the client or listed with a reason in `coverage-allowlist.json` |
| `npm run test:e2e` | Playwright `e2e/*.e2e.spec.ts` against the harness (below) |
| `npm run test:a11y` | Playwright `e2e/*.a11y.spec.ts`: axe on every route in three looks, reflow at five widths and 200% zoom, 44 px targets |
| `npm run test:visual` | Playwright `e2e/*.visual.spec.ts`: reviewed screenshots (update deliberately with `--update-snapshots`) |

The visual baselines are `e2e/__screenshots__/` (169 PNGs, about 43 MB): 13 primary routes at 360, 390, 768, 1440 and 1920 px in Desktop dark and light, plus Focus at 768, 1440 and 1920, with reduced motion on. They were rendered by this repository's Playwright Chromium on Windows. Another operating system renders text differently, so regenerate them on purpose there and review the diff; the tolerance is 40 pixels per screen, small enough that a changed corner radius fails. Run the visual project on its own (`npm run test:visual`): it needs the fresh harness database to itself, because other projects in the same run add products and change counts on screen.

### The e2e harness

`e2e/setup.ts` starts `e2e/harness.py`: the real v2 API built by its test factory on a **disposable** PostgreSQL database (created per run and dropped on exit), a local EdDSA token issuer, and `/__e2e/token` and `/__e2e/grant` endpoints. It then builds the app with `--mode e2e` (the fake auth port replaces Neon Auth) into its own `dist-test/run-<time>/` folder and previews it.

```sh
export WEARHOUSE_TEST_ADMIN_URL=postgresql://postgres@127.0.0.1:55432/postgres   # a DISPOSABLE server only
npm run test:e2e
```

Ports default to 4174 (preview) and 8199 (API). Set `E2E_PREVIEW_PORT` and `E2E_API_PORT` to run a second suite at the same time. Each run deletes only `dist-test` folders older than two hours, so parallel suites do not remove each other's builds. Point `--output` somewhere private if another suite is writing to `test-results/`.

The harness needs `apps/api/.venv` (see `apps/api/README.md`).

## Quality results

Recorded 2026-11-26 on the production build served locally, against a local harness seeded with eight synthetic products (no H&M data). These are lab measurements on one machine, not field data.

**Lighthouse 12.6.1, default mobile profile** (Moto G Power emulation, simulated slow 4G, 4× CPU slowdown), signed out:

| Page | Performance | Accessibility | LCP | CLS | TBT |
|---|---|---|---|---|---|
| Landing `/` | 99 | 100 | 1.99 s | 0.001 | 48 ms |
| App Home `/app/` | 92 | 100 | **2.93 s** | 0.000 | 51 ms |
| Catalogue `/app/#/catalogue` | 89 | 100 | **3.23 s** | 0.002 | 76 ms |

**Budget status:** the landing page meets LCP ≤ 2.5 s and CLS ≤ 0.1. **The app does not yet meet LCP ≤ 2.5 s on this profile.** Its LCP element is ordinary text that React renders, so LCP is the time to download and execute the entry chunk (about 175 KB gzip, almost all React, React Router, TanStack Query and Motion core) and, on the catalogue, its lazy route chunk. CLS is within budget on every page. Likely next steps: move staff and Indonesian copy out of the entry chunk, and preload the current route's chunk.

**INP** (Lighthouse's navigation mode does not measure it): the worst interaction per flow, from the browser's Event Timing entries, at phone size with 4× CPU throttling. Opening a product and going Back: 72 ms. Opening search and typing a query: 48 ms. Switching Home tabs and opening the catalogue: 24 ms. All are within INP ≤ 200 ms.

**Shell budget:** the app entry and its static imports are 178,747 gzip bytes of 204,800. Inflating the entry by 40 KB of incompressible data makes `npm run check:size` exit 1 (220,802 bytes), which is what fails CI.

**Accessibility** (`npm run test:a11y`): no serious or critical axe violations (WCAG 2.2 A/AA tags) on any route, signed out and signed in, in Desktop dark, Desktop light and Focus. No horizontal page scroll at 360, 390, 768, 1440 and 1920 px or at 200% zoom. Controls are at least 44 px at phone width. The keyboard-only purchase-and-redeem path is `e2e/keyboard.e2e.spec.ts`.

**Hardening** (`e2e/harden.e2e.spec.ts`): every route online, with a slow API, with the API stopped midway through a session (each route ends in content or a recoverable error, and Retry recovers), and with a screen's code failing to load. The access token never reaches the URL, storage, cookies or the console.
