> **Historical document.** Paths here predate the `legacy/` relocation; see `docs/architecture/migration-inventory.md` §3 for the current locations.

# TDD — Digital Wardrobe Live Demo (Functional Backend First, Three.js Last)

**Course:** INFS4305 System Integration, Final Project (25%) · **FYP:** Digital Wardrobe (Capstone Design 1, Ch1–3 v11)
**Status:** Draft v0.1 · **Scope:** simple *functioning* virtual wardrobe + backend + BMKG integration + measurable demo. Frontend is a thin test page first; the real Three.js avatar comes last.

---

## 0. Decisions, Course Mapping, Assumptions

### 0.1 Backend decision: Neon (PostgreSQL), not Firebase

| Need from the spec | Neon Postgres | Firebase (Firestore) |
|---|---|---|
| Thesis Table 4 already says "FastAPI; SQLite dev, PostgreSQL deploy" | Direct match, zero redesign | Contradicts the methodology chapter |
| Interface I3 is "SQL" in your deck | Matches | Not SQL |
| Activation code "usable once" (3.4.4) | One atomic `UPDATE ... WHERE used_at IS NULL RETURNING`; DB enforces it | Needs transactions plus security rules; easy to get wrong |
| Slot uniqueness ("one item per slot"), foreign keys | `UNIQUE`, `FK`, `CHECK` constraints | App-level only |
| Wear log, recency queries, metrics aggregation | Plain SQL | Awkward aggregation |
| Backup if venue wifi dies | SQLite via the same SQLAlchemy models | Emulator only |

**Decision:** FastAPI + SQLAlchemy over **Neon Postgres** (hosted demo DB), with **SQLite** as the offline fallback using identical models. Firebase is not used. (Optional later: Firebase Auth only. Out of scope for the demo.)

### 0.2 Course topics linked (from *System Integration*, Grady)

| Assignment chapter | Book chapter | Where it shows up in this build |
|---|---|---|
| **Ch 11–12 (REQUIRED)** | Architecture definition; Interface development | §1 architecture, §3 interface list I1–I6 |
| **Ch 15 (REQUIRED)** | Integration of test and analysis results | §4 phases, §5.2 metrics M1–M5, `measure.py` |
| Ch 1–2 | Introduction; human basis | Problem: weather-blind outfits for Indonesian Gen Z |
| Ch 5 | Information systems and communications | Data flows, shared data foundation (Neon) |
| Ch 9 | Discontinuity management | BMKG fault ladder LIVE → CACHED → MANUAL (§5.1) |

Matches your existing `INFS4305_DigitalWardrobe_BMKG_Integration.pptx` (six topics). No change to the deck's claims is needed. **Warning:** the deck states measured results (e.g. "13.8 → 17 ms", "33 requests") and says `measure.py` exists. I found no `measure.py` or server code anywhere under the project folder, so Phase 5 below must produce the real numbers. Don't present the deck's numbers until the script produces them.

### 0.3 Assumptions (flagged, not verified)
1. **BMKG response shape** (`https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=<kode>` → `lokasi` + `data[].cuaca[][]` with `local_datetime`, `t`, `hu`, `weather_desc`) is from memory. **Phase 0 task: curl the live endpoint once and freeze a real sample as the mock fixture.**
2. Package versions in §2 are assumptions for a Nov 2026 start; run `pip index versions <pkg>` at scaffold and pin what you actually install.
3. One synthetic user, no real login (assignment requires synthetic/anonymised data). A static demo API key header guards writes.
4. Garment "compatibility" is a colour/style stand-in (as the deck already discloses), not the FashionCLIP model.

---

## TDD SECTION 1 — SYSTEM ARCHITECTURE OVERVIEW

**1.1 Architectural Pattern**
Layered monolith with ports-and-adapters at the edges: `api (routers) → services (rules) → repositories (SQL)`, and external systems (BMKG, DB) behind adapter interfaces.
*Why:* (a) your deck's claim "the server is the only part that talks to BMKG" is exactly a gateway adapter; (b) the demo must swap BMKG live ↔ mock ↔ failure-injected without touching rules, and swap Neon ↔ SQLite when offline; (c) a monolith is one process to start on a laptop in front of a class. Microservices/serverless were rejected as extra moving parts that raise demo risk.

**1.2 Component Diagram**

```
                  ┌──────────────────────────── Digital Wardrobe server (FastAPI) ───────────────────────────┐
 Web client       │                                                                                          │
 (test page now;  │  routers ──► services                                                                    │
  Three.js last)  │  /outfits     OutfitService ──► RulesEngine (slot/heat/rain/dress-code)                  │
   │  I1 REST     │  /garments    WardrobeService   ScoringService (compat stand-in, pref, recency)          │
   ├─────────────►│  /wardrobe    RegistrationService (public QR code, activation code, rate limit)          │
   │              │  /weather     WeatherGateway ──► BMKGClient ─ I2 ─► BMKG open API (api.bmkg.go.id)       │
   │              │  /avatar                │             │ validate → TTLCache(3h) → fallback ladder        │
   │              │  /metrics     InterfaceLog (every I1/I2 call) ◄── middleware                             │
   │              │                         │ I3 SQL                                                         │
   │              └─────────────────────────┼────────────────────────────────────────────────────────────────┘
 Phone camera ─ I5 (GS1 Digital Link URL) ──►│
                                             ▼
                       Neon Postgres (demo) ◄── same SQLAlchemy models ──► SQLite file (offline backup)
 measure.py ── I6 (HTTP + fault-injection switch) ──► server;  results → results/*.json, docs/RESULTS.md
```

**1.3 Data Flow Topology**
1. Client → `POST /api/v1/outfits/recommend {occasion, when, adm4}` (I1).
2. `OutfitService` asks `WeatherGateway.slot_for(adm4, when)`. Gateway tries cache → BMKG (3 s timeout) → validates each entry → caches 3 h. On failure uses last good ≤ 6 h, else returns `source=MANUAL_REQUIRED`.
3. Rules engine filters wardrobe combinations by slot, heat, rain, dress-code; scorer ranks; top 5 returned with `weather.source ∈ {LIVE, CACHED, MANUAL}`.
4. Every call is written to `interface_log` (interface id, status, latency ms) — this is the on-screen log in the demo and the raw data for Ch 15 metrics.
5. Choosing an outfit writes `wear_log` and updates `garment.last_worn_at`, which feeds the recency penalty next time.

**1.4 State Management Contract**
Postgres is the single source of truth. Only services mutate state, and only via repositories. The weather cache is process-local, keyed `(adm4)`, TTL 3 h, with a `fetched_at` carried into every response so staleness is visible. Clients are stateless and refetch. No websockets for the demo (polling/refetch only).

---

## TDD SECTION 2 — TECHNOLOGY STACK & DEPENDENCY MATRIX

| Layer | Technology | Version (assumed; confirm at scaffold) | Justification |
|---|---|---|---|
| Language | Python | 3.11.x (matches thesis Table 4; 3.11 is installed on this machine) | Same language as the thesis models |
| API | FastAPI + Uvicorn | latest stable at scaffold | Thesis choice; auto OpenAPI = the Ch 12 interface list for free |
| Validation | Pydantic | v2.x | Contract checks for I1 and I2 |
| ORM / migrations | SQLAlchemy 2.x + Alembic | 2.x | One model set for Neon and SQLite |
| DB (demo) | Neon Postgres | PG 16/17 (Neon default) | Matches thesis "PostgreSQL for deployment"; atomic code redemption |
| DB (offline) | SQLite | stdlib | Wi-Fi-failure backup |
| DB driver | psycopg 3 | 3.x | Neon connection (`sslmode=require`) |
| HTTP client | httpx | 0.2x | Timeouts for the BMKG call |
| Codes | `secrets`, `qrcode` | stdlib / 7.x | 128-bit serials, 80-bit activation codes (thesis 3.4.4) |
| Rate limit | in-DB counter (no extra service) | n/a | 10 activations/user/hour, survives restart |
| Testing | pytest, pytest-asyncio, respx (httpx mocks) | latest | Unit, integration, fault injection |
| Measurement | `measure.py` (stdlib `statistics`, `time`) | n/a | p50/p95, reproducible offline and `--live` |
| Frontend (now) | Single static `index.html` + fetch | n/a | Prove function before looking good |
| Frontend (last) | Three.js + GLTFLoader, Vite | pin current r-release | Thesis 3.4.5 avatar |
| Secrets | `.env` (git-ignored), `python-dotenv` | n/a | `DATABASE_URL` for Neon is never committed |

**Dependency Risk Assessment**
- **BMKG API**: no published SLA or rate limit, format may change → validation + cache + manual fallback (§5.1); self-limit to 1 call/3 h/location; credit BMKG on every weather screen.
- **Neon free tier**: scale-to-zero cold start (typically a second or more on first query) would distort M3. Mitigation: warm the DB with a `SELECT 1` before every measurement run and report cold vs warm separately.
- **Neon MCP not authenticated in this session**: the project/branch must be created by you via `neon:authenticate` (or the Neon console). I will not create cloud resources without your go-ahead.

---

## TDD SECTION 3 — COMPONENT INTERFACE SPECIFICATIONS

### 3.1 Interface list (the Ch 12 table; replaces/extends deck slide 5)

| ID | Interface | What | Format | Direction | Frequency |
|---|---|---|---|---|---|
| I1 | Client ↔ Server | Wardrobe, outfit request, 5 outfits, saved outfits | JSON/REST over HTTPS | Both | Each tap |
| I2 | BMKG → Server | Forecast: time, t, hu, weather_desc | JSON GET | Inbound | ≤ 1 per 3 h per place |
| I3 | Server ↔ DB | Garments, codes, wear log, interface log | SQL (SQLAlchemy) | Both | Each request |
| I4 | Server internal | Compatibility score function | Python call | Internal | Each request |
| I5 | Phone camera → Server | GS1 Digital Link QR `https://host/01/{gtin}/21/{serial}` | URL | Inbound | Each scan |
| I6 | measure.py → Server | Test traffic + fault switch | HTTP | Both | Per test run |

I2 contract checks (from the deck): required fields present; temperature 15–40 °C; humidity 0–100 %; times within 3 days. "Rain" = description contains `hujan`; "hot" = t ≥ 32 °C.

### 3.2 Data layer (PostgreSQL DDL; SQLAlchemy models mirror it)

```sql
CREATE TABLE app_user   (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), display_name TEXT NOT NULL,
                         gender TEXT CHECK (gender IN ('female','male')), home_adm4 TEXT);
CREATE TABLE product    (gtin TEXT PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL,
                         slot TEXT NOT NULL CHECK (slot IN ('top','bottom','dress','outer','footwear','accessory')),
                         color_hex TEXT NOT NULL, style TEXT NOT NULL,           -- compat stand-in
                         rain_suitable BOOLEAN NOT NULL DEFAULT FALSE, heavy BOOLEAN NOT NULL DEFAULT FALSE,
                         long_sleeve BOOLEAN NOT NULL DEFAULT FALSE, long_bottom BOOLEAN NOT NULL DEFAULT FALSE,
                         formality SMALLINT NOT NULL DEFAULT 1, image_url TEXT, glb_template TEXT);
CREATE TABLE garment_code (serial TEXT PRIMARY KEY,                               -- public, 128-bit hex
                         gtin TEXT NOT NULL REFERENCES product(gtin),
                         activation_hash TEXT NOT NULL UNIQUE,                    -- SHA-256 of 80-bit code
                         owner_id UUID REFERENCES app_user(id), used_at TIMESTAMPTZ);
CREATE TABLE garment    (id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                         owner_id UUID NOT NULL REFERENCES app_user(id),
                         gtin TEXT REFERENCES product(gtin), serial TEXT UNIQUE REFERENCES garment_code(serial),
                         name TEXT NOT NULL, slot TEXT NOT NULL, attrs JSONB NOT NULL DEFAULT '{}',  -- manual add
                         times_recommended INT NOT NULL DEFAULT 0, times_chosen INT NOT NULL DEFAULT 0,
                         last_worn_at DATE, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE outfit     (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), owner_id UUID NOT NULL REFERENCES app_user(id),
                         label TEXT, planned_for DATE, occasion TEXT);            -- calendar + "Saved outfits 1/2/3"
CREATE TABLE outfit_item(outfit_id UUID REFERENCES outfit(id) ON DELETE CASCADE,
                         garment_id UUID REFERENCES garment(id), slot TEXT NOT NULL,
                         PRIMARY KEY (outfit_id, slot));                          -- one item per slot, enforced by DB
CREATE TABLE wear_log   (id BIGSERIAL PRIMARY KEY, outfit_id UUID REFERENCES outfit(id), worn_on DATE NOT NULL);
CREATE TABLE activation_attempt (user_id UUID, at TIMESTAMPTZ DEFAULT now(), ok BOOLEAN);
CREATE TABLE interface_log (id BIGSERIAL PRIMARY KEY, at TIMESTAMPTZ DEFAULT now(), interface TEXT NOT NULL,
                         route TEXT, status INT, latency_ms REAL, weather_source TEXT, note TEXT);
```

Atomic redemption (the "use once" guarantee):

```sql
UPDATE garment_code SET owner_id = :uid, used_at = now()
WHERE activation_hash = :h AND used_at IS NULL
RETURNING serial, gtin;        -- 0 rows → reject with the same generic error for unknown / used / public-code input
```

### 3.3 REST endpoints (`/api/v1`, OpenAPI is the source of truth)

```
GET    /health                                   -> 200 {db:"neon|sqlite", weather_mode:"live|mock"}
GET    /wardrobe                                 -> 200 [Garment]
POST   /garments                                 -> 201 | 422        manual add (thrifted): name, slot, attrs
DELETE /garments/{id}                            -> 204 | 404
POST   /garments/activate  {code}                -> 201 Garment | 400 generic "invalid code" | 429
GET    /scan/01/{gtin}/21/{serial}               -> 200 ProductPage (wishlist only, never ownership) | 404   (I5)
POST   /outfits/recommend  {occasion,when,adm4,manual_weather?}
                                                 -> 200 {weather:{source,fetched_at,rain,hot,t}, outfits:[≤5 Outfit]} | 422
POST   /outfits            {items[], label?, planned_for?}  -> 201 | 409 (slot clash) | 422
GET    /outfits?week=2026-W48                    -> 200 [Outfit]    (calendar strip)
POST   /outfits/{id}/wear                        -> 204   writes wear_log, updates last_worn_at, times_chosen
GET    /weather?adm4=...                         -> 200 {source, slots[]} (debug view)
GET    /avatar/{outfit_id}                       -> 200 {body, slots:{top:{template,texture,tint},...}}   (feeds Three.js, Phase 6)
GET    /metrics/interface-log?limit=50           -> 200 [Row]       (on-screen log in the demo)
POST   /admin/fault  {mode: none|timeout|http500|malformed|missing_fields}   -> 200   (demo only, needs API key)
```

### 3.4 Python service interfaces

```python
# weather.py
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class WeatherSource(str, Enum):
    LIVE = "LIVE"; CACHED = "CACHED"; MANUAL = "MANUAL"

@dataclass(frozen=True)
class WeatherSlot:
    at: datetime; temp_c: float; humidity: int; description: str
    rain: bool; hot: bool; source: WeatherSource; fetched_at: datetime

class WeatherUnavailable(Exception): ...
class BMKGFormatError(ValueError): ...      # raised by validate_entry()

class BMKGClient(Protocol):                 # real, mock-fixture and fault-injecting implementations
    async def fetch(self, adm4: str, timeout_s: float = 3.0) -> dict: ...

def validate_entry(raw: dict) -> WeatherSlot: ...           # raises BMKGFormatError
class WeatherGateway:
    def __init__(self, client: BMKGClient, ttl_s: int = 10800, stale_max_s: int = 21600): ...
    async def slot_for(self, adm4: str, when: datetime,
                       manual: "ManualWeather | None" = None) -> WeatherSlot: ...   # may raise WeatherUnavailable

# rules.py
@dataclass(frozen=True)
class Context: rain: bool; hot: bool; occasion: str     # occasion ∈ {campus, casual, worship, formal, wedding}
def allowed(outfit: "Outfit", ctx: Context) -> bool: ...    # slot, heat, rain, dress-code rules (thesis 3.4.3 a–d)
def candidates(wardrobe: list["Garment"], ctx: Context) -> list["Outfit"]: ...

# scoring.py
def compat(o: "Outfit") -> float: ...                          # 0..1, colour/style stand-in (I4)
def pref(g: "Garment", p0: float = 0.5, a: int = 5) -> float:  # (chosen + p0*a) / (recommended + a)   (Eq. 8)
def recency(g: "Garment", today: date, h: float = 4.0) -> float: ...   # exp(-Δt/h); never-worn → 0   (Eq. 9)
def score(o: "Outfit", today: date, w=(0.5, 0.3, 0.2)) -> float: ...   # w1·compat + w2·pref − w3·recency   (Eq. 7)
def recommend(wardrobe, ctx, today, k: int = 5) -> list["Outfit"]: ...

# registration.py
def new_serial() -> str: ...                    # secrets.token_hex(16)  → 128 bit
def new_activation_code() -> tuple[str, str]: ...   # (16 chars shown once, sha256 hash stored)
class ActivationError(Exception): ...           # always rendered as the same generic message
def activate(user_id: UUID, code: str) -> "Garment": ...   # rate-limited 10/h; atomic UPDATE above
```

---

## TDD SECTION 4 — IMPLEMENTATION PHASES & TEST SUITE STRATEGY

Rule: tests are written first; no phase starts until the previous phase's tests are green. Frontend work (Phases 5–6) starts only after the backend demo path works end to end.

**Phase 0 — Setup & Data Freeze** (½ day)
- Scope: repo scaffold; Neon project + branch `demo` (you authenticate); `.env`; capture one **real** BMKG response for Jakarta as `fixtures/bmkg_real_sample.json`; seed script with synthetic wardrobe (28 garments, ≥ 3 per slot, mix of rain-suitable/heavy/long-sleeve).
- Deliverable: `GET /health` returns `db:"neon"`; `python seed.py` is idempotent.
- Tests: `test_health_reports_db_backend`, `test_seed_is_idempotent`, `test_seed_has_28_garments_across_all_slots`, `test_real_bmkg_sample_passes_validate_entry` (this is the check on assumption 0.3.1).

**Phase 1 — Rules & Scoring core (pure functions, no DB/HTTP)**
- Deliverable: `pytest tests/unit` green; CLI `python -m app.cli recommend --rain --occasion campus` prints 5 outfits.
- Unit tests:
  1. `test_rain_rule_requires_rain_footwear_or_outer_when_rain_true`
  2. `test_rain_rule_ignores_footwear_when_rain_false`
  3. `test_heat_rule_removes_heavy_outer_when_hot`
  4. `test_slot_rule_rejects_top_plus_dress_combination`
  5. `test_slot_rule_requires_footwear`
  6. `test_worship_requires_long_sleeve_and_long_bottom`
  7. `test_wedding_requires_formality_at_least_3`
  8. `test_pref_new_garment_starts_at_half` · `test_pref_moves_toward_choice_rate_with_evidence`
  9. `test_recency_penalty_highest_when_worn_yesterday_and_decays` · `test_never_worn_has_zero_penalty`
  10. `test_recommend_returns_at_most_five_sorted_descending`
  11. `test_recommend_returns_empty_list_not_error_when_no_outfit_allowed`
  12. `test_every_recommended_outfit_passes_allowed` (property test over 200 random contexts)

**Phase 2 — Persistence & Wardrobe API**
- Deliverable: CRUD + save/plan/wear via Swagger UI against Neon **and** SQLite (`DATABASE_URL` switch).
- Integration tests (run on both DBs via a parametrised fixture):
  1. `test_add_manual_garment_then_listed_in_wardrobe`
  2. `test_create_outfit_with_two_items_in_same_slot_returns_409`
  3. `test_db_rejects_duplicate_slot_in_outfit_item` (constraint, not just app check)
  4. `test_wear_outfit_updates_last_worn_and_times_chosen`
  5. `test_week_endpoint_returns_only_outfits_planned_in_that_week`
  6. `test_delete_garment_used_in_outfit_is_blocked_or_cascades_as_documented`
  7. `test_every_request_writes_interface_log_row`

**Phase 3 — Weather Gateway (the integration; Ch 11–12, 9)**
- Deliverable: recommend works with BMKG mock, real BMKG (`WEATHER_MODE=live`), and each injected fault; `source` is always shown.
- Tests (httpx mocked with `respx`):
  1. `test_valid_bmkg_payload_maps_hujan_to_rain_true`
  2. `test_temp_32_is_hot_31_9_is_not`
  3. `test_missing_field_entry_rejected_with_BMKGFormatError`
  4. `test_temp_out_of_15_40_rejected` · `test_humidity_out_of_0_100_rejected`
  5. `test_entries_beyond_3_days_rejected`
  6. `test_second_call_within_3h_served_from_cache_without_http`
  7. `test_timeout_after_3s_falls_back_to_cache_source_CACHED`
  8. `test_http_500_falls_back_to_cache`
  9. `test_malformed_json_falls_back_to_cache`
  10. `test_cache_older_than_6h_not_used` → `MANUAL`
  11. `test_cold_failure_without_cache_returns_manual_required_and_outfits_still_returned_when_manual_given`
  12. `test_fault_endpoint_requires_api_key`

**Phase 4 — Garment Registration (QR + activation, ties to FYP RQ3)**
- Tests:
  1. `test_valid_code_adds_garment_in_product_slot_exactly_once`
  2. `test_second_use_of_same_code_rejected_with_generic_error`
  3. `test_unknown_code_and_used_code_and_public_serial_return_identical_response_body`
  4. `test_two_concurrent_redemptions_only_one_succeeds` (threaded, Postgres)
  5. `test_eleventh_attempt_in_an_hour_returns_429`
  6. `test_scan_url_shows_product_but_does_not_grant_ownership`
  7. `test_serials_are_128_bit_and_unique_over_100k_samples`
  8. `test_activation_code_stored_only_as_hash`

**Phase 5 — Measurement harness (Ch 15)**: `measure.py`
- Deliverable: `python measure.py` (offline mock) and `python measure.py --live` produce `results/<timestamp>.json` and `docs/RESULTS.md` with baseline vs integrated. **Metrics fixed before running (do not edit after seeing results):**

| ID | Metric | Baseline | Integrated | Pass condition (set now) |
|---|---|---|---|---|
| M1 | % of top-5 outfits passing rain+heat checks, 24 slots × 4 occasions | recommender without weather | with BMKG | integrated ≥ 95 % (expect 100 %; baseline is whatever it measures) |
| M2 | Manual inputs to get a weather-aware outfit | 2 (rain, hot) | 0 | = 0 on LIVE/CACHED |
| M3 | End-to-end latency p50/p95, 30 runs, DB warm | no weather call | cold-BMKG and cached | p95 ≤ 500 ms cached; report cold separately |
| M4 | Forecast entries mapped correctly / bad feeds rejected | n/a | validated feed | 100 % mapped; 24/24 bad entries rejected |
| M5 | Usable answer ≤ 4 s under 4 faults (timeout, 500, malformed, missing fields) | naive client | gateway | 4/4 resilient; naive expected to fail |

  Tests: `test_measure_is_deterministic_given_seed`, `test_measure_writes_results_json_with_all_five_metrics`, `test_measure_refuses_to_run_if_db_cold_without_warmup`.
- Report limits honestly: mock vs live, synthetic wardrobe, stand-in compatibility.

**Phase 6 — Minimal frontend (function over looks)**
- One HTML page: weather badge (LIVE/CACHED/MANUAL), occasion dropdown, Recommend, 5 outfit cards, "Wear this", week strip, activation-code box, interface-log panel, fault dropdown.
- Validation: (1) the live-demo script in deck slide 9 can be run entirely from this page; (2) Recommend → render < 1 s on warm cache; (3) no console errors with BMKG down.

**Phase 7 — Three.js avatar (last)**
- Scope: `GET /avatar/{outfit_id}` already returns slot → template/texture/tint. Load one female body GLB + one template GLB each for top, bottom (skirt, pants), dress, outer, footwear; apply product photo as texture (thesis 3.4.5); slot-swap on outfit select; dress fills both top and bottom slots; fallback to a 2D layered image if frame time misses the target; "Camera / 3D Avatar" toggle and "Saved outfits 1 2 3" from your Canva prototype.
- Acceptance: switching outfit updates the avatar < 300 ms; ≥ 30 fps on the demo laptop and on a mid-range phone; avatar failure never blocks outfit selection.

**Phase 8 — Demo hardening**: record the backup MP4; `demo_script.md` (the four runs on slide 9); `docker`-free one-command start `run_demo.ps1`; pre-warm Neon; rehearse with offline mock switch.

---

## TDD SECTION 5 — DESIGN VERIFICATION & EDGE CASES

**5.1 Failure Mode Catalog**

| Failure Mode | System Manifestation | Detection Method | Correct Response |
|---|---|---|---|
| BMKG timeout | `/recommend` would hang | `httpx` 3 s timeout | Use cache ≤ 6 h (`CACHED`); log I2 note `timeout` |
| BMKG 500 / malformed JSON / missing fields | Parse error or wrong rain/hot flags | `validate_entry` raises `BMKGFormatError` | Reject whole feed, fall back as above; never use a partial entry |
| No cache and BMKG down (cold failure) | No weather at all | `WeatherUnavailable` | Return `weather.source="MANUAL_REQUIRED"`; client shows 2-tap Rainy/Dry, Hot/Normal; outfits returned after |
| BMKG format changes silently (e.g. renamed field) | All entries rejected | Contract check rate = 100 % rejected | Alert in log; only `BMKGClient` adapter changes |
| Neon cold start / DB unreachable | First request slow or `OperationalError` | health check + latency | Warm before demo; `DATABASE_URL=sqlite:///demo.db` fallback |
| Same activation code redeemed twice concurrently | Double ownership | Atomic `UPDATE … WHERE used_at IS NULL` | One wins, other gets generic error |
| Wardrobe too small to satisfy rain rule | Zero outfits | `recommend` returns `[]` | Message "no rain-ready outfit; add rain footwear/outer", not a 500 |
| Fault switch left on after demo | Wrong results in later measurement | `/health` shows fault mode | `measure.py` asserts `fault=none` at start |
| Secrets committed | Neon credential leak | `.gitignore` + pre-commit grep | Rotate Neon password |

**5.2 Performance Thresholds**

| Metric | Target | Hard Limit | Measurement Method |
|---|---|---|---|
| `/recommend` p95, cached weather, warm DB | ≤ 250 ms | 500 ms | `measure.py`, 30 runs (M3) |
| `/recommend` cold BMKG | ≤ 1.5 s | 3.2 s (timeout + overhead) | `measure.py`, report separately |
| Fault answer | ≤ 3.5 s | 4 s | M5 |
| BMKG calls | ≤ 8/day/location | 1 per 3 h | `interface_log` count |
| Candidate generation, 28 garments | ≤ 50 ms | 150 ms | pytest timing |
| Avatar frame rate (Phase 7) | ≥ 45 fps laptop | 30 fps phone | browser performance panel |

**5.3 Platform / Environment Edge Cases**
- Venue wifi dead: `WEATHER_MODE=mock` + `DATABASE_URL=sqlite` start path tested; MP4 backup recorded.
- Timezones: BMKG times are local (WIB/WITA/WIT) with a UTC field; store UTC, compute "afternoon" in the location's zone. Test across midnight.
- Laptop sleep/wake: the cache survives, but the Neon connection may be stale → `pool_pre_ping=True`.
- Windows/PowerShell: scripts provided as `.ps1`; paths contain spaces and apostrophes (project path has `Draven's`), so quote everything and prefer relative paths.
- Browser camera/QR requires HTTPS or localhost; demo on `localhost`.
- Data ethics: synthetic wardrobe only, no personal photos; BMKG credited on every weather screen; AI use and FYP-text reuse disclosed in the team file.

---

## Next Steps

1. **You:** authenticate Neon (`neon:authenticate`) or give me the connection string via `.env` (don't paste it in chat), and run the one-off `curl` for a real BMKG Jakarta sample, or let me do it in Phase 0.
2. I scaffold `Live Demo/backend/` (FastAPI, SQLAlchemy models from §3.2, `pytest` skeleton with the Phase 0–1 test names above) and implement Phases 0–1 test-first.
3. Then Phases 2–5, so numbers for the deck exist before any frontend work.

## Diagnostic Question (RESOLVED)

**Decision: rebuild.** The old `measure.py` / server code is not on disk and will not be reused. Slide 8 numbers (13.8 → 17 ms, 33 requests, etc.) are **placeholders** until this repo's `measure.py` produces replacements. Rebuilding is mandatory for Phases 0–5 as specified above; the deck must be updated from `results/*.json` and `docs/RESULTS.md` only. The user will paste the TDD to the coding agent as the build baseline.

**Build directive for the implementing agent:**
1. Create everything under `Live Demo/backend/` (code), `Live Demo/backend/tests/`, `Live Demo/backend/fixtures/`, `Live Demo/results/`. Do not look for or import old code.
2. Work strictly in phase order; write the named tests first and show them failing, then implement until green.
3. Never write a number into `docs/RESULTS.md` or the deck by hand; only `measure.py` writes them.
4. Read `DATABASE_URL` from `.env` (never commit it); default to `sqlite:///demo.db` if unset.
5. Stop and ask before creating any cloud resource (Neon project) or running `--live` against BMKG for the first time.

---

## Growth Breadcrumb Log (adaptation-growth-pipeline)

No EXPERIENCE_POOL exists, so this was a **POOL GAP**: no logged MISTAKEs could be consulted. Session tally: 3 breadcrumbs, 0 repeated mistakes.

- `[TIER-0] RULE (IMPACT-HIGH)` — For "use once" tokens, put the guarantee in one atomic SQL `UPDATE … WHERE used_at IS NULL RETURNING`, not in app logic. Chosen because it forces Postgres over Firebase here.
- `[TIER-0] MISTAKE-candidate (IMPACT-HIGH)` — The deck reported measured results for a harness (`measure.py`) with no code on disk. Fix: results must come from a script committed beside the deck; never write numbers before the script exists.
- `[TIER-0] RULE (IMPACT-MED)` — Fix metrics and pass conditions before running; report cold/warm latency separately (Neon scale-to-zero would otherwise distort M3).
