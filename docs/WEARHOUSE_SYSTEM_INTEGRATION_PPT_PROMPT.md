# Copy-ready prompt: Wearhouse system integration presentation

Create a client-ready PowerPoint presentation for **INFS4305 System Integration**, titled **“Wearhouse: From Garment Tags to Weather-Aware Outfits.”** Present Wearhouse as the current implementation of the Digital Wardrobe FYP. Make this a guided product journey with technical evidence: viewers should understand how to use the program, what each integration does, how it was tested, and what still needs improvement.

Use the following instructions and verified project facts as the content brief. Produce the presentation, speaker notes, diagram specifications, demo runbook, and reference appendix. Do not invent screenshots, working credentials, measurements, deployments, sources, or completed tests.

## 1. Audience, duration, and assignment requirements

The audience is a client steering committee and the INFS4305 lecturer. Explain the program in plain language, while making the system integration work explicit.

Prepare a **20-minute session: 10 minutes of slides, 5 minutes of live demonstration with audience participation, and 5 minutes of Q&A.** This is the schedule in the assignment PDF, page 5. The separately pasted instructions say 15 minutes, split 5/5/5; provide a condensed 5-minute talk track in the notes as a contingency. Do not claim that the lecturer approved one version over the other.

Meet these requirements:

- At least four course topics. Explicitly cover Ch. 11–12 Architecture and Interfaces, Ch. 15 Test and Analysis, Ch. 5 Information Systems and Communications, and Ch. 9 Discontinuity Management. Also connect the user problem to Ch. 1–2.
- Show an architecture diagram, interface list, working external-system exchange, one handled failure, at least three measured metrics, and baseline versus integrated results.
- Include a feasible improvement tied to **[insert the actual Homework 3 trend and citation]**. Homework 3 was not supplied; do not invent its contents.
- Give every group member a speaking or Q&A role. The reference deck names **Clairine Safa Naqayya** and **Kris Aaron Witanto**; verify the final roster. The FYP is authored by **Clairine Safa Naqayya, student ID 2023400015, Sampoerna University, 2026**. Maximum group size: five.
- Include a team contribution/peer-assessment file reminder, owner-consent confirmation, AI-use disclosure, FYP-reuse disclosure, backup demo recording, and final report reminder: **12–15-page PDF with an improvement plan**.
- Use APA 7 citations. Write original explanatory text, cite reused FYP material, and do not promise a Turnitin score. The assignment ceiling is 20%.

## 2. Sources and evidence precedence

Use these supplied references:

1. `INFS4305 Final Project Presentation Assignment.pdf`: requirements and rubric.
2. `Digital_Wardrobe_Capstone_Ch1-3_v11_Methodology.docx`: FYP motivation, research questions, methodology, and proposed design.
3. `INFS4305_DigitalWardrobe_BMKG_Integration.pptx`: earlier narrative and visual reference, with outdated facts corrected.

Use these project sources when attached or accessible:

- Current source: `apps/api/src/wearhouse/`, `apps/web/client/src/`, `packages/contracts/openapi-v2.json`.
- UI evidence: `apps/web/client/src/routes/store/{Tag,Redeem,Orders}.tsx`, `routes/staff/Commerce.tsx`, `routes/wardrobe/{Library,ItemRoute,Fitting,Suggest,Planner,Weather}.tsx`, and `src/i18n/wardrobe.ts`.
- BMKG contract: `apps/api/src/wearhouse/weather/{contract,application}.py`.
- Legacy integration measurements: `docs/RESULTS.md` and `results/2026-11-24T03-49-41Z_offline-mock.json`.
- Current performance: `docs/architecture/release-evidence-perf.md`.
- Current registration experiment: `research/reports/rq3/20261125T150923Z-a2983ef3/report.md`.
- Avatar evidence: `docs/architecture/release-evidence-avatar.md`.
- Latest research reports: `research/reports/rq1/20261125T205603Z-f1630668/` and `research/reports/rq2/20261126T012606Z-21acd80e/`.
- Frontend task status: `openspec/changes/add-wearhouse-frontend/tasks.md`.
- Brand: `DESIGN.md` and `Assets/`.

Prefer source code and dated raw evidence over stale overview text. Some README/status pages still say the new frontend does not exist, although its source and completed feature tasks exist. Feature implementation is not proof of completed release acceptance. Deployment configuration exists for the v2 client and API, but this review did not verify their current public availability. Use **[verified presentation-day app URL]** until checked.

Keep three evidence categories visibly separate:

1. **Current Wearhouse v2**: the program being explained and used for the guided journey.
2. **Legacy v1 BMKG integration experiment**: the existing before/after M1–M5 results. These are historical integration evidence, not measurements of the current React client or public v2 deployment.
3. **Proposed work**: future features, physical retail rollout, and any measurements not yet run.

## 3. The product journey to teach

Use one fictional user preparing a campus outfit for a potentially rainy day. Follow this sequence throughout the deck:

**Open Wearhouse → browse or scan a garment → obtain a private licence/activation key → redeem an official garment → add an unofficial item already owned → compose a look → request weather-aware suggestions → save a plan → optionally record actual wear.**

Show actual UI labels. Use “licence key” as an audience-friendly term, and explain once that the API calls it an **activation key**. It records a garment claim in Wearhouse; it does not prove legal ownership, authenticity, or that every retailer participates.

### Public QR and private key: explain and demonstrate both

- A public QR identifies an individual garment unit by its serial and opens the product discovery page. Current v2 links use the app route `#/items/<serial>`.
- Scanning the public tag allows lookup and a wishlist action. It does **not** add ownership, even when copied or photographed.
- A private, one-time activation key is issued separately and redeemed through the signed-in user's Redeem screen. Successful redemption adds that unit to the buyer's wardrobe as **Official**.
- Current code supports scanning a private key QR in Redeem: scanning fills the key field; the user still reviews it and presses Redeem. A public tag QR scanned there is explained as a lookup link rather than redeemed.
- Replay or invalid keys receive a generic rejection. No second garment or second owner should be created. An idempotent network retry is different from trying to make another claim.
- Keys shown on slides must be disposable presentation credentials. Normal user keys remain private.

### How codes are physically attached and how garments attach to outfits

Explain both meanings of “attached” with two clear diagrams:

**Physical attachment — proposed retailer workflow:**

- Attach the public discovery QR to a garment's hangtag or care label, with its human-readable serial and garment name.
- Deliver the private key only to the purchaser, for example on a receipt, an authenticated order screen, or beneath a tamper-evident scratch-off panel. A separate private QR may encode the same key as raw text for the in-app scanner.
- Never print a visible private key in the public QR. Each garment unit gets its own serial and key; an outfit is not registered by one shared key.
- Illustrate this as a proposed physical rollout. The current application implements digital issuance, printable public tags, and simulated purchase/key delivery; there is no evidence of participating retail stores or physical label trials.

**Digital attachment — implemented program flow:**

`Catalogue product → individual serialized unit → private key redemption → owner’s wardrobe item → selected outfit/look revision → avatar slot → planner entry or wear log`.

The key belongs to the garment unit. Saving an outfit links wardrobe items together; it does not reuse, expose, or consume their keys again. A top occupies the top slot, trousers the bottom slot, shoes the footwear slot, and accessories their allowed positions. A dress conflicts with a separate top-and-bottom combination. The avatar is a category-based visual approximation, not a measurement of physical fit or fabric drape.

### Unofficial clothing

Demonstrate **Wardrobe → “Add an unofficial piece”**:

1. Enter an item name, such as “My thrifted linen shirt.”
2. Select the garment slot; optionally enter category, colour, and size.
3. Save, then optionally add a private item photo in its inspector.
4. Set relevant attributes/care state where supported, and use the item in a look or eligible outfit suggestion.

Explain the distinction: **Official** items come through catalogue/unit redemption and have a serial/provenance; **Unofficial** items are declared by the user, require no QR or key, and have no verified catalogue provenance. Manual entry does not turn an unofficial item into an official one. Missing weather attributes must not be presented as automatically verified. Show the actual runtime visibility rules rather than promising public sharing of unofficial pieces.

## 4. Architecture and BMKG integration facts

Current v2 architecture:

`Browser (React + TypeScript; Three.js loaded for avatar) ↔ FastAPI /api/v2 modular backend ↔ PostgreSQL`.

External connections: Neon Auth for browser sign-in/access tokens and backend token verification; BMKG HTTPS JSON for forecasts; source-backed catalogue import for products. These are different interfaces. Internal modules and the avatar are not additional external systems.

Show ownership boundaries: users operate the app; the project team maintains the client/API/database; BMKG owns the weather service; the identity provider operates authentication. The browser does not call BMKG directly in this integration. Do not draw a standalone deployed ML/model microservice: scoring is an internal component unless a verified deployment proves otherwise.

Include an interface table with ID, purpose/payload, format, direction, trigger/frequency, owner, and failure handling:

- I1: browser ↔ v2 API; JSON over HTTPS, bearer token on protected requests, user actions.
- I2: API ↔ BMKG; GET by `adm4`, forecast JSON returned, on-demand refresh after cache expiry.
- I3: API ↔ PostgreSQL; SQL/transactions for catalogue, ownership, wardrobe, looks, cache and plans.
- I4: browser ↔ Neon Auth, plus backend ↔ configured JWKS endpoint; sign-in/session and signing-key verification. No access tokens or keys displayed in slides/logs.
- I5: camera/tag → browser discovery route → API lookup; URL/text, per scan; separate from private redemption.
- I6: private key → redemption endpoint → transaction; JSON, on claim; one-time state transition and replay rejection.

Identify this as the **presentation's v2 interface numbering**. The legacy experiment uses different I1–I6 labels; do not pretend they match.

BMKG official documentation checked on November 26, 2026:

- Endpoint: `https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=<code>`.
- Example location: Kemayoran, `31.71.03.1001`.
- Village-level forecasts, three-day horizon, three-hour forecast intervals, published updates twice daily.
- Access limit: 60 requests/minute/IP. BMKG attribution is required.
- Source: https://data.bmkg.go.id/prakiraan-cuaca/

Distinguish forecast interval, provider update frequency, and application cache duration. They are not the same thing.

Explain the implemented transformation:

`JSON fields local_datetime/utc_datetime, t, hu, weather_desc → validated forecast slot → rain and hot flags → hard garment filters → ranked outfit suggestions`.

App-specific contract checks include temperature 15–40 °C, humidity 0–100%, required fields, and accepted timestamp bounds. These are implementation validation choices, not universal BMKG temperature guarantees. Rain is detected from “hujan” in the description; hot means temperature ≥32 °C. The application caches valid data for three hours. It first uses a fresh cache, otherwise attempts BMKG; on failure it may use a valid cached feed up to six hours old, otherwise requests manual weather. Clearly label LIVE, CACHED, and manual/unavailable states. Seven-day planning does not mean BMKG supplies seven-day forecasts; dates beyond the horizon must be labelled accordingly.

## 5. Measured evidence: reproduce the exact scope and values

Use the following as the main baseline/integrated table. Caption it **“Legacy v1 integration experiment, November 24, 2026; synthetic BMKG-format feed; warm Neon database; in-process Python ASGI requests.”** The raw report records **zero live BMKG calls**. Never label it a public v2 benchmark or forecast-prediction accuracy test.

| Metric | Baseline | Integrated | Interpretation |
|---|---|---|---|
| M1: top-five outfits passing rain/heat rules | 65.0% (312/480) | 100.0% (480/480) | +35 percentage points; validates weather reaching the rules |
| M2: weather inputs per request | 2 | 0 on available LIVE/CACHED weather | Removes two weather questions; manual fallback still needs them |
| M3: recommendation latency | p50 230.35 ms; p95 254.13 ms | Cached p50 205.93 ms, p95 229.00 ms; cold mock p50 287.64 ms, p95 320.99 ms | Both integrated p95 values below the cached-path 500 ms budget; cold result is still mocked |
| M4: mapping/validation | Not applicable: no external feed | 100% mapped; 24/24 bad entries rejected | Schema/field correctness, not accuracy of predicted weather |
| M5: usable response within four seconds under faults | Naive client: 0/4 fault types | Gateway: 4/4 fault types | Injected timeout, HTTP 500, malformed JSON, missing fields |

For M1: 24 forecast slots × four occasions × five recommendations = 480 outfits per condition; wardrobe has 28 synthetic garments. For M3: 30 runs per condition, warmed database; no browser-to-server network hop. M5's timeout gateway response was 3296.1 ms, versus a naive failure capped at 4516.4 ms. M5 is four fault scenarios, not an empirical production error rate or a statistical availability guarantee.

Use the M1/M2/M3 and M5 before/after comparisons to meet the three-metric minimum. Explain that M1 =100% is expected when hard filters use the weather; it does not establish fashion satisfaction or Indonesian-user adoption. Faster cached results partly reflect fewer candidate outfits after filtering, so do not attribute the entire difference to caching or claim integration is always faster. Do not combine SQLite latency numbers with the Neon results.

Optional current-v2 evidence, in a separate inset/appendix:

- Registration: 500/500 genuine activations correctly placed; 0 false acceptances in 103,500 attempts across guessing, alteration, public-QR contents, and replay. Validation tests disabled admission limits to isolate validation; production rate limits were tested separately. This is bounded test evidence, not proof that forgery is impossible.
- Local backend performance: catalogue p95 266.7 ms over 500 requests at 20 concurrent clients; product recommendations p95 17.9 ms over 30 requests; outfit suggestions p95 339.3 ms over 30 requests with 80 items. API/database were local and warmed; these have no measured pre-integration counterpart in this review.
- Avatar: 59.9 FPS on the documented RTX 3090 desktop; laptop and mid-range phone not measured. Low-poly placeholders and a 60 Hz cap limit generalization.

Do not force thesis RQ results into the main talk. If asked, report them honestly: RQ1 reranking missed its MAP target; corrected RQ2 simulation passed its declared coverage/compatibility rule, with selected weights [1,0,0], so its gain cannot be attributed to a learned rotation weight. Research-model evaluation and current serving behaviour are distinct.

## 6. Slide plan: a walkthrough with the rubric embedded

Create **12 narrated slides totaling exactly 10 minutes**, then a demo holding slide and a Q&A slide. Put detailed references and technical backup after Q&A; exclude them from the timed talk. Use screenshots with numbered action callouts and a persistent small journey marker. Each slide gets a takeaway title, concise visible copy, a visual, APA/source footer, speaker, timing, and natural speaker notes.

| Slide | Time | Content and visual |
|---|---:|---|
| 1 | 0:20 | Title, presenters, FYP attribution; promise: “Scan it, add it, style it, check the weather.” |
| 2 | 0:30 | User problem: shopping, ownership records, daily styling and weather are disconnected. Show the complete journey and why integration helps. Ch. 1–2. |
| 3 | 0:35 | Step 1: open/sign in, browse catalogue or scan a public tag, inspect product, wishlist or simulated purchase. Real annotated screens. Label checkout simulated. |
| 4 | 1:05 | Step 2: public QR versus private key; physical hangtag/receipt diagram and digital claim sequence. Explain one-time verification and how a garment enters its slot. Use a realistic test-tag panel, not decorative QR artwork. |
| 5 | 0:35 | Step 3: add clothing already owned through “Add an unofficial piece.” Compare official/unofficial in a compact two-column card. |
| 6 | 0:40 | Step 4: combine items in the fitting room, save a look, plan a day, log actual wear. Show garment→look→avatar-slot links; plans and wear logs are different. |
| 7 | 1:05 | Step 5: set location/occasion/date and request suggestions. Explain BMKG fetch→validation→flags→rules→outfits with a real forecast/source badge. Ch. 5. |
| 8 | 1:05 | What makes the journey work: v2 architecture and readable interface table. Ch. 11–12; mark external boundaries and distinguish lookup from redemption. Put a full-size table in the appendix if necessary. |
| 9 | 1:35 | Did integration help? Legacy M1–M5 results, visible baseline/integrated chart or table, thresholds and experiment scope. Ch. 15. Prioritize understandable comparisons; preserve evidence labels. |
| 10 | 0:45 | What if BMKG fails? Fresh-cache/live/stale-cache/manual decision diagram and four injected faults. Show source labels, age and user action. Ch. 9. |
| 11 | 0:45 | Improvement and feasibility: monitored background refresh, contract-change detection, measured v2 cloud baseline; tie the selected improvement to actual Homework 3. Include cost/effort estimate explicitly labelled an estimate, risk, owner, ethics and success criteria. |
| 12 | 1:00 | Audience instructions and demo verification card: what to scan, how to enter/scan a private demo key, expected success and replay outcomes, unofficial-item route, clear safety/demo labels. Brief recap of the four required topic links and presenter handoff. |
| 13 | 5:00 | Live demo holding slide: large public lookup QR, readable URL, experiment status, and ordered checkpoints. Avoid an unattended key-redemption race. |
| 14 | 5:00 | Q&A: keep architecture/results/verification shortcuts available. Every member answers within their evidence area. |

Suggested speakers for a two-member group: Clairine covers the product/FYP journey (1–6); Kris covers integration/evidence (7–10); split 11–12 and demo duties. Both answer questions. Change this only to match the verified group roster and actual contributions.

## 7. Testable QR/key assets and audience exercise

This deck must contain **real, scannable demo assets**, not QR-looking images or made-up licence strings. Prepare a fixture manifest for the presenter with:

`Fixture ID | runtime/database | garment/product ID | unit serial | public lookup URL | key delivery location | assigned tester | expected result | rehearsal status`.

Use a dedicated presentation environment with fictional test users and disposable units. Prepare three independent units plus a reserve:

- **A / Discovery:** repeated public scans show the same product without granting ownership. The whole class may scan this public QR.
- **B / Valid claim:** a designated presenter or volunteer redeems one fresh key successfully; show the Official wardrobe entry and correct slot. Reuse it to show rejection without another item being added.
- **C / Private QR claim:** a separate tester scans a QR containing a different fresh key inside Redeem, reviews the populated field, then submits. Typing and scanning that same key are alternative inputs for one claim, not two licences.
- **D / Reserve:** unused unit for recovery if a rehearsal consumed B or C.

For v2, issue units through the existing staff inventory interface (backend `POST /api/v2/admin/unit-batches`) against a real published demo product; capture the actual returned public serial and privately delivered key. Alternatively obtain the buyer-bound key through the existing simulated purchase/order flow and use the matching buyer account. Do not assume a key issued to one buyer can be claimed by another. Inspect the selected flow before preparing volunteer accounts.

Generate the public QR from the verified app URL and returned serial. Generate a private test-key QR from the **raw key text**, so no secret is embedded in a public URL. Include manual text/paste alternatives. Use sharp black-on-white QR assets with at least a four-module quiet zone; test projected scanning from the back of the room and printed tags. Do not stretch, crop, recolour, or replace QR modules with a logo.

On the audience slide, place garment photo/name, public QR, serial, destination and “Lookup only.” Reveal the disposable private key/QR only for its assigned test, with “Presentation test credential — one use.” Normal private keys are never exposed this way. One key cannot support simultaneous successful claims by the whole audience; give each independent tester a different unit/key if multiple people must succeed.

**Important existing-asset warning:** `test-tags/TEST-TAGS.md` and its PNG/SVG files belong to legacy v1. There, either the public QR or its matching key can consume a registration tag. Their unused status was not checked. Do not reuse those images or keys as v2 proof: this would contradict v2's discovery-only public QR design. Existing UI example strings are also not usable credentials.

If the deck generator cannot access the app or issue fixtures, use **[fresh demo serial]**, **[fresh issued key]**, and **[insert tested QR asset]** in the draft and list them as unresolved preparation tasks. Never claim those placeholders are working. A final presentation cannot call its assets “tested” until a presenter has checked the real environment. Successful rehearsals consume keys; mint a fresh final set afterwards and record which set is reserved for class.

## 8. Five-minute live demo runbook

Keep the explanation on slides so the demonstration can move quickly. Pre-sign in, preselect products, set up a populated wardrobe, and open the required tabs before starting. Show measured outputs or logs alongside the visible app behaviour.

- **0:00–0:30:** Audience scans fixture A; show discovery and point out that the wardrobe count has not changed.
- **0:30–1:35:** Claim fixture B, show the Official item/slot, and attempt replay. If rehearsed within this budget, use fixture C for a private-key scan; otherwise keep C as an interactive backup/Q&A exercise.
- **1:35–2:05:** Add “My thrifted linen shirt” with the unofficial form; show the Unofficial label.
- **2:05–2:35:** Equip selected pieces and save a look. Point out that the items are linked to the look without reusing their keys.
- **2:35–3:30:** Request BMKG-aware suggestions and show the actual source/timestamp and relevant outfit rules. Demonstrate real external exchange when available; never label mocked data LIVE.
- **3:30–4:25:** Show a controlled weather failure with a valid cached forecast, then no usable cache and the manual fallback if rehearsal permits. Existing admin fault controls are in the **legacy v1** demo; if using them, explicitly announce the switch to the isolated v1 test environment. Do not imply those controls exist in the current v2 UI. If a v2 failure fixture is used, identify how it was created and keep it confined to the presentation environment.
- **4:25–5:00:** Show the measured baseline/integrated report, summarize the observed verification outcomes, and hand over to Q&A.

Rehearse to five minutes. If a step overruns, show the private-key QR alternative and second failure in Q&A rather than cutting architecture or measured evidence. Have a recorded five-minute run, screenshots, a downloadable results file, and local mock/offline backup ready. An offline recording is a fallback, not proof of live BMKG availability that day. Use the legacy offline runner only for the legacy demo; do not describe SQLite as a v2 option.

## 9. Improvement plan, rubric mapping, and Q&A preparation

Make the proposed improvement precise: monitored background refresh of BMKG data so the next outfit request more often finds fresh data, with a bounded refresh policy respecting published limits and explicit stale/manual handling. This is proposed work, not an implemented service. Suggested planning estimate: 2–4 developer-days plus evaluation, labelled as an estimate rather than a measured project cost. Consider scheduler/hosting usage, stale-data risks, schema changes, location privacy, attribution and ownership of monitoring. Do not call current hosting permanently free or promise zero operating cost.

Set measurable acceptance goals: cached v2 end-to-end p95 budget under a defined client/network/concurrency workload; source age visible in every weather response; complete/rejected mapping tests; repeat the four outage scenarios. Collect a matched v2 baseline and integrated benchmark rather than copying v1 numbers. Do not issue advance “pass” claims.

Include an appendix matrix covering every rubric item:

- A1 15 points: live external data flow plus handled failure.
- A2 10: interface contract, field validation and visible source/timestamp.
- A3 15: predefined metrics, matched baselines, raw evidence and limits.
- B1 15: coherent user journey and explicit chapter links.
- B2 10: participation and evidence-based Q&A by every member.
- B3 15: contribution log, peer assessment and accountable handoffs; do not fabricate contributions.
- C1 7: improvement tied to the supplied Homework 3 trend.
- C2 7: realistic cost, effort, risk, ethics and data use.
- C3 6: precise current architecture, proposed changes and interface descriptions.

Prepare short evidence-based answers to: Why BMKG? What crosses the interface? Why can a public QR not claim ownership? Where is the private key attached? Can the same garment appear in multiple saved looks? Can users add thrifted clothing? Does Official mean genuine retail authentication? What happens after key replay? What happens if BMKG is unavailable? Why are M1 results perfect? Why are legacy results not v2 cloud results? Does the avatar prove fit? Are simulated purchases real payments? What remains unmeasured?

## 10. Visual style, citations, and output checks

Use a clean 16:9 Wearhouse style: plum `#632947`, blush `#f1e0e6`, warm paper `#faf6f3`, dark ink `#2b1624`, and Figtree or a readable substitute. Use supplied Wearhouse logos. Make the product screenshots central; add numbered actions and short explanations. Avoid generic fashion stock imagery, fabricated dashboards, dense paragraphs, and decorative code. Use readable diagrams, high contrast, and approximately 28 pt body type; split dense tables into backup slides.

References must include, as applicable:

- Naqayya, C. S. (2026). *Digital wardrobe: A clothing and outfit recommendation system for Indonesian Gen Z* [Unpublished undergraduate final year project manuscript, Sampoerna University]. Use this for the supplied Chapters 1–3 v11 manuscript.
- Badan Meteorologi, Klimatologi, dan Geofisika. (n.d.). *Data prakiraan cuaca terbuka*. Retrieved November 26, 2026, from https://data.bmkg.go.id/prakiraan-cuaca/
- The INFS4305 assignment document, with course/institution author verified from supplied metadata; do not invent a lecturer name.
- Project measurement/research reports, identified as team/project technical evidence with actual dates and exact file/run identifiers; use the verified author/group and repository URL if available.
- The actual Homework 3 source once supplied.

Add external research references only if they are used in the narrative and their bibliographic details are verified. The old deck's 25.8% rainy-outfit figure, 13.8→17 ms latency, “Python standard library only,” “no stated BMKG rate limit,” public-QR ownership flow, and separate model-service diagram must not be copied into the current presentation as current facts.

Provide a disclosure such as: “This integration builds on Clairine Safa Naqayya’s Digital Wardrobe FYP with the owner’s confirmed permission. Reused concepts, text and figures are cited. AI assistance was used for [actual tasks]; the group reviewed the material and is responsible for the implementation, sources and results.” Leave permission/tasks unconfirmed until the team supplies them.

Before finalizing, check: 600 seconds of narrated slides; 300 seconds demo; 300 seconds Q&A; four or more course topics; actual architecture and interface list; at least three genuine before/after metrics; explicit legacy/v2 evidence labels; scannable public tags and freshly issued private demo keys; unofficial-clothing walkthrough; garment-to-look/slot explanation; one failure demonstration; recording backup; APA references; no invented sources or results; no normal user secrets; every member participates; unresolved deployment/fixture/Homework 3/consent items listed for the presenter.

Also supply a condensed **five-minute slide narration** for a 15-minute total slot: combine discovery/registration/unofficial/look steps, retain the architecture/interface slide, retain three metric comparisons and fallback explanation, then retain the same five-minute demo and five-minute Q&A.
