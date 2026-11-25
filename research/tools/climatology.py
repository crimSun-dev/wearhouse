"""Cited Jakarta climatology for the RQ2 simulation (replaces the ASSUMED placeholder; complete-wearhouse-tdd follow-up).

Station: BMKG Stasiun Meteorologi Kemayoran, Jakarta (WMO 96745), period 1991-2020.

- rain[m] = Number_of_Days_with_Precipitation_>=_1_mm (WMO 1991-2020 normals, BMKG submission) / days in month.
- hot[m]  = share of observed days with daily max temperature >= 32 C, from the station's daily series in NOAA
  GHCN-Daily (ID000096745), 1991-2020. The normals publish only >= 30/35 C counts, so the 32 C share is computed
  from the daily data and the daily series is validated month by month against the official >= 30 C counts and
  the mean daily maximum (reported in the manifest).

Both sources are public NOAA NCEI archives (US government data, no terms to accept). Downloads go to
research/data/climate/ (git-ignored); their sha256 values, the computed values and the validation go to
research/manifests/jakarta_climate.json; the values are written into research/configs/rq2.json.

    research/.venv/Scripts/python.exe research/tools/climatology.py            # use local files (verify sha256)
    research/.venv/Scripts/python.exe research/tools/climatology.py --refresh  # download again, re-pin
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "research" / "data" / "climate"
MANIFEST = ROOT / "research" / "manifests" / "jakarta_climate.json"
CONFIG = ROOT / "research" / "configs" / "rq2.json"
SOURCES = {
    "wmo_normals": {
        "file": "StasiunMeteorologiKemayoran_96745.csv",
        "url": "https://www.ncei.noaa.gov/data/oceans/archive/arc0216/0253808/6.6/data/0-data/"
               "Region-5-WMO-Normals-9120/Indonesia/CSV/StasiunMeteorologiKemayoran_96745.csv",
        "citation": "WMO Climatological Standard Normals for 1991-2020 (NCEI Accession 0253808), station 96745 "
                    "Stasiun Meteorologi Kemayoran, submitted by BMKG. NOAA National Centers for Environmental "
                    "Information.",
    },
    "ghcn_daily": {
        "file": "ID000096745.csv",
        "url": "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/ID000096745.csv",
        "citation": "Menne, M. J., et al. (2012). Global Historical Climatology Network - Daily (GHCN-Daily), "
                    "station ID000096745 JAKARTA/OBSERVATORY. NOAA National Centers for Environmental Information.",
    },
}
HOT_C = 32.0
DAYS_IN_MONTH = [31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # Feb averaged over leap years


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fetch(refresh: bool) -> dict[str, str]:
    DATA.mkdir(parents=True, exist_ok=True)
    pinned = json.loads(MANIFEST.read_text(encoding="utf-8"))["files"] if MANIFEST.exists() and not refresh else {}
    out = {}
    for key, s in SOURCES.items():
        p = DATA / s["file"]
        if refresh or not p.exists():
            req = urllib.request.Request(s["url"], headers={"User-Agent": "wearhouse-research/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                p.write_bytes(r.read())
        digest = sha256(p)
        if key in pinned and pinned[key]["sha256"] != digest:
            sys.exit(f"{p} sha256 {digest} != pinned {pinned[key]['sha256']}; use --refresh to re-pin deliberately")
        out[key] = digest
    return out


def wmo_rows(path: Path) -> dict[tuple[str, str], list[float]]:
    """(parameter code, calculation name) -> 12 monthly values from a WMO normals station sheet."""
    rows = list(csv.reader(path.open(encoding="utf-8-sig")))
    found = {}
    for i, r in enumerate(rows):
        if r and r[0] == "WMO_Number" and len(r) > 4 and r[4] == "January":
            for d in rows[i + 1:]:
                if not d or d[0] in ("", "Parameter_Code"):
                    break
                try:
                    found[(d[1], d[2])] = [float(v) for v in d[4:16]]
                except ValueError:  # year-of-extreme rows such as '1992/24'; not needed
                    continue
    return found


def daily_tmax(path: Path) -> dict[int, list[float]]:
    by_month: dict[int, list[float]] = defaultdict(list)
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            d, t = r.get("DATE", ""), (r.get("TMAX") or "").strip()
            if t and "1991-01-01" <= d <= "2020-12-31":
                by_month[int(d[5:7])].append(int(t) / 10)  # GHCN-Daily TMAX: tenths of a degree C
    return by_month


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    digests = fetch(a.refresh)
    wmo = wmo_rows(DATA / SOURCES["wmo_normals"]["file"])
    rain_days, ge30, tmean = wmo[("2", "Count")], wmo[("121", "Count")], wmo[("3", "Mean")]
    tmax = daily_tmax(DATA / SOURCES["ghcn_daily"]["file"])
    monthly, validation = {}, {}
    for m in range(1, 13):
        xs, dim = tmax[m], DAYS_IN_MONTH[m - 1]
        monthly[str(m)] = {"rain": round(rain_days[m - 1] / dim, 3), "hot": round(sum(t >= HOT_C for t in xs) / len(xs), 3)}
        validation[str(m)] = {
            "daily_days": len(xs),
            "share_ge30_daily": round(sum(t >= 30 for t in xs) / len(xs), 3),
            "share_ge30_wmo": round(ge30[m - 1] / dim, 3),
            "mean_tmax_daily": round(sum(xs) / len(xs), 2),
            "mean_tmax_wmo": tmean[m - 1]}
    worst = max(abs(v["share_ge30_daily"] - v["share_ge30_wmo"]) for v in validation.values())
    MANIFEST.write_text(json.dumps({
        "name": "jakarta_climate", "station": "BMKG Stasiun Meteorologi Kemayoran, Jakarta (WMO 96745)",
        "period": "1991-2020", "built_on": date.today().isoformat(),
        "method": {"rain": "WMO normals days with precipitation >= 1 mm / days in month",
                   "hot": f"share of observed GHCN-Daily days with TMAX >= {HOT_C} C",
                   "validation": f"daily vs WMO share of days >= 30 C: max abs difference {worst:.3f}"},
        "files": {k: {"path": f"research/data/climate/{SOURCES[k]['file']}", "url": SOURCES[k]["url"],
                      "sha256": digests[k], "citation": SOURCES[k]["citation"]} for k in SOURCES},
        "monthly": monthly, "validation": validation}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    cfg["climatology"] = {
        "status": f"CITED: Jakarta Kemayoran (WMO 96745) 1991-2020; rain = WMO normals rain days (>= 1 mm) per day; "
                  f"hot = share of days with max >= {HOT_C:g} C from GHCN-Daily (validated against the normals, max "
                  f"difference {worst:.3f}). See research/manifests/jakarta_climate.json.",
        "source": "research/manifests/jakarta_climate.json",
        "monthly": monthly}
    CONFIG.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(monthly))
    print(f"validation: max |daily - WMO| share of days >= 30 C = {worst:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
