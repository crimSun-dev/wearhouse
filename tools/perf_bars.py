"""Measure the ecosystem TDD §14 release bars against the local development stack (complete-wearhouse-tdd 4.1).

Starts a separate API instance (port 8101) on the development database with:
- a local token issuer (WEARHOUSE_OIDC_JWKS_FILE: the documented development identity path, refused in deployments);
- raised edge rate limits, so the load test measures latency, not the limiter.

It measures over real HTTP:
- catalogue first page, 20 concurrent clients, mixed filters (budget p95 <= 500 ms);
- personal product recommendations (budget p95 <= 1 s);
- outfit suggestions for an 80-item wardrobe (budget p95 <= 2 s).

Its two measurement users are deleted again through the normal account-deletion API. The results (hardware, data
size, warm state) are written to docs/architecture/release-evidence-perf.md and a JSON file next to it. Do not edit
those numbers by hand.

Run from the repo root with the API venv and the dev environment loaded:
    source <scratchpad>/dev/env.sh && apps/api/.venv/Scripts/python.exe tools/perf_bars.py
"""
from __future__ import annotations

import json
import os
import platform
import random
import secrets
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
from wearhouse.testing import LocalIssuer  # noqa: E402

PORT = 8101
BASE = f"http://127.0.0.1:{PORT}/api/v2"
BUDGETS = {"catalogue_first_page_p95_ms": 500, "personal_recommendations_p95_ms": 1000, "outfit_suggestions_p95_ms": 2000}
CATALOGUE_QUERIES = [{}, {"q": "denim"}, {"category": "Trousers"}, {"size": "alpha:M"}, {"colour": "Black"},
                     {"slot": "top", "sort": "name"}, {"q": "dress", "size": "alpha:S"}]
COLOURS = ["Black", "White", "Beige", "Dark Blue", "Light Pink", "Grey", "Dark Green", "Red"]
WARDROBE = {"top": 20, "bottom": 15, "dress": 8, "footwear": 10, "outer": 12, "bag": 3, "headwear": 2, "scarf": 3,
            "wrist": 4, "earrings": 3}  # 80 items


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, max(0, int(round(q / 100 * len(xs) + 0.5)) - 1))]


def summary(ms: list[float]) -> dict:
    return {"n": len(ms), "p50_ms": round(statistics.median(ms), 1), "p95_ms": round(pct(ms, 95), 1),
            "max_ms": round(max(ms), 1)}


def hardware() -> dict:
    def ps(cmd):
        try:
            return subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True,
                                  timeout=20).stdout.strip()
        except Exception:
            return None
    return {"cpu": ps("(Get-CimInstance Win32_Processor).Name"), "logical_cpus": os.cpu_count(),
            "ram_gb": ps("[math]::Round((Get-CimInstance Win32_OperatingSystem).TotalVisibleMemorySize/1MB,1)"),
            "os": platform.platform(), "python": platform.python_version()}


def main() -> int:
    if os.environ.get("WEARHOUSE_ENV") != "development":
        print("refusing: load the development environment (WEARHOUSE_ENV=development) first", file=sys.stderr)
        return 2
    issuer = LocalIssuer(issuer="https://perf-issuer.wearhouse.local", audience="wearhouse-perf")
    tmp = Path(tempfile.mkdtemp(prefix="wh-perf-"))
    jwks = issuer.write_jwks(tmp / "jwks.json")
    env = {**os.environ, "WEARHOUSE_OIDC_ISSUER": issuer.issuer, "WEARHOUSE_OIDC_AUDIENCE": issuer.audience,
           "WEARHOUSE_OIDC_JWKS_FILE": str(jwks), "WEARHOUSE_OIDC_ALGORITHMS": "RS256",
           "WEARHOUSE_RATE_IP_PER_MIN": "10000000", "WEARHOUSE_RATE_GLOBAL_PER_MIN": "10000000",
           "WEARHOUSE_RATE_WRITES_PER_MIN": "100000", "PYTHONPATH": str(ROOT / "apps" / "api" / "src")}
    env.pop("WEARHOUSE_OIDC_JWKS_URL", None)
    server = subprocess.Popen([sys.executable, "-m", "uvicorn", "wearhouse.bootstrap.asgi:app", "--host", "127.0.0.1",
                               "--port", str(PORT), "--log-level", "warning"], env=env, cwd=ROOT / "apps" / "api")
    try:
        for _ in range(120):
            try:
                if httpx.get(f"{BASE}/health/ready", timeout=2).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            print("API did not become ready", file=sys.stderr)
            return 1
        results = run(issuer)
    finally:
        server.terminate()
        server.wait(timeout=30)
    write(results)
    print(json.dumps({k: v for k, v in results.items() if k.endswith("pass") or k == "verdicts"}, indent=1))
    return 0


def run(issuer: LocalIssuer) -> dict:
    rng = random.Random(20261126)
    auth = lambda sub: {"Authorization": "Bearer " + issuer.token(sub)}  # noqa: E731
    # -- catalogue: warm, then 20 concurrent clients x 25 first-page requests
    with httpx.Client(timeout=30) as c:
        for q in CATALOGUE_QUERIES * 2:
            c.get(f"{BASE}/catalogue/products", params={**q, "limit": 24}).raise_for_status()
    lat: list[float] = []
    errors: list[str] = []
    lock = threading.Lock()

    def worker(seed):
        r = random.Random(seed)
        with httpx.Client(timeout=30) as c:
            for _ in range(25):
                q = r.choice(CATALOGUE_QUERIES)
                t = time.perf_counter()
                resp = c.get(f"{BASE}/catalogue/products", params={**q, "limit": 24})
                ms = (time.perf_counter() - t) * 1000
                with lock:
                    (lat.append(ms) if resp.status_code == 200 else errors.append(str(resp.status_code)))

    t0 = time.perf_counter()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    wall = time.perf_counter() - t0
    catalogue = {**summary(lat), "concurrency": 20, "errors": len(errors), "throughput_rps": round(len(lat) / wall, 1)}

    tag = secrets.token_hex(3)
    shopper, ward = f"perf-shopper-{tag}", f"perf-wardrobe-{tag}"
    with httpx.Client(timeout=60) as c:
        # -- personal recommendations
        for sub, handle in ((shopper, f"perfshop_{tag}"), (ward, f"perfward_{tag}")):
            c.patch(f"{BASE}/me/profile", headers=auth(sub), json={"handle": handle}).raise_for_status()
        for _ in range(3):
            c.get(f"{BASE}/me/recommendations/products", headers=auth(shopper), params={"limit": 12}).raise_for_status()
        rec = []
        for _ in range(30):
            t = time.perf_counter()
            c.get(f"{BASE}/me/recommendations/products", headers=auth(shopper), params={"limit": 12}).raise_for_status()
            rec.append((time.perf_counter() - t) * 1000)
        # -- outfit suggestions at 80 items
        n = 0
        for slot, count in WARDROBE.items():
            for i in range(count):
                c.post(f"{BASE}/me/wardrobe/items", headers=auth(ward),
                       json={"name": f"Perf {slot} {i}", "slot": slot, "colour": rng.choice(COLOURS)}).raise_for_status()
                n += 1
        for _ in range(3):
            c.get(f"{BASE}/me/recommendations/outfits", headers=auth(ward), params={"limit": 5}).raise_for_status()
        out = []
        for i in range(30):
            occasion = ("casual", "campus", "worship", "wedding")[i % 4]
            t = time.perf_counter()
            r = c.get(f"{BASE}/me/recommendations/outfits", headers=auth(ward),
                      params={"limit": 5, "occasion": occasion, "rain": "false", "hot": "true"})
            r.raise_for_status()
            out.append((time.perf_counter() - t) * 1000)
        considered = r.json()["candidates_considered"]
        # -- clean up: the normal account deletion (recent sign-in, typed handle)
        for sub, handle in ((shopper, f"perfshop_{tag}"), (ward, f"perfward_{tag}")):
            c.request("DELETE", f"{BASE}/me", headers=auth(sub), json={"confirm": handle}).raise_for_status()

    eng = create_engine(os.environ["WEARHOUSE_DATABASE_URL"].replace("postgresql://", "postgresql+psycopg://", 1))
    with eng.connect() as conn:
        published = conn.execute(text("SELECT count(*) FROM product WHERE publication_state = 'published'")).scalar_one()
        sized = conn.execute(text("SELECT count(*) FROM product WHERE cardinality(browse_sizes) > 0")).scalar_one()
    eng.dispose()
    res = {"measured_at": datetime.now(timezone.utc).isoformat(), "hardware": hardware(),
           "dataset": {"published_products": published, "products_with_sizes": sized, "wardrobe_items": n,
                       "outfit_candidates_considered": considered},
           "state": "warm (warm-up requests first); API and PostgreSQL on the same machine; HTTP over loopback",
           "catalogue_first_page": catalogue, "personal_recommendations": summary(rec), "outfit_suggestions": summary(out)}
    res["verdicts"] = {
        "catalogue_first_page_p95_ms": catalogue["p95_ms"] <= BUDGETS["catalogue_first_page_p95_ms"] and not errors,
        "personal_recommendations_p95_ms": res["personal_recommendations"]["p95_ms"] <= BUDGETS["personal_recommendations_p95_ms"],
        "outfit_suggestions_p95_ms": res["outfit_suggestions"]["p95_ms"] <= BUDGETS["outfit_suggestions_p95_ms"]}
    return res


def write(r: dict) -> None:
    out = ROOT / "docs" / "architecture"
    stamp = r["measured_at"][:19].replace(":", "-")
    (out / "evidence").mkdir(exist_ok=True)
    (out / "evidence" / f"perf-{stamp}.json").write_text(json.dumps(r, indent=2), encoding="utf-8")
    v = r["verdicts"]
    rows = [("Catalogue first page, 20 concurrent clients", r["catalogue_first_page"], "catalogue_first_page_p95_ms"),
            ("Personal product recommendations", r["personal_recommendations"], "personal_recommendations_p95_ms"),
            (f"Outfit suggestions, {r['dataset']['wardrobe_items']} items", r["outfit_suggestions"], "outfit_suggestions_p95_ms")]
    h = r["hardware"]
    md = [
        "# Release evidence: performance (generated by tools/perf_bars.py; do not edit numbers by hand)", "",
        f"Measured {r['measured_at']} on {h['cpu']} ({h['logical_cpus']} logical CPUs, {h['ram_gb']} GB RAM), {h['os']}, "
        f"Python {h['python']}. {r['state']}. Dataset: {r['dataset']['published_products']:,} published products "
        f"({r['dataset']['products_with_sizes']:,} sized). This is a laptop development stack, not production hosting.", "",
        "| Bar (TDD §14) | n | p50 | p95 | max | Budget p95 | Result |", "|---|---|---|---|---|---|---|"]
    for name, s, key in rows:
        md.append(f"| {name} | {s['n']} | {s['p50_ms']} ms | {s['p95_ms']} ms | {s['max_ms']} ms | {BUDGETS[key]} ms | "
                  f"{'PASS' if v[key] else 'FAIL'} |")
    md += ["", f"Catalogue throughput {r['catalogue_first_page']['throughput_rps']} requests/s, "
           f"{r['catalogue_first_page']['errors']} errors. Outfit suggestions considered "
           f"{r['dataset']['outfit_candidates_considered']} candidate combinations per request (top-8 per slot).",
           f"Raw results: `docs/architecture/evidence/perf-{stamp}.json`."]
    (out / "release-evidence-perf.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
