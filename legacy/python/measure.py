"""measure.py — Ch 15 measurement harness (interface I6).

    python measure.py                 # offline: synthetic 24-slot feed, temp SQLite, no network
    python measure.py --live          # real BMKG (a handful of calls) — ask before the first run
    python measure.py --db-url "$DATABASE_URL" --yes   # measure against Neon (RESETS demo data there)

Writes results/<timestamp>.json and regenerates docs/RESULTS.md. Metrics and pass
conditions are fixed in the TDD (§4 Phase 5) and copied below; do not edit them after
seeing results. Nobody writes numbers into RESULTS.md by hand.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import json
import platform
import random
import shutil
import statistics
import sys
import tempfile
import time
import warnings
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

warnings.filterwarnings("ignore", message="Using .httpx. with .starlette.testclient.")
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text

from app.config import DEFAULT_FIXTURE, REPO_DIR, Settings
from app.db import assert_legacy_target, backend_name, make_engine
from app.domain import Garment, Outfit
from app.main import create_app
from app.rules import Context, heat_ok, rain_ok
from app.scoring import recommend
from app.seed_data import DEFAULT_ADM4, seed_wardrobe
from app.seeding import reset_demo
from app.weather import (
    BMKG_URL,
    BMKGFormatError,
    HttpBMKGClient,
    StaticBMKGClient,
    fault_transport,
    utcnow,
    validate_entry,
)

REC = "/api/v1/outfits/recommend"
API_KEY = "measure-key"
HEADERS = {"X-API-Key": API_KEY, "X-Interface": "I6"}
OCCASIONS_M1 = ("campus", "casual", "worship", "wedding")
FAULTS = ("timeout", "http500", "malformed", "missing_fields")
INITIAL_FAULT_FOR_TESTS = "none"  # tests flip this to prove the fault=none guard works

# Fixed before any run (TDD §4 Phase 5). Do not edit after seeing results.
PASS = {
    "M1": "integrated >= 95 % of top-5 outfits pass rain+heat checks (24 slots x 4 occasions)",
    "M2": "integrated needs 0 manual inputs on LIVE/CACHED (baseline needs 2: rain, hot)",
    "M3": "p95 <= 500 ms with cached weather and warm DB; cold BMKG reported separately",
    "M4": "100 % of forecast entries mapped correctly; 24/24 bad entries rejected",
    "M5": "usable answer <= 4 s under 4/4 faults (timeout, 500, malformed, missing fields)",
}
USABLE_WITHIN_MS = 4000.0
CACHED_P95_LIMIT_MS = 500.0


class MeasurementError(RuntimeError):
    pass


class ColdDatabaseError(MeasurementError):
    pass


# ----------------------------------------------------------------- inputs
_DESCS = [("Cerah", 3), ("Cerah Berawan", 3), ("Berawan", 3), ("Hujan Ringan", 3), ("Hujan Sedang", 2),
          ("Hujan Petir", 1)]


def _fmt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def synthetic_feed(seed: int, now: datetime) -> dict:
    """24 three-hourly slots in the real BMKG shape. Values depend only on `seed`."""
    rng = random.Random(seed)
    start = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
    entries = []
    for i in range(24):
        at = start + timedelta(hours=3 * i)
        desc = rng.choices([d for d, _ in _DESCS], weights=[w for _, w in _DESCS])[0]
        entries.append({
            "utc_datetime": _fmt(at), "local_datetime": _fmt(at + timedelta(hours=7)),
            "t": round(rng.uniform(24.0, 35.0), 1), "hu": rng.randint(60, 98), "weather_desc": desc,
        })
    return {"lokasi": {"adm4": DEFAULT_ADM4, "timezone": "Asia/Jakarta", "note": "SYNTHETIC feed from measure.py"},
            "data": [{"cuaca": [entries[0:8], entries[8:16], entries[16:24]]}]}


def _entries(feed: dict) -> list[dict]:
    return [e for day in feed["data"][0]["cuaca"] for e in day]


def _utc(e: dict) -> datetime:
    return datetime.strptime(e["utc_datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def bad_entries(now: datetime | None = None) -> list[tuple[str, dict]]:
    """24 contract violations (M4)."""
    now = now or utcnow()
    good = {"utc_datetime": _fmt(now), "local_datetime": _fmt(now + timedelta(hours=7)), "t": 30, "hu": 80,
            "weather_desc": "Berawan"}

    def var(label, **changes):
        e = dict(good)
        for k, v in changes.items():
            if v is ...:
                e.pop(k)
            else:
                e[k] = v
        return label, e

    later = lambda h: {"utc_datetime": _fmt(now + timedelta(hours=h)), "local_datetime": _fmt(now + timedelta(hours=h + 7))}
    return [
        var("missing t", t=...), var("missing hu", hu=...), var("missing weather_desc", weather_desc=...),
        var("missing local_datetime", local_datetime=...),
        var("null t", t=None), var("null hu", hu=None), var("null weather_desc", weather_desc=None),
        var("t 14.9", t=14.9), var("t 0", t=0), var("t -10", t=-10),
        var("t 40.1", t=40.1), var("t 45", t=45), var("t 99", t=99),
        var("hu -1", hu=-1), var("hu 100.1", hu=100.1), var("hu 250", hu=250),
        var("t as string", t="30"), var("hu as string", hu="80"), var("t as bool", t=True),
        var("73 h ahead", **later(73)), var("10 days ahead", **later(240)), var("2 days old", **later(-48)),
        var("empty description", weather_desc="  "), var("unparseable time", utc_datetime="tomorrow"),
    ]


class RecordingClient:
    """Keeps the last raw payload so M1/M4 can judge against the feed the server actually saw."""

    def __init__(self, inner):
        self.inner = inner
        self.last: dict | None = None
        self.calls = 0

    async def fetch(self, adm4: str, timeout_s: float = 3.0) -> dict:
        self.calls += 1
        payload = await self.inner.fetch(adm4, timeout_s)
        self.last = copy.deepcopy(payload)
        return payload


# ---------------------------------------------------------------- metrics
def m4_validation(feed: dict, now: datetime | None = None) -> dict:
    now = now or utcnow()
    checked = []
    for e in _entries(feed):
        checked.append((e, now))
    real = json.loads(Path(DEFAULT_FIXTURE).read_text(encoding="utf-8"))
    real_now = datetime.fromisoformat(_entries(real)[0]["analysis_date"]).replace(tzinfo=timezone.utc)
    checked += [(e, real_now) for e in _entries(real)]
    correct = 0
    for e, n in checked:
        try:
            s = validate_entry(e, now=n)
        except BMKGFormatError:
            continue
        ok = (s.rain == ("hujan" in e["weather_desc"].lower()) and s.hot == (e["t"] >= 32)
              and s.temp_c == float(e["t"]) and s.humidity == int(e["hu"]) and s.at == _utc(e))
        correct += ok
    bad = bad_entries(now)
    rejected = 0
    for _, e in bad:
        try:
            validate_entry(e, now=now)
        except BMKGFormatError:
            rejected += 1
    pct = round(100.0 * correct / len(checked), 2)
    return {
        "name": "Forecast entries mapped correctly / bad entries rejected",
        "baseline": "n/a",
        "integrated": {"mapped_correct": correct, "mapped_total": len(checked), "pct_mapped": pct,
                       "bad_rejected": rejected, "bad_total": len(bad),
                       "sources": "measured feed + frozen real BMKG sample"},
        "pass_condition": PASS["M4"],
        "passed": pct == 100.0 and rejected == len(bad) == 24,
    }


def _outfit_from_items(items: list[dict]) -> Outfit:
    keys = ("color_hex", "style", "rain_suitable", "heavy", "long_sleeve", "long_bottom", "formality")
    return Outfit(tuple(Garment(id=i["id"], name=i["name"], slot=i["slot"], **{k: i["attrs"][k] for k in keys})
                        for i in items))


def m1_m2(c: TestClient, feed: dict) -> tuple[dict, dict]:
    snapshot = seed_wardrobe()  # weather-blind baseline ranks the same synthetic wardrobe
    entries = sorted(_entries(feed), key=_utc)[:24]
    b_pass = b_total = i_pass = i_total = empty = 0
    manual_inputs: list[int] = []
    sources: Counter = Counter()
    rain_slots = sum("hujan" in e["weather_desc"].lower() for e in entries)
    hot_slots = sum(e["t"] >= 32 for e in entries)
    for e in entries:
        at = _utc(e)
        rain, hot = "hujan" in e["weather_desc"].lower(), e["t"] >= 32
        today = (at + timedelta(hours=7)).date()
        for occ in OCCASIONS_M1:
            for r in recommend(snapshot, Context(rain=False, hot=False, occasion=occ), today):
                b_total += 1
                b_pass += rain_ok(r.outfit, rain) and heat_ok(r.outfit, hot)
            resp = c.post(REC, json={"occasion": occ, "when": at.isoformat()})
            if resp.status_code != 200:
                raise MeasurementError(f"recommend failed: {resp.status_code} {resp.text}")
            body = resp.json()
            src = body["weather"]["source"]
            sources[src] += 1
            manual_inputs.append(0 if src in ("LIVE", "CACHED") else 2)
            if not body["outfits"]:
                empty += 1
            for o in body["outfits"]:
                i_total += 1
                outfit = _outfit_from_items(o["items"])
                i_pass += rain_ok(outfit, rain) and heat_ok(outfit, hot)
    pct = lambda p, t: round(100.0 * p / t, 2) if t else None
    i_pct = pct(i_pass, i_total)
    m1 = {
        "name": "% of top-5 outfits passing rain+heat checks",
        "baseline": {"pct_passing": pct(b_pass, b_total), "passing": b_pass, "total": b_total,
                     "recommender": "same rules, weather ignored (rain=False, hot=False)"},
        "integrated": {"pct_passing": i_pct, "passing": i_pass, "total": i_total,
                       "contexts_without_outfit": empty},
        "contexts": {"slots": len(entries), "occasions": list(OCCASIONS_M1), "rain_slots": rain_slots,
                     "hot_slots": hot_slots},
        "pass_condition": PASS["M1"],
        "passed": i_pct is not None and i_pct >= 95.0,
    }
    m2 = {
        "name": "Manual inputs needed to get a weather-aware outfit",
        "baseline": {"manual_inputs": 2, "note": "a weather-blind app needs the user to state rain and heat"},
        "integrated": {"max_manual_inputs": max(manual_inputs), "mean_manual_inputs": round(statistics.mean(manual_inputs), 3),
                       "requests": len(manual_inputs), "weather_sources": dict(sorted(sources.items()))},
        "pass_condition": PASS["M2"],
        "passed": max(manual_inputs) == 0,
    }
    return m1, m2


def _stats(samples: list[float]) -> dict:
    s = sorted(samples)
    p95 = statistics.quantiles(s, n=20, method="inclusive")[18] if len(s) >= 2 else s[0]
    return {"n": len(s), "p50_ms": round(statistics.median(s), 2), "p95_ms": round(p95, 2),
            "mean_ms": round(statistics.mean(s), 2), "max_ms": round(s[-1], 2)}


def _timed_post(c: TestClient, body: dict, expect_source: str | None = None) -> float:
    t0 = time.perf_counter()
    r = c.post(REC, json=body)
    ms = (time.perf_counter() - t0) * 1000
    if r.status_code != 200:
        raise MeasurementError(f"recommend failed: {r.status_code} {r.text}")
    src = r.json()["weather"]["source"]
    if expect_source and src != expect_source:
        raise MeasurementError(f"expected weather source {expect_source}, got {src}")
    return ms


def m3_latency(c: TestClient, runs: int, cold_runs: int) -> dict:
    manual = {"occasion": "campus", "manual_weather": {"rain": False, "hot": False}}
    c.post(REC, json=manual)  # unmeasured warm-up so series order does not bias the comparison
    base = [_timed_post(c, manual, "MANUAL") for _ in range(runs)]
    c.post(REC, json={"occasion": "campus"})  # make sure a forecast is cached (also a warm-up)
    cached = [_timed_post(c, {"occasion": "campus"}, "CACHED") for _ in range(runs)]
    cold = []
    for _ in range(cold_runs):
        c.post("/api/v1/admin/weather/clear-cache")
        cold.append(_timed_post(c, {"occasion": "campus"}, "LIVE"))
    cached_stats = _stats(cached)
    return {
        "name": "End-to-end /recommend latency (in-process ASGI, DB warm)",
        "baseline": {"no_weather_call": _stats(base)},
        "integrated": {"cached_weather": cached_stats, "cold_bmkg": _stats(cold)},
        "pass_condition": PASS["M3"],
        "passed": cached_stats["p95_ms"] <= CACHED_P95_LIMIT_MS,
    }


async def _naive_attempt(mode: str, healthy: dict) -> dict:
    """A naive client: no timeout, no status check, no validation, no cache."""
    async with httpx.AsyncClient(transport=fault_transport(mode, lambda: copy.deepcopy(healthy)), timeout=None) as cl:
        r = await cl.get(BMKG_URL, params={"adm4": DEFAULT_ADM4})
        e = r.json()["data"][0]["cuaca"][0][0]
        return {"t": e["t"], "rain": "hujan" in e["weather_desc"].lower(), "hot": e["t"] >= 32}


def _naive(mode: str, healthy: dict, cap_s: float) -> dict:
    t0 = time.perf_counter()
    try:
        asyncio.run(asyncio.wait_for(_naive_attempt(mode, healthy), cap_s))
        err = None
    except TimeoutError:
        err = f"no answer after {cap_s:g} s (measurement cap)"
    except Exception as exc:  # noqa: BLE001 - recording how the naive client breaks is the point
        err = f"{type(exc).__name__}: {str(exc)[:80]}"
    ms = (time.perf_counter() - t0) * 1000
    return {"usable": err is None and ms <= USABLE_WITHIN_MS, "ms": round(ms, 1), "error": err}


def m5_faults(c: TestClient, healthy: dict, naive_cap_s: float) -> dict:
    c.post("/api/v1/admin/fault", json={"mode": "none"})
    c.post(REC, json={"occasion": "campus"})  # one good fetch so the fallback has something to serve
    gw, naive = {}, {}
    for mode in FAULTS:
        c.post("/api/v1/admin/fault", json={"mode": mode})
        t0 = time.perf_counter()
        r = c.post(REC, json={"occasion": "campus"})
        ms = (time.perf_counter() - t0) * 1000
        body = r.json() if r.status_code == 200 else {}
        src = body.get("weather", {}).get("source")
        gw[mode] = {"usable": r.status_code == 200 and bool(body.get("outfits")) and src in ("LIVE", "CACHED")
                    and ms <= USABLE_WITHIN_MS, "ms": round(ms, 1), "source": src}
        c.post("/api/v1/admin/fault", json={"mode": "none"})
        naive[mode] = _naive(mode, healthy, naive_cap_s)
    g_ok = sum(v["usable"] for v in gw.values())
    return {
        "name": "Usable answer within 4 s under injected BMKG faults",
        "baseline": {"resilient": sum(v["usable"] for v in naive.values()), "of": len(FAULTS), "per_fault": naive,
                     "client": "naive: no timeout, no status check, no validation, no cache"},
        "integrated": {"resilient": g_ok, "of": len(FAULTS), "per_fault": gw,
                       "client": "WeatherGateway: 3 s deadline, validation, 3 h cache, 6 h fallback"},
        "pass_condition": PASS["M5"],
        "passed": g_ok == len(FAULTS),
    }


# ------------------------------------------------------------- the harness
def warm_db(engine, tries: int = 10, threshold_ms: float = 200.0) -> dict:
    """Neon scales to zero; the first query is slow. Ping until a query is fast, or refuse."""
    first = None
    for _ in range(tries):
        t0 = time.perf_counter()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ms = (time.perf_counter() - t0) * 1000
        first = ms if first is None else first
        if ms < threshold_ms:
            return {"first_ping_ms": round(first, 2), "warm_ping_ms": round(ms, 2)}
    raise ColdDatabaseError(f"database still slow after {tries} pings (last {ms:.0f} ms)")


def run_measurement(*, live: bool = False, seed: int = 2026, runs: int = 30, cold_runs: int | None = None,
                    db_dir: Path | str | None = None, db_url: str | None = None, bmkg_timeout_s: float = 3.0,
                    naive_cap_s: float = 4.5, warmup: bool = True) -> dict:
    if not warmup:
        raise ColdDatabaseError("refusing to measure: DB warm-up skipped (cold Neon would distort M3)")
    cold_runs = cold_runs if cold_runs is not None else (3 if live else runs)
    tmp = None
    if db_url is None:
        if db_dir is None:
            tmp = Path(tempfile.mkdtemp(prefix="dw-measure-"))
            db_dir = tmp
        db_dir = Path(db_dir)
        db_dir.mkdir(parents=True, exist_ok=True)
        for f in db_dir.glob("measure.db*"):
            f.unlink()
        db_url = "sqlite:///" + (db_dir / "measure.db").as_posix()
    now = utcnow()
    feed = None if live else synthetic_feed(seed, now)
    recorder = RecordingClient(HttpBMKGClient() if live else StaticBMKGClient(feed))
    probe = make_engine(db_url)
    try:  # read-only target check BEFORE create_app (init_db) or reset_demo touch anything
        assert_legacy_target(probe, destructive=True)
    finally:
        probe.dispose()
    settings = Settings(database_url=db_url, weather_mode="live" if live else "mock", api_key=API_KEY,
                        bmkg_timeout_s=bmkg_timeout_s, auto_seed=True)
    app = create_app(settings, bmkg_base=recorder)
    try:
        with app.state.Session() as s:
            reset_demo(s)  # fresh, seeded wardrobe → deterministic results
        app.state.fault.set(INITIAL_FAULT_FOR_TESTS)
        with TestClient(app, headers=HEADERS) as c:
            warm = warm_db(app.state.engine)
            health = c.get("/api/v1/health").json()
            if health["fault"] != "none":
                raise MeasurementError(f"fault switch is '{health['fault']}' at start; must be 'none'")
            first = c.get("/api/v1/weather").json()
            if first["source"] != "LIVE" or recorder.last is None:
                raise MeasurementError(f"could not load a forecast to measure against: {first.get('note')}")
            feed = recorder.last
            m4 = m4_validation(feed, now)
            m1, m2 = m1_m2(c, feed)
            m3 = m3_latency(c, runs, cold_runs)
            m5 = m5_faults(c, feed, naive_cap_s)
            bmkg_calls = recorder.calls
    finally:
        app.state.engine.dispose()
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
    metrics = {"M1": m1, "M2": m2, "M3": m3, "M4": m4, "M5": m5}
    return {
        "meta": {
            "generated_by": "measure.py",
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "mode": "live-bmkg" if live else "offline-mock",
            "feed": "real BMKG response" if live else f"synthetic 24-slot feed (seed {seed})",
            "seed": seed, "runs": runs, "cold_runs": cold_runs, "db": backend_name(db_url),
            "db_warmup": warm, "bmkg_timeout_s": bmkg_timeout_s, "bmkg_calls": bmkg_calls if live else 0,
            "python": platform.python_version(), "platform": platform.platform(),
            "wardrobe": "synthetic, 28 garments", "compatibility": "colour/style stand-in, not FashionCLIP",
            "transport": "in-process ASGI (no network between client and server)",
        },
        "metrics": metrics,
        "all_passed": all(m["passed"] for m in metrics.values()),
    }


def deterministic_view(result: dict) -> dict:
    """Everything that must not change between runs with the same seed (no timings, no timestamps)."""
    m = copy.deepcopy(result["metrics"])
    out = {"M1": m["M1"], "M2": m["M2"], "M4": m["M4"]}
    out["M5"] = {side: {k: v["usable"] for k, v in m["M5"][side]["per_fault"].items()} for side in ("baseline", "integrated")}
    return {"metrics": out, "seed": result["meta"]["seed"], "mode": result["meta"]["mode"]}


# ----------------------------------------------------------------- report
def _cell(metric: str, side: str, m: dict) -> str:
    v = m[side]
    if metric == "M1":
        return f"{v['pct_passing']} % ({v['passing']}/{v['total']})"
    if metric == "M2":
        return f"{v['manual_inputs']} inputs" if side == "baseline" else f"max {v['max_manual_inputs']} inputs"
    if metric == "M3":
        if side == "baseline":
            s = v["no_weather_call"]
            return f"p50 {s['p50_ms']} / p95 {s['p95_ms']} ms"
        a, b = v["cached_weather"], v["cold_bmkg"]
        return f"cached p50 {a['p50_ms']} / p95 {a['p95_ms']} ms; cold p50 {b['p50_ms']} / p95 {b['p95_ms']} ms"
    if metric == "M4":
        return "n/a" if side == "baseline" else f"{v['pct_mapped']} % mapped; {v['bad_rejected']}/{v['bad_total']} bad rejected"
    return f"{v['resilient']}/{v['of']} faults answered"


def render_report(out_dir: Path) -> str:
    runs = []
    for f in sorted(out_dir.glob("*.json")):
        try:
            runs.append((f, json.loads(f.read_text(encoding="utf-8"))))
        except (ValueError, OSError):
            continue
    latest: dict[tuple[str, str], tuple[Path, dict]] = {}
    for f, r in runs:  # latest run per (weather mode, database)
        latest[(r["meta"]["mode"], r["meta"]["db"])] = (f, r)
    lines = ["# RESULTS — Digital Wardrobe Live Demo", "",
             "> This file is generated by measure.py from `results/*.json`. Do not edit numbers by hand.", ""]
    if not latest:
        lines.append("No results yet. Run `python measure.py`.")
    if not any(mode == "live-bmkg" for mode, _ in latest):
        lines += ["## live-bmkg", "", "Not run yet (`python measure.py --live`).", ""]
    for key in sorted(latest):
        f, r = latest[key]
        meta = r["meta"]
        lines += [f"## {key[0]} · {key[1]} — {meta['timestamp']}", "",
                  f"Source file: `results/{f.name}` · feed: {meta['feed']} · DB: {meta['db']} "
                  f"(warm-up first ping {meta['db_warmup']['first_ping_ms']} ms) · runs: {meta['runs']} "
                  f"(cold: {meta['cold_runs']}) · BMKG timeout {meta['bmkg_timeout_s']} s · Python {meta['python']}", "",
                  "| ID | Metric | Baseline | Integrated | Pass condition (fixed in TDD) | Result |",
                  "|---|---|---|---|---|---|"]
        for k in ("M1", "M2", "M3", "M4", "M5"):
            m = r["metrics"][k]
            lines.append(f"| {k} | {m['name']} | {_cell(k, 'baseline', m)} | {_cell(k, 'integrated', m)} | "
                         f"{m['pass_condition']} | {'PASS' if m['passed'] else 'FAIL'} |")
        m5 = r["metrics"]["M5"]
        lines += ["", "M5 per fault (ms / outcome):", "",
                  "| Fault | Naive client | Gateway |", "|---|---|---|"]
        for mode_name in FAULTS:
            n, g = m5["baseline"]["per_fault"][mode_name], m5["integrated"]["per_fault"][mode_name]
            lines.append(f"| {mode_name} | {n['ms']} ms, {'usable' if n['usable'] else 'FAILED: ' + str(n['error'])} | "
                         f"{g['ms']} ms, {'usable' if g['usable'] else 'FAILED'} ({g['source']}) |")
        m1 = r["metrics"]["M1"]["contexts"]
        lines += ["", f"M1 contexts: {m1['slots']} forecast slots ({m1['rain_slots']} rainy, {m1['hot_slots']} hot) "
                  f"x {len(m1['occasions'])} occasions ({', '.join(m1['occasions'])}).", ""]
    lines += ["## Limits (report these honestly)", "",
              "- Offline runs use a synthetic feed in the real BMKG format; live runs use whatever BMKG returns that day.",
              "- Latency is measured in-process (ASGI, no network hop between client and server). The DB is warmed first.",
              "- M3 baseline and integrated latencies differ mostly by workload: dry/normal weather admits more outfit "
              "combinations to score than rainy or hot weather does, so the weather-blind baseline is not 'faster' by design.",
              "- The wardrobe is synthetic (28 garments, one synthetic user).",
              "- Compatibility is a colour/style stand-in, not the FashionCLIP model.",
              "- M1 integrated is expected to be ~100 % by construction (the rules use the weather); it checks that "
              "the weather really reaches the rules end to end. The baseline shows what a weather-blind recommender does.",
              ""]
    return "\n".join(lines)


def write_outputs(result: dict, out_dir: Path, report: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = result["meta"]["timestamp"].replace(":", "-").replace("+00-00", "Z")
    path = out_dir / f"{stamp}_{result['meta']['mode']}.json"
    path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render_report(out_dir), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--live", action="store_true", help="use the real BMKG API (a few calls)")
    p.add_argument("--seed", type=int, default=2026)
    p.add_argument("--runs", type=int, default=30)
    p.add_argument("--cold-runs", type=int, default=None, help="default: 3 live (BMKG budget), --runs offline")
    p.add_argument("--bmkg-timeout", type=float, default=3.0)
    p.add_argument("--naive-cap", type=float, default=4.5)
    p.add_argument("--out-dir", type=Path, default=REPO_DIR / "results")
    p.add_argument("--report", type=Path, default=REPO_DIR / "docs" / "RESULTS.md")
    p.add_argument("--db-dir", type=Path, default=None, help="where the temporary SQLite DB goes")
    p.add_argument("--db-url", default=None, help="measure against this DB instead (e.g. Neon). RESETS its demo data")
    p.add_argument("--yes", action="store_true", help="confirm --db-url may be reset")
    a = p.parse_args(argv)
    if a.db_url and not a.yes:
        p.error("--db-url wipes outfits/wear/registrations/logs in that database; add --yes to confirm")
    if a.live:
        print("LIVE mode: calls api.bmkg.go.id (1 + cold-runs times). Weather data: BMKG.", file=sys.stderr)
    result = run_measurement(live=a.live, seed=a.seed, runs=a.runs, cold_runs=a.cold_runs, db_dir=a.db_dir,
                             db_url=a.db_url, bmkg_timeout_s=a.bmkg_timeout, naive_cap_s=a.naive_cap)
    path = write_outputs(result, a.out_dir, a.report)
    for k, m in result["metrics"].items():
        print(f"{k} {'PASS' if m['passed'] else 'FAIL'}  {m['name']}")
    print(f"wrote {path}\nwrote {a.report}")
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
