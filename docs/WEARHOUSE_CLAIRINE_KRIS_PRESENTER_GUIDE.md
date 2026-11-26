# Wearhouse presenter guide

**For Clairine Safa Naqayya and Kris Aaron Witanto**  
**Companion:** `WEARHOUSE_CLAIRINE_KRIS_20_MINUTE_SCRIPT.md`  
**Basis:** all 19 slides and embedded notes in the supplied PPT, current application source, and recorded project evidence reviewed on November 26, 2026.

Presentation readiness is the state in which the spoken claims, demonstrated behaviour, and supporting evidence describe the same system under identifiable conditions. This guide establishes those conditions for Wearhouse, assigns presenter responsibilities, and provides the operational checks needed to deliver the twenty-minute session accurately.

## I. Responsibilities and coordination

| Area | Clairine | Kris |
|---|---|---|
| Main presentation | Slides 1–4, proposed improvement on 14, shared handoff on 9 | Slides 5–8 and shared handoff on 9 |
| Live program | Public lookup, claim, replay, unofficial item, saved look | Location, forecast source, suggestions, isolated failure test |
| Primary questions | FYP scope, garment records, official/unofficial entry, outfits, avatar, planner | Interfaces, identity verification, database transactions, weather mapping, measurements, failure handling |
| Preparation | Test garments, intended buyer, wardrobe slots, product screenshots, owner-reuse disclosure | Environment readiness, source/timestamp evidence, fault fixture, results file, recording playback |
| Shared responsibility | Rehearsal, factual review, contribution log, peer assessment, final submission | Rehearsal, factual review, contribution log, peer assessment, final submission |

The operator controls the mouse and narrates the current action; the other presenter observes the clock and points to the expected evidence. A handoff should identify both the next presenter and the next process. Use the prepared lines rather than speaking simultaneously. Contribution records should describe work actually performed; the role allocation above does not establish historical contribution.

For twenty minutes, use **10 minutes of narration + 5 minutes of demonstration + 5 minutes of discussion**. The supplied PPT still states 5/5/5 on slides 16–17 and in its original notes. Before presenting, update those timing labels to 10/5/5 if the deck is being revised. The script itself brings slide 14 forward before slide 9, ensuring that the improvement plan is addressed within the main presentation.

## II. Project analysis: what each presenter must understand

### A. Product scope and evidence boundaries

Wearhouse v2 encompasses catalogue discovery, simulated purchasing, garment claiming, personal wardrobe management, outfit composition, planning, and social functions. Its browser client uses React and TypeScript, its backend uses FastAPI, and its persistent data reside in PostgreSQL. Neon Auth provides identity functions, while BMKG provides external forecasts. Source-backed catalogue ingestion and private activation credentials support the garment workflow. The system also accepts manually declared clothing and distinguishes it from catalogue-backed records. These components provide the product context, although the presentation deliberately concentrates on garment registration and weather integration.

The legacy v1 runtime remains a separate course demonstration with different routes, identity assumptions, and registration behaviour. The main comparison table in the PPT comes from that environment’s November 24 experiment. Current v2 source and tests establish implementation details, while dated reports establish the scope of recorded experiments. Neither source code nor a deployment configuration proves that a public service is available during class. Several overview documents also lag behind the actual frontend source, making them unsuitable as the sole readiness reference. The presenter should therefore identify the runtime before using its result as evidence.

| Distinction | Current Wearhouse v2 | Legacy v1 measurement/demo |
|---|---|---|
| Backend | `apps/api`, FastAPI, `/api/v2` | `legacy/python`, `/api/v1`; separate deployed Neon adapter also exists |
| Client | `apps/web/client` | `legacy/web` |
| Local API port | 8100 | 8000 |
| Identity | Verified token and server-granted capabilities | Synthetic demo identity/shared demo write key |
| Public QR | Discovery only | Legacy tag/key registration can consume the same unit |
| Persistent storage | PostgreSQL | Neon PostgreSQL or local SQLite fallback |
| Main before/after evidence | No matched current browser/cloud comparison supplied | M1–M5 mock-feed experiment recorded |
| Classroom fault switch | No equivalent visible control established in the reviewed v2 UI | Legacy admin fault and cache controls |

### B. Registration and outfit composition

An activation credential authorizes one garment-unit claim under the applicable ownership rules. The public serial identifies the unit for discovery, while the private key supports redemption. Purchased units can bind their credentials to the buyer, so a valid key may still be invalid for another account. Redemption checks credential state and unit state before recording the claim, and a transaction protects related changes from partial completion. Current UI labels distinguish Official and Unofficial wardrobe items. Those labels describe the acquisition path and available provenance rather than independent authentication of the physical garment.

Outfit composition begins after wardrobe entry. A saved look associates selected wardrobe-item identifiers with permitted slots and preserves a revision of that selection. The same item may occur in multiple looks because saving a look does not create another garment or consume another activation key. A top and bottom can form the clothing core, while a dress conflicts with the separate top-and-bottom selection. Footwear and optional outerwear support automated outfit generation, and additional accessory slots support fitting-room composition. A plan selects intended wear for a date; a wear event records actual use and can influence later preference/recency calculations.

Manual entry requires neither a serial nor a key. The current form accepts a name and slot, with optional descriptive fields, and the inspector permits review of supported attributes and a private photo. Attribute origins matter because catalogue rules and user declarations provide different forms of evidence. The user should not assume that selecting a category proves waterproofing or physical fit. The avatar uses category templates and approximate colour, with a disclosed two-dimensional fallback where needed. The presentation should therefore describe it as a visualization of selected items.

### C. Weather behaviour that differs from the deck’s existing notes

Current suggestions operate on a selected date and a daily forecast summary. The source implementation groups slots by local date and sets rain or hot when any available slot for that day has the corresponding condition. The reviewed controls expose Date, Occasion, Rain, Hot, and Refresh, rather than a precise outing-time selector. BMKG’s three-hour interval describes the forecast granularity; the provider’s twice-daily update frequency and the application’s three-hour cache are separate concepts. The parser checks required fields and app-specific numeric/timestamp limits before accepting a feed. The rules interpret “hujan” as rain and temperature of at least 32 °C as heat.

For current v2, rain requires rain-suitable footwear or outerwear, and heat excludes heavy outerwear. Occasion rules add further constraints, such as long sleeves and a long bottom for worship or a formal piece for a wedding. A daily forecast can be unavailable, outside the horizon, or disabled by settings. In the unavailable case, suggestions can report `weather.source = NONE`, with no rain or heat rules applied. A manual override sets source MANUAL; if only one condition is supplied, the other can remain unknown. The demonstration should set both Rain and Hot explicitly when demonstrating complete manual weather context.

| Observed source/state | Interpretation | Appropriate explanation |
|---|---|---|
| LIVE | Gateway accepted a newly fetched feed | Identify source and fetch time; show external-request evidence if proving live exchange |
| CACHED | A stored forecast was reused | Identify age; distinguish ordinary cache use from fallback after a failed refresh |
| MANUAL_REQUIRED on weather service | No usable feed/location context | Show the status, then enter explicit conditions in Suggestions |
| NONE on suggestions | No forecast context reached the rules | State that weather rules were not applied |
| MANUAL on suggestions | At least one override was supplied | Show both selected values; do not imply automatic BMKG context |
| DISABLED | A relevant setting is off | Explain that the user disabled the functionality |
| Mock fixture | A controlled feed replaces the dependency | Declare the fixture even if an application badge represents a successful simulated fetch |

## III. Required preparation before the presentation

### A. Close the PPT gaps

| Slide | Current issue | Required preparation |
|---|---|---|
| 1 and original notes | Main talk totals five minutes | Use the companion ten-minute narration |
| 2–4 | Garment/catalogue/wardrobe imagery is labelled as design mockups | Introduce it as design reference; demonstrate the actual interface |
| 5 notes | Describes a selected time slot | Say selected date and explain daily aggregation |
| 7 | Legacy metrics can be mistaken for current app measurements | Say experiment scope before presenting values |
| 8 | Manual fallback appears simpler than actual suggestions state | Explain NONE and enter both overrides when needed |
| 10 | `[Verified app URL]` and `[Fresh demo serial]` remain placeholders | Insert the verified public lookup and a real scannable QR before claiming audience readiness |
| 14 | Homework 3 trend/citation pending | Obtain the actual source, add its connection, retain estimate/proposal labels |
| 15 | Fixture and recording readiness pending | Complete the fixture manifest and test playback |
| 16–17 | 5/5/5 and 15-minute labels | Update to 10/5/5 and 20 minutes if revising the deck |

This task produces the script and guide; it does not modify the supplied PPT or issue credentials. The checks above remain presenter preparation tasks until completed in the intended environment.

### B. Environment and tab preparation

Use the existing configured presentation environment rather than changing infrastructure during class. Confirm the v2 client, v2 API, identity provider, and intended database before issuing demonstration units. For local v2 development, the existing `tools/dev_api.ps1` runner uses configured `WEARHOUSE_*` variables and serves the API on port 8100; its `-CheckOnly` option validates readiness without starting the service. The legacy `run_demo.ps1` serves the separate course runtime on port 8000, with `-Offline` for its SQLite/mock configuration. A local `127.0.0.1` URL cannot be opened by audience phones as though it referred to the presenter’s laptop. Audience lookup therefore requires a reachable verified HTTPS deployment or an explicitly arranged network-accessible demonstration setup.

Prepare these tabs in presentation order:

1. V2 public lookup for fixture A, in a signed-out or normal audience view.
2. V2 presenter account with Redeem, Wardrobe, and the intended garment information ready.
3. V2 unofficial-entry form and Fitting room; keep bottom and footwear available in the same account.
4. V2 Weather and Outfit suggestions with the saved location and relevant settings checked.
5. Separately labelled legacy fault environment, if using its fault controls.
6. The exact measurement report and raw-run identifier.
7. The five-minute backup recording stored locally and tested without internet.

Warm the application before the session and verify sign-in again shortly before presenting. Maintain one normal user view for product demonstration and a separate staff view for preparation. Avoid exposing tokens, connection strings, normal user keys, or private account details in projected developer tools. If request evidence is needed, prepare a view showing only the route, response status, source, and timing. A backend fetch trace is stronger live-exchange evidence than a browser request alone, because the browser normally contacts Wearhouse rather than BMKG. Do not infer production availability from a successful local test.

### C. Fixture manifest and QR preparation

| Fixture | Purpose | Expected outcome | Assigned user |
|---|---|---|---|
| A | Public lookup QR | Repeated product lookup; no claim | Audience/public |
| B | Private activation plus independent replay | One Official item, then generic rejection | Verified intended buyer/presenter |
| C | Private-key QR alternative | Scanner fills key; user confirms redemption | Separate verified intended user |
| D | Unused recovery unit | Available if rehearsal consumed another key | Recorded in advance |

Maintain a private manifest containing product ID, garment/unit ID, serial, public URL, intended claimant, key-delivery location, environment, and rehearsal status. Use a published product that exists in the intended environment. Prepare units through the supported staff inventory flow or through simulated purchase and the matching buyer’s order receipt. Current staff issuance uses `POST /api/v2/admin/unit-batches`; purchaser delivery uses the order’s private key endpoint and may restrict redemption to that buyer. Public tags use the actual app’s `#/items/<serial>` route. A private-key QR encodes the raw key text and is scanned inside Redeem, without embedding the secret in a public link.

Current order screens support **Reveal key → Show as QR**, and Redeem supports **Scan a key QR**. Manual entry remains the alternative when camera support is unavailable. Test the phone/browser permissions and scanner compatibility before class rather than assuming every device supports the camera workflow. Use a high-contrast QR, a clear quiet zone, a readable fallback URL, and a printed backup. Reserve keys after rehearsal because successful claims consume them. The existing `test-tags/` assets belong to v1 and must not be presented as v2 discovery-only tags.

### D. Wardrobe and forecast prerequisites

Prepare at least one ready top, bottom, and footwear combination, or a ready dress and footwear. The claimed outerwear and unofficial shirt alone do not provide a complete automated recommendation core. Keep care state **Ready**, assign known slots, and inspect the attributes required by the selected test conditions. For rain, ensure at least one eligible footwear or outerwear item has the relevant rain attribute; for heat, avoid relying exclusively on heavy outerwear. The saved manual look and the automatically suggested outfit do not have to be identical, because suggestion rules may exclude a manually chosen item. Explain that distinction if it becomes visible.

Save Kemayoran’s code `31.71.03.1001` through Weather and choose a date with available forecast slots. Check that style suggestions and weather participation are enabled in Settings. Leave Rain and Hot on **From forecast** for the automatic demonstration, then set both explicitly for manual recovery. If the real forecast is dry, demonstrate its actual conditions. A rainy scenario may be supplied through an identified test fixture or user override, with its source stated. Do not repeatedly change location until an attractive result appears and then describe it as a predetermined live test.

## IV. Demonstration control and recovery

| Demo elapsed | Operator | Minimum evidence to show |
|---|---|---|
| 00:00–00:30 | Clairine | Correct product opens from public lookup; wardrobe count unchanged |
| 00:30–01:35 | Clairine | One claim creates one Official item; new claim attempt rejected |
| 01:35–02:05 | Clairine | Manual shirt saved with Unofficial label |
| 02:05–02:35 | Clairine | Correct items linked to one saved look |
| 02:35–03:30 | Kris | Location, date, actual forecast source/time, applicable rule explanation |
| 03:30–04:25 | Kris | Declared controlled failure and identifiable recovery path |
| 04:25–05:00 | Both | Observed outcomes distinguished from historical measurements |

For a legacy live fault demonstration, prime the cache, enable the timeout mode, request a recommendation, and show both the failure note and the cached response. The cache must be due for refresh so the injected fault is actually exercised; the legacy fault control marks cached data for refresh. If time allows, clear only that isolated test cache and demonstrate the manual path. Restore the fault mode afterwards. Turning off the presenter’s entire internet connection is unsuitable because it can also disconnect the browser, authentication, and database. Removing a saved location demonstrates missing context rather than a BMKG server outage.

| Problem | Immediate action | Spoken response |
|---|---|---|
| Audience QR does not scan | Open the verified URL; leave printed tag available | “The lookup link provides the same product-discovery route. Audience scanning can continue after the demonstration.” |
| Buyer mismatch or consumed key | Confirm intended account; switch once to reserved fixture D | “This credential is not valid for the current claim. The reserved test unit will be used; the failed attempt has not established ownership.” |
| Replay displays the original success | Check whether the same idempotent request was retried; start a new claim intent and confirm count | “A retry can return the original result without creating another item. A separate claim attempt is required to test replay rejection.” |
| No suggestions | Inspect reasons, Ready items, slots, attributes, and settings; use prepared known wardrobe | “The current combination does not satisfy the declared requirements. The explanation identifies the missing or excluded items.” |
| Source shows NONE | Enter both Rain and Hot manually | “Weather conditions are unavailable, so the rain and heat rules have not been applied. Explicit manual conditions will supply that context.” |
| No fresh LIVE response | Show CACHED accurately; use a recorded verified live exchange if required | “This request reused a forecast. The recording identifies the separate live exchange and its date.” |
| Actual source is mock | Keep mock label visible | “This is the controlled test feed used to demonstrate the contract and rules.” |
| Application/network failure | Allow one retry or approximately fifteen seconds, then play local backup | “The live environment is unavailable. The backup records the same workflow and identifies its test conditions.” |
| Demo exceeds time | Omit private QR alternative and planner action; preserve measured evidence and failure proof | “The remaining optional workflow is available during questions.” |

## V. Questions and evidence-based answers

### 1. What is being integrated?

**Kris:** “The backend integrates BMKG forecast JSON with the user’s wardrobe and outfit rules. Identity, storage, and garment claiming provide additional interfaces with distinct responsibilities. The evaluated case is the movement of weather data through validation into outfit selection.”

### 2. Why BMKG?

**Kris:** “BMKG provides official Indonesian forecasts at village level in a documented JSON format. Its location codes support the intended local context, while its published horizon, access limit, and attribution requirements provide a defined integration contract.”

### 3. What happens when someone photographs the public QR?

**Clairine:** “In v2, the photograph provides the discovery link and serial. It does not provide the private activation key and does not change ownership. The public tag and the purchaser credential serve separate processes.”

### 4. Where are the QR and key attached?

**Clairine:** “The proposed physical workflow places the public QR on a hangtag or care label and delivers the private key through the buyer’s receipt or protected panel. The implemented application supports digital issuance and simulated order delivery. A physical retail rollout remains proposed.”

### 5. How is a garment attached to an outfit?

**Clairine:** “The successful claim creates a wardrobe item, and the saved look records that item’s identifier in the selected slot. An outfit can reference the item again without another activation. Each garment unit has its own key; the saved outfit does not receive a shared ownership key.”

### 6. Can unofficial clothing be used?

**Clairine:** “Yes. Add an unofficial piece creates a user-declared record with a selected slot and optional descriptive details. The item can participate in composition and eligible suggestions, while retaining its Unofficial label and lacking verified catalogue provenance.”

### 7. Does Official prove that a physical garment is genuine?

**Clairine:** “Official identifies a catalogue-backed claim in Wearhouse. It does not independently authenticate the physical object or establish legal ownership. That broader assurance would require a participating issuer and a verified physical supply-chain process.”

### 8. What prevents two people from claiming one unit?

**Kris:** “The backend checks active credentials and unit state within a transaction, with row locking and an atomic state change. Purchased credentials can also be buyer-bound. An independent repeated claim receives a generic rejection.”

### 9. Why might a repeated request return success?

**Kris:** “Idempotency allows the same network intent to return its original result without repeating the mutation. A replay test uses a new intent with a consumed key. The important outcome in both cases is that a second owned item is not created.”

### 10. Is the QR a GS1 Digital Link?

**Kris:** “The current v2 tag is a Wearhouse discovery URL. The H&M article identifiers used by this project are not verified GTINs, so the presentation should not label these v2 tags as GS1 Digital Links. The legacy demo used separate synthetic GS1-shaped identifiers.”

### 11. How secure are the keys?

**Kris:** “The design uses random keys, server-side validation, one-time state transitions, generic rejections, and admission limits. The recorded v2 experiment accepted 500 genuine activations and rejected 103,500 false-claim attempts. Admission limits were disabled for the validation families and tested separately; this is bounded evidence rather than a universal security guarantee.”

### 12. Is the recommendation model trained machine learning?

**Kris:** “The current outfit-serving implementation declares a heuristic compatibility baseline combined with hard rules, preference, and recency. The research pipelines have separate model experiments. A trained research result should not be described as the active serving model without a verified imported artifact and declared model mode.”

### 13. Does the program forecast the weather itself?

**Kris:** “No. BMKG supplies the forecast. Wearhouse validates and interprets it as rain and heat conditions, then applies garment rules. Mapping correctness and garment-rule compliance therefore measure the integration rather than meteorological prediction accuracy.”

### 14. Why is the compliance score 100%?

**Kris:** “The integrated system removes combinations that violate the configured weather rules. Complete compliance among retained combinations is therefore expected. The test confirms that weather information reaches the filters; satisfaction, style quality, and real-world forecast errors require other evaluations.”

### 15. Did integration make requests faster?

**Kris:** “In this legacy mock experiment, cached p95 was 229.00 ms compared with baseline 254.13 ms, while cold mock p95 was 320.99 ms. Filtering changes the candidate workload, so the evidence does not support a general claim that integration always improves speed.”

### 16. What does p95 mean?

**Kris:** “It is the ninety-fifth percentile of measured request durations. Approximately ninety-five percent of the observations completed within that value. The report used thirty runs per condition, so it remains a limited workload sample.”

### 17. What exactly was tested before and after integration?

**Kris:** “M1 compared weather-rule compliance with and without weather context. M2 compared two manual weather inputs with automatically available context. M3 compared no-weather, cached, and cold-mock latency. M5 compared a naive client and the gateway across four fault scenarios. These are distinct baselines, not a single universal experiment condition.”

### 18. How many live BMKG calls are in the main results?

**Kris:** “Zero. The quoted November 24 report uses synthetic BMKG-format data. A live classroom exchange is separate evidence and should retain its own source, date, and observed output. The existing results file says the live measurement mode has not been run.”

### 19. Does four of four faults mean 100% availability?

**Kris:** “It means that the tested gateway returned a usable answer within four seconds for four selected failure types. It is not a production availability percentage or a guarantee across arbitrary outages.”

### 20. What happens when there is no weather?

**Kris:** “The gateway can fall back to valid cached data, otherwise the weather service requires manual context. Current suggestions can show NONE and continue without weather rules. Both manual conditions should be entered before presenting that result as weather-aware.”

### 21. Why does a seven-day planner not show seven days of weather?

**Clairine:** “The planner stores intended outfits across seven dates, while BMKG supplies a shorter forecast horizon. Planning can therefore continue beyond forecast availability, but the application must retain the beyond-forecast or unavailable indication.”

### 22. Does the avatar prove fit or phone performance?

**Clairine:** “The avatar represents garment categories and approximate colour rather than fabric drape or size fit. The recorded frame-rate evidence is 59.9 FPS on the documented desktop; laptop and mid-range-phone measurements were not supplied.”

### 23. What are the current research limitations?

**Kris:** “RQ1 reduced duplicates relative to its first stage but missed its MAP improvement target. The corrected RQ2 simulation met its declared coverage and compatibility rule, although selected weights [1,0,0] do not support attributing its gain to rotation. Those research findings remain separate from the current application’s heuristic serving mode.”

### 24. Are purchases and retail labels real?

**Clairine:** “Checkout is simulated, with no real payment processing demonstrated. Retail label attachment is a proposed deployment workflow. The current evidence supports the digital issuance, delivery, lookup, and claim processes.”

### 25. What is the next improvement?

**Both, divided by role:** “The proposed monitored refresh should retain forecast age, respect provider limits, and identify contract failures. A matched v2 client-to-server benchmark must define the network and workload before comparing results. The Homework 3 connection, scheduler cost, responsible owner, and acceptance evidence should be completed before the improvement is presented as submission-ready.”

## VI. Metrics and source reference sheet

The appendix slides provide targeted support rather than a second presentation. Use slide 12 for interfaces, slide 13 for measurement method, slide 14 for the improvement plan, slide 15 for fixture preparation, slide 16 for rubric/submission requirements, and slide 17 for references. Slides 18 and 19 show settings-design and brand references; they should not be used as evidence that an illustrated control is implemented or that a live test passed. Return to slide 11 after answering an appendix-based question.

| Evidence | Values to retain | Meaning and limits |
|---|---|---|
| Legacy M1 | 65.0% (312/480) → 100.0% (480/480) | +35 percentage points; 24 slots × 4 occasions × 5 results; 28 synthetic garments |
| Legacy M2 | 2 → 0 | Automatically available weather only; manual fallback still requires inputs |
| Legacy M3 p50 | 230.35 → 205.93 cached / 287.64 cold mock ms | Warm DB, in-process ASGI, 30 runs per condition |
| Legacy M3 p95 | 254.13 → 229.00 cached / 320.99 cold mock ms | No browser network hop; cached-path budget 500 ms |
| Legacy M4 | 100% mapped; 24/24 bad entries rejected | Contract correctness; baseline has no external feed |
| Legacy M5 | 0/4 naive → 4/4 gateway | Four fault scenarios with usable-answer threshold ≤4 seconds |
| Legacy timeout | 4516.4 ms naive failure → 3296.1 ms gateway usable response | Naive failure duration capped by measurement |
| V2 registration | 500/500 genuine; 0/103,500 false accepted | Separate experiment; limits disabled for validation, tested independently |
| V2 local performance | Catalogue p95 266.7 ms; product recommendation 17.9 ms; outfit suggestion 339.3 ms | Local, warmed API/database; no matched before/after supplied |

Primary file references for rehearsal and verification:

- `docs/RESULTS.md` and `results/2026-11-24T03-49-41Z_offline-mock.json`: exact legacy metrics and experimental scope.
- `apps/api/src/wearhouse/weather/contract.py`: parsed fields, thresholds, and fallback contract.
- `apps/api/src/wearhouse/weather/application.py`: daily aggregation, location and planner weather states.
- `apps/api/src/wearhouse/wardrobe/application.py`: suggestion context, manual overrides, NONE, care-state filtering, and saved-look operations.
- `apps/api/src/wearhouse/recommendations/{application,domain}.py`: current heuristic scoring and hard garment rules.
- `apps/api/src/wearhouse/ownership/application.py`: claim transaction, buyer binding, idempotency, and issuance.
- `apps/web/client/src/routes/store/{Tag,Redeem,Orders}.tsx`: current lookup, key entry/scanning, and receipt flow.
- `apps/web/client/src/routes/wardrobe/{Library,ItemRoute,Fitting,Suggest,Weather}.tsx`: actual form fields and user actions.
- `apps/web/client/e2e/qr.e2e.spec.ts`: camera-fixture and key-QR decoding tests. These are automated test scenarios, not proof that every audience phone has been tested.
- `research/reports/rq3/20261125T150923Z-a2983ef3/report.md`: registration evidence and declared deviations.
- `docs/architecture/release-evidence-perf.md` and `release-evidence-avatar.md`: current local performance and device limits.
- BMKG, *Data prakiraan cuaca terbuka*: https://data.bmkg.go.id/prakiraan-cuaca/ — provider documentation verified in the preceding project analysis on November 26, 2026.

## VII. Rehearsal and submission gate

Conduct one slow rehearsal for accuracy and one uninterrupted timed rehearsal for delivery. In the first, verify each claim against the visible result and record any mismatch. In the second, follow the 10/5/5 timetable, maintain the operator handoffs, and record actual completion times. If the talk runs long, shorten secondary explanation rather than removing the evidence scope or improvement plan. If the demonstration runs long, move the separate private-QR example and optional planner action to discussion. Successful rehearsal claims must be followed by a new reserved credential set for presentation day.

Before the session, confirm these specifications:

- Slide timing labels agree with the twenty-minute format.
- The public QR resolves from an audience phone and shows the intended v2 product.
- Fresh claim and reserve keys belong to the intended environment and account.
- Required wardrobe slots, care states, and attributes support the selected example.
- Live forecast evidence is distinguishable from cached, manual, and mocked context.
- The controlled failure is rehearsed in an isolated environment or available as a labelled recording.
- The results file is available offline and its scope is stated in the spoken script.
- The Homework 3 source and connection are supplied, or the pending state is explicitly retained.
- Both presenters understand their evidence areas and can answer without fabricating certainty.
- The FYP-owner consent, actual AI assistance, contribution log, peer assessment, APA references, and 12–15-page report requirements are checked.

The review underlying this guide inspected the deck and implementation evidence; it did not run the presentation-day deployment, consume activation keys, inject live faults, or complete a new benchmark. Presentation readiness therefore depends on completing the operational checks above. The final standard is consistency between the claim, the demonstrated state, and the evidence available to support it.
