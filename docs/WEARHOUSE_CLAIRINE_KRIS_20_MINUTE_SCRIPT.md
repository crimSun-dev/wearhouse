# Wearhouse: 20-minute presentation script

**Presenters:** Clairine Safa Naqayya and Kris Aaron Witanto  
**Deck:** `Wearhouse PPT SIS INTGRATION.pptx` — 19 slides, supplied November 26, 2026  
**Delivery:** 10-minute presentation, 5-minute demonstration, 5-minute discussion

Wearhouse is a digital wardrobe system that connects garment registration, outfit composition, and weather information within a common application. This script follows the supplied presentation, explains the implemented program, and distinguishes the current Wearhouse interface from the earlier integration experiment used for the measured comparisons.

The prose follows the supplied *Academic Writing Style Replication Prompt, Version 2.0*: definitions precede application, transitions connect the analytical stages, and claims remain qualified by their evidence. Operational directions appear separately from spoken passages. Read the passages labelled **Say**; use the directions to coordinate the presentation.

## I. Timing and slide order

The supplied PPT currently specifies a five-minute main talk. This script expands that talk to ten minutes to meet the requested **20-minute total session**. The demonstration occupies minutes 10–15; audience discussion occupies minutes 15–20. Because audience questions cannot be predicted, Section IV provides a timed discussion sequence for use when the audience has no immediate questions.

| Session time | Slide | Speaker | Duration |
|---|---|---|---:|
| 00:00–00:30 | 1 — Cover | Clairine | 0:30 |
| 00:30–01:20 | 2 — A digital record for each garment | Clairine | 0:50 |
| 01:20–02:50 | 3 — The tag and the activation key | Clairine | 1:30 |
| 02:50–03:55 | 4 — Building a look from your wardrobe | Clairine | 1:05 |
| 03:55–05:15 | 5 — How weather changes an outfit | Kris | 1:20 |
| 05:15–06:55 | 6 — How Wearhouse connects clothes and weather | Kris | 1:40 |
| 06:55–08:30 | 7 — Before and after BMKG | Kris | 1:35 |
| 08:30–09:20 | 8 — When BMKG is unavailable | Kris | 0:50 |
| 09:20–09:45 | 14 — The next test for Wearhouse v2 | Clairine | 0:25 |
| 09:45–10:00 | 9 — Demo handoff | Both | 0:15 |
| 10:00–15:00 | 10 — Wearhouse live demo | Both | 5:00 |
| 15:00–20:00 | 11 — Questions | Both | 5:00 |

Slide 14 is intentionally brought forward from the appendix so that the improvement plan receives spoken coverage. Prepare a slide-show hyperlink or practise jumping to slide 14 and then returning to slide 9. Slides 12–19 otherwise remain supporting material. Rehearse the spoken passages at approximately 120–140 words per minute, allowing the remaining time for pointing, slide changes, and brief pauses. The timetable is a rehearsal target; it is not a guarantee of delivery speed.

## II. Ten-minute spoken presentation

### Slide 1 — Cover

**Clairine | 00:00–00:30**

**Action:** Face the audience. Introduce both presenters before indicating the title.

**Say:**

> Wearhouse is a digital wardrobe system connecting garment records, saved outfits, and weather information. Good afternoon. I am Clairine Safa Naqayya, presenting with Kris Aaron Witanto. The project develops the Digital Wardrobe FYP into an integration case study. This presentation follows a garment from its public tag to an outfit, then examines how BMKG influences suggestions and how the integration performs.

### Slide 2 — A digital record for each garment

**Clairine | 00:30–01:20**

**Action:** Point first to the physical jacket and then to its digital record. Identify the illustration as a design mockup.

**Say:**

> A wardrobe item records a particular piece of clothing owned by a user. A catalogue page describes the product, while the wardrobe identifies the piece available for selection. After registration, the denim jacket carries a garment slot and relevant details, such as colour and size. The same item can appear in several saved looks without another registration. This connection addresses the separation between acquiring clothing and using it in daily outfit decisions. Chapters 1 and 2 establish this user need and the processes required to support it. The image illustrates the design; the demonstration will use the running program.

### Slide 3 — The tag and the activation key

**Clairine | 01:20–02:50**

**Action:** Indicate the public tag, then explain private purchaser delivery. Use a physical sample tag if available. Do not project a normal user key.

**Say:**

> Garment registration separates public discovery and private claiming. The public QR links to a garment unit’s serial, allowing product inspection and a signed-in wishlist action. This lookup does not change the wardrobe. The private activation key, also described as a licence key, authorizes one claim through Redeem. Following validation, the application records the unit against the user and labels the wardrobe item Official. An independent attempt with the consumed key is rejected.
>
> In the proposed retail workflow, a hangtag or care label would carry the public QR, while a receipt or protected panel would deliver the private key. Current Wearhouse supports digital issuance, printable tags, and simulated order delivery; participating physical retailers have not been established. A separate private QR can fill the key field inside Redeem, where the user confirms submission. Each key belongs to one garment unit. Official records its Wearhouse claim and catalogue provenance, without independently certifying retail authenticity. A photographed public tag therefore supports discovery without providing a claim credential.

### Slide 4 — Building a look from your wardrobe

**Clairine | 02:50–03:55**

**Action:** Trace the sequence from the unofficial shirt to the jacket, saved look, planner, and wear log.

**Say:**

> Unofficial clothing enters through user declaration without a catalogue activation key. Through Add an unofficial piece, the user enters a name and slot, with optional category, colour, and size details. A thrifted linen shirt can occupy Top alongside the registered jacket in Outerwear. Its Unofficial label distinguishes a record without verified catalogue serial or acquisition provenance. Relevant attributes can be reviewed in the item inspector before using them in suggestions. This pathway incorporates existing clothing without requiring a purchase.
>
> A saved look links the selected wardrobe items to their corresponding slots, so composing another outfit does not consume their activation keys again. The avatar provides a category-based visual approximation of those selections. Planning records an intended outfit for a date, whereas the wear log records what the user actually wore. Kris will now explain how weather information enters this process.

### Slide 5 — How weather changes an outfit

**Kris | 03:55–05:15**

**Action:** Follow the four stages on the slide. Say “selected date” rather than promising an outing-time selector.

**Say:**

> Weather integration introduces external forecasts into outfit selection. The user saves a location code, chooses a date and occasion, and requests wardrobe suggestions. BMKG, Indonesia’s meteorological agency, provides village-level forecasts in three-hour intervals across a three-day horizon. The application retrieves JSON data, validates its fields, and transforms the forecast into conditions for the garment rules. The Indonesian word “hujan” indicates rain, while temperatures of at least thirty-two degrees Celsius indicate heat. These conditions remove unsuitable combinations before ranking.
>
> In the current implementation, suggestions use a daily summary: any rainy forecast slot can activate the rain rule, and any hot slot can activate the heat rule for that date. Rain requires suitable footwear or outerwear, while heat excludes heavy outerwear. Consequently, the program does not guarantee the weather for a precise departure time. A seven-day planner also extends beyond BMKG’s forecast horizon, so later days must retain an unavailable or beyond-forecast status. This transformation illustrates Chapter 5: information exchanged between systems becomes a usable input to an operational decision.

### Slide 6 — How Wearhouse connects clothes and weather

**Kris | 05:15–06:55**

**Action:** Trace a private claim and a forecast request separately. Point to the external-system boundaries. Keep slide 12 available for interface questions.

**Say:**

> The architecture organizes this workflow around three application components: the browser, the FastAPI backend, and PostgreSQL. The React and TypeScript browser provides the interface, the backend validates requests and applies application rules, and the database stores garment units, wardrobe records, saved looks, and cached forecasts. Two external services have distinct responsibilities. Neon Auth supports sign-in and supplies the signing keys used to verify access tokens. BMKG supplies forecast data to the backend. The browser therefore requests an outfit through Wearhouse rather than contacting BMKG directly.
>
> A private claim crosses the interface as a protected JSON request containing the activation key. The backend verifies the user, checks the credential and garment state, and records the successful claim within a database transaction. A transaction groups related changes so that a failure does not leave a partially completed ownership record. Public discovery follows a separate read operation, which explains why opening a tag does not create ownership. A forecast request crosses another boundary: the backend sends the location code to BMKG, validates the response, and stores an accepted forecast for subsequent use. The interface appendix identifies the payload, trigger, owner, and failure response for each connection. These explicit boundaries address Chapters 11 and 12 by making responsibility and data exchange reviewable.

### Slide 7 — Before and after BMKG

**Kris | 06:55–08:30**

**Action:** Introduce the experiment caption before reading the comparisons. Point to the baseline and integrated columns. Use slide 13 if methodological detail is requested.

**Say:**

> Integration performance was evaluated through the earlier version-one experiment dated November twenty-fourth. This distinction is essential: the table reports a synthetic BMKG-format feed, a warmed Neon database, and in-process Python requests, with zero live BMKG calls. The results therefore provide controlled integration evidence rather than a benchmark of the current public Wearhouse interface. The baseline and integrated conditions were compared using predefined measures. Across twenty-four forecast slots, four occasions, and five recommendations, weather-rule compliance increased from three hundred and twelve of four hundred and eighty outfits to all four hundred and eighty. This represents an increase from sixty-five to one hundred percent, or thirty-five percentage points.
>
> Manual weather inputs decreased from two to zero when forecast data were available. The ninety-fifth-percentile recommendation latency was approximately two hundred and fifty-four milliseconds at baseline, two hundred and twenty-nine with cached weather, and three hundred and twenty-one with a cold mock request. The gateway also produced a usable answer within four seconds for all four injected fault scenarios, compared with none for the naive client. These findings support Chapter 15, Test and Analysis, while retaining important limits. Perfect compliance checks whether weather reaches the hard rules; it does not demonstrate user satisfaction or forecast accuracy. The latency difference also partly reflects changes in the number of candidate outfits after filtering.

### Slide 8 — When BMKG is unavailable

**Kris | 08:30–09:20**

**Action:** Follow the fallback stages from left to right. Explain the current `NONE` state if it appears during demonstration.

**Say:**

> Discontinuity management concerns how the integration responds when an external dependency becomes unavailable or returns invalid information. Wearhouse first accepts a valid forecast from its three-hour fresh cache. When a refresh is required, the gateway attempts BMKG and, following failure, may retain valid cached data up to six hours old. If no usable forecast remains, the weather service reports that manual information is required. In current suggestions, unavailable weather can appear as NONE, meaning that rain and heat rules were not applied. The presenter must then enter both manual conditions before describing the result as weather-aware. Chapter 9 is therefore demonstrated through explicit source states and a controlled recovery process.

### Slide 14 — The next test for Wearhouse v2

**Clairine | 09:20–09:45**

**Action:** Jump to appendix slide 14. Keep the “proposed work” and estimate labels visible.

**Say:**

> The proposed improvement is monitored background refresh, combined with a matched benchmark of the current client and API. Its estimated effort is two to four developer-days plus evaluation, subject to scheduler cost and deployment conditions. Assessment should verify forecast age, field validation, and the four failure responses. The Homework 3 trend and citation remain to be supplied before submission.

**Preparation note:** Once the actual Homework 3 material is available, replace the final sentence with one accurate connection to its named trend and source. Do not imply that a missing reference has been completed.

### Slide 9 — Demo handoff

**Both | 09:45–10:00**

**Action:** Return to slide 9, then open slide 10 and the prepared browser.

**Clairine — say:**

> The demonstration will now follow a public lookup, a private claim, and a saved outfit containing an unofficial item.

**Kris — say:**

> The final steps will identify the forecast source and demonstrate the prepared failure response.

## III. Five-minute live demonstration

Use slide 10 as the holding slide. Elapsed times below start at the beginning of the demonstration; add ten minutes for the session clock. Clairine operates the wardrobe flow and Kris operates weather and failure handling. The non-operating presenter watches the timer and directs the audience to the relevant evidence.

### Demo 00:00–00:30 — Public lookup

**Clairine operates.** Open the verified public lookup for fixture A. Invite audience scanning without requiring every person to complete the step. Show the garment name and discovery message. The presenter’s wardrobe count should remain unchanged.

**Clairine — say:**

> The public QR opens the record associated with this garment serial. Audience members may scan it to inspect the product. The lookup does not register the garment to a viewer, so the wardrobe count remains unchanged. Ownership requires the separate private key.

**Kris checks:** Correct v2 app and expected product; no private key on the audience slide. If scanning is slow, use the prepared lookup tab after fifteen seconds and keep the QR available for later.

### Demo 00:30–01:35 — Private claim and replay

**Clairine operates.** Open Redeem as the intended fixture-B user. Paste the reserved key, submit it once, and show the resulting Official garment in Wardrobe. Start a new redemption attempt with the consumed key and show rejection. Return to Wardrobe and confirm that only one additional item exists.

**Clairine — say:**

> This activation key belongs to a disposable presentation unit. Submitting it creates one Official wardrobe item for the assigned user. The record identifies the garment and its slot. An independent attempt to claim the same key again should receive a generic rejection, while the wardrobe should retain only one copy of the claimed unit.

**After the observed result, say:**

> The claim succeeded once, and the repeated claim did not create another item. The distinction between public discovery and private claiming is now visible in the program.

Use that final sentence only if the observed result supports it. The replay must be a new claim intent; an automatic retry with the same idempotency key can correctly return the original successful result without another mutation.

### Demo 01:35–02:05 — Unofficial clothing

**Clairine operates.** Open **Wardrobe → Add an unofficial piece**. Enter “My thrifted linen shirt,” select **Top**, optionally enter beige as the colour, and save. Show the Unofficial label.

**Clairine — say:**

> A garment already owned can enter through manual declaration. This shirt requires a name and slot rather than a licence key. Its Unofficial label preserves the distinction from catalogue-backed claims, while allowing the user to select it when composing a look.

### Demo 02:05–02:35 — Save a look

**Clairine operates.** Open **Fitting room**, select the claimed outerwear and unofficial shirt, and add the prepared bottom and footwear. Enter **Campus Rain Demo** in Look name and select **Save look**. Show the saved look. Use a preassembled fitting-room tab only if it contains the intended current items.

**Clairine — say:**

> The fitting room connects wardrobe items through their garment slots. Saving this look preserves those selections without redeeming their keys again. The preview represents garment categories; the saved record can subsequently support planning, while actual wear is recorded separately. Kris will now examine the weather input.

### Demo 02:35–03:30 — Forecast-aware suggestion

**Kris operates.** Open **Weather**. Show the saved Kemayoran code `31.71.03.1001`, actual source, update time, and forecast entries. Open **Outfit suggestions**, choose a date with available slots and **Campus**, and leave Rain and Hot as **From forecast**. Show an actual suggestion and its explanation.

**Kris — say:**

> This forecast is associated with the saved location code. Its source and update time indicate whether the application retrieved data or reused a cached response. Suggestions use the selected date’s rain and heat summary to apply the relevant rules before ranking combinations. The explanation identifies the conditions used for this result.

**Choose the observed branch:**

- **LIVE:** “The displayed source is LIVE, indicating a successful gateway fetch. The update time identifies when the application obtained the feed.”
- **CACHED:** “The displayed source is CACHED. This is a reused forecast, so the demonstration is not claiming a new BMKG exchange on this request.”
- **NONE:** “The displayed source is NONE. Weather rules were not applied, so this result cannot yet be described as weather-aware. Both manual conditions must be supplied.”
- **Mock/test fixture:** “This environment uses a declared test feed. It demonstrates the contract and rule behaviour rather than a live BMKG exchange.”

If the forecast is dry, explain the actual dry conditions. Do not describe rain protection as being triggered when the displayed context is not rainy. Reserve a clearly labelled rainy test condition for the failure fixture or Q&A.

### Demo 03:30–04:25 — Controlled failure and recovery

**Kris operates.** Use the rehearsed failure environment. The current v2 UI does not expose the legacy fault switch. The available legacy runner and fault controls may be used in a separately labelled tab, with its own synthetic data.

**If using the isolated legacy test, say before switching:**

> This tab is the isolated version-one integration test, which produced the earlier measurements. The prepared timeout affects its weather dependency, while the current Wearhouse account remains separate. The next request should either recover through its valid cached forecast or identify that manual weather is required.

**Actions:** With cache primed, enable timeout, request recommendations, and show the CACHED fallback note/log. If rehearsed within the remaining time, clear that test cache, request again, and answer both manual weather fields. Restore the legacy fault setting to none afterwards.

**After a successful cached recovery, say:**

> The response identifies CACHED because the external request failed and a valid stored forecast remained available. This is the recovery behaviour evaluated by the fault experiment.

**If showing current v2 manual recovery instead:** Open Suggestions and set **Rain** and **Hot** explicitly to Yes or No; point to **MANUAL**. State: “Both conditions now come from the user. This demonstrates the manual-input path; clearing a location or overriding weather alone does not constitute an injected BMKG outage.”

The recording of a controlled failure is the fallback if no isolated live failure setup is ready. Introduce it as a recording and retain the original environment/source labels.

### Demo 04:25–05:00 — Evidence and handoff

**Kris operates.** Return briefly to the measurement report or slide 7. Clairine confirms the observed product outcomes.

**Clairine — say:**

> The demonstration has shown public discovery, a single private claim, unofficial entry, and composition of a saved look. Each stage preserves a distinct record and purpose.

**Kris — say:**

> The weather step also identifies the data source and the prepared recovery behaviour. The comparative values remain those of the dated legacy experiment. A matched current-version benchmark is the next evaluation requirement. Thank you. The presentation can now move to questions.

**Action:** Display slide 11 at session minute 15.

## IV. Five-minute Q&A and guided discussion

Audience questions take priority. Clairine answers FYP, garment, and user-workflow questions; Kris answers architecture, BMKG, test, and failure-handling questions. Aim for forty-five seconds per answer, then allow a brief follow-up. Use the guide’s evidence references when clarification is required.

If the room is quiet, invite questions for approximately ten seconds and introduce the following five evidence points. These are prepared discussion topics, not questions falsely attributed to the audience. If real questions fill the period, omit the corresponding prepared topic.

### 15:00–16:00 — Verification and repeated claims

**Clairine — invitation:**

> Thank you. Questions may address the garment workflow, the external interfaces, or the measurement results. While the audience considers those areas, the distinction between identifying a garment and claiming it warrants a final clarification.

**Clairine — explanation:**

> A public serial supports lookup, while a private key supports the controlled claim. The same wardrobe item can appear in multiple saved looks because those looks refer to the item after registration. The key is not reused during composition. This design separates product information, ownership state, and outfit selection, allowing each process to apply its own validation requirements.

**Kris — evidence:**

> The current registration experiment accepted five hundred genuine activations and rejected all one hundred and three thousand five hundred tested false claims. That finding is bounded by its test conditions and does not establish that every possible attack is prevented.

### 16:00–17:00 — Meaning of the measured improvement

**Kris — explanation:**

> The compliance result assesses whether the software applies its declared rain and heat rules. Once weather reaches a hard filter, complete compliance is expected for the retained combinations. The baseline establishes what happens when those same weather conditions are ignored. Consequently, the increase from sixty-five to one hundred percent supports the correctness of the integration path, while user satisfaction and meteorological prediction accuracy require separate evaluation. The latency measurements similarly describe the stated in-process workload and cannot be transferred directly to a public browser session.

**Clairine — implication:**

> The product claim should therefore remain proportionate to that evidence: the application can make its configured weather conditions operational in outfit selection. Its value to Indonesian users still requires evaluation with representative users and deployment conditions.

### 17:00–18:00 — Practical use and unofficial garments

**Clairine — explanation:**

> Manual declaration allows existing or thrifted clothing to participate without a retailer issuing a code. The user supplies its descriptive information and garment slot, and may review the attributes that influence suggestions. This approach expands the usable wardrobe while preserving the source distinction between catalogue-backed and self-declared records. The avatar then presents the selected categories and approximate colours. It does not measure body dimensions, simulate fabric drape, or establish whether a physical size will fit.

**Kris — implication:**

> Data provenance remains relevant after entry. An item’s attributes may originate from catalogue rules or user corrections, and the application should expose that origin rather than presenting every characteristic as an independently verified retail fact.

### 18:00–19:00 — Failure handling and current limitations

**Kris — explanation:**

> The fallback policy protects continuity through a fresh cache, a bounded older cache, and explicit manual conditions. However, an unavailable forecast in current v2 suggestions can produce a NONE source, under which weather rules are not applied. That state must remain visible because an outfit returned without weather information cannot be evaluated as though BMKG supplied it. A manual choice restores explicit context only when the relevant conditions have been entered. The controlled failure experiment and the current user-interface behaviour should therefore be explained separately.

**Clairine — implication:**

> A useful interface improvement would make the transition from unavailable weather to both manual inputs more explicit. That proposal should be assessed through a documented test rather than described as a completed feature.

### 19:00–20:00 — Improvement and closing evaluation

**Clairine — explanation:**

> The next development decision is to connect the proposed improvement to the actual Homework 3 trend and confirm its operational cost, responsible owner, and assessment criteria. Monitored refresh has value only if it maintains understandable forecast age and reduces avoidable delays without concealing failures. The current architecture provides a defined location for that change through the weather gateway.

**Kris — closing:**

> The next evaluation should compare baseline and integrated current-version requests under the same client, network, dataset, and concurrency conditions. It should also repeat field validation and the four failure scenarios while retaining source labels. Wearhouse’s integration is therefore assessable through three linked requirements: traceable garment state, explicit weather provenance, and reproducible measurement. Further deployment claims should be based on that evidence. Thank you.

## V. Delivery notes

Do not read interface IDs, file paths, or full reference entries aloud. Explain “p95” once as the ninety-fifth percentile: approximately ninety-five percent of the measured requests completed within that value. Say “thirty-five percentage points” for 65% to 100%. Pause when switching from present product behaviour to historical measurement evidence.

The words LIVE, CACHED, MANUAL, and NONE should be spoken according to the observed result. An unavailable condition is useful evidence when explained accurately. Avoid declaring a test passed before its output appears. If the demonstration fails, use the response lines in the companion guide and continue with the labelled recording.

For a room that grants only fifteen minutes, retain the PPT’s original five-minute talk notes, the five-minute demonstration, and five-minute Q&A. This is a contingency only; the main script above is planned for twenty minutes.
