# Wearhouse landing: scrollcraft report (2026-11-26)

Brief: self-authored under the owner's explicit creative delegation (see BRIEF.md). Not re-interviewed.

**Grammar: chaptered editorial.** The brief asks for distinct scenes (Store, Key, Wardrobe, Weather, Week, Friends) and an editorial-premium register with a game-dashboard edge. Filmic one-shot and continuous world lose to "not one unbroken world"; live surface would need a computing replica of the app when the real app is one click away; typographic poster discards the product screens; gallery suits a range, not a journey; split stage has no two-sided argument; rhythmic cutlist contradicts the calm open and calm middle of the energy curve.

**Signature move.** Scroll types the example key WEAR-HOUS-EXAM-PLE2 one group at a time (labelled "Example key, not a real one"); each completed group releases one hinge of the wardrobe; on the fourth the doors swing open and a real catalogue piece (live from the public API, drawn silhouette when offline) settles onto the shelf. Pure CSS driven by the engine's `--sc-p`; the engine is copied unchanged.

**Fingerprint gate.** Registry was empty: nothing to clear. Row appended.

**Journey and feeling curve.** Title (curiosity) → Store (desire: real-source pieces, simulated prices said plainly) → Key (anticipation, then delight at the peak) → Weather and week (reassurance: BMKG, honest horizon) → Friends (belonging: private by default) → Colophon (readiness: Open Wearhouse).

**Peak.** The pinned key/wardrobe chapter (span 4.4, the largest on the page), with a held pause before the fourth group.

**Score.** Title `flow` · Store `reveal` (+ live count) · Key `pin` (signature) · Weather `parallax` · Friends `reveal` · Colophon `flow`: four families, no device twice in a row, no `scrub`.

**Assets.** Real Focus-mode screens of the live app (synthetic demo account, no keys or personal data) in `shots/`, compressed to WebP in `public/landing/` (8 files, about 180 KB). No generated imagery: `KIE_AI_API_KEY` is not set; adding one later can bring the photoreal garments and sets the brief describes.

**Verified.** Shoot harness at desktop, 390×844 and reduced motion (contact sheets in `lab/`, gitignored): all cues clear 4.5:1; the peak is the largest visual change; reduced motion shows the finished composition. End-to-end (`e2e/landing.e2e.spec.ts`): both CTAs reachable by keyboard and open the app routes; only public endpoints, no Authorization header, no suggestion request; with the API unreachable the page renders fully with no live tiles, counts or errors; reduced motion is static and complete; readable with JavaScript disabled.

**Feel check (cold scroll, one word per chapter):** curious, interested, *wow*, calm, warm, done. Matches the intended curve; the felt peak is the doors opening.

**Not verified.** A real phone (iOS video/touch behaviour does not apply here: no video, but touch scroll pacing is untested on device). The harness flags a short still stretch as the peak pins in (27–35% desktop): the stage is grounded with its greeting line, which the cue contract allows.
