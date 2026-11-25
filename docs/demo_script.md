# Live demo script (draft)

Four runs, all done from the web page (http://127.0.0.1:8000/). **Draft:** check the order and wording against deck slide 9.

**Before class:** `.\run_demo.ps1 -Reset` (this wakes Neon and gives clean data). Confirm the health line says `db=neon fault=none`.
If the venue wifi is dead, use `.\run_demo.ps1 -Offline -Reset` (SQLite + frozen real BMKG sample) or play the backup MP4.

1. **Normal run (I1 → I2 → I3).** Pick an occasion → Recommend. The badge shows **LIVE** with BMKG time, temperature and description,
   and 5 outfits appear. Recommend again: the badge shows **CACHED** ("cache hit") and no new I2 row appears in the interface log.
   Point at rain → rain-ready shoes/outer, hot → no heavy outerwear.
2. **BMKG fails (Ch 9 discontinuity).** Demo controls → fault `timeout` → Set → Recommend. After about 3 s the badge shows
   **CACHED** ("fallback after timeout") and outfits still appear. The interface log shows the failed I2 row (`timeout`).
   Repeat with `http500`, `malformed`, `missing_fields` if there is time.
3. **Cold failure → manual.** Keep a fault on, click "Clear weather cache", Recommend: the badge shows **MANUAL_REQUIRED** and the two-tap
   Rainy/Dry, Hot/Normal prompt appears. Answer it → outfits come back (source **MANUAL**). Set fault back to `none`.
4. **Garment registration (RQ3).** Issue a tag. Scan its QR (or open the tag link): the garment is added to the wardrobe.
   Entering the matching activation key afterwards returns "invalid code", because the tag was already used.
   Issue a second tag and enter its key instead: it adds the garment with the same result. Its QR can no longer add it again.

**Close:** show `docs/RESULTS.md` (written by `measure.py`) for M1–M5.
