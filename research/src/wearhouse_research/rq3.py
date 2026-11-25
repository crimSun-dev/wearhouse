"""RQ3 experiment (methodology v11 section 3.5.3): two-code garment registration, run through the REAL v2 API in a
disposable PostgreSQL database with real permitted H&M catalogue rows.

Runs inside the API environment (needs the `wearhouse` package, its test factory and WEARHOUSE_TEST_ADMIN_URL
pointing at a DISPOSABLE server):

    apps/api/.venv/Scripts/python.exe -m wearhouse_research.rq3 --config research/configs/rq3.json

Phases: genuine activations -> four false-claim families at the validation layer (admission limits disabled so
a limiter cannot mask a validation failure) -> separate rate-limit test with production limits -> design checks.
"""
from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import math
import random
import secrets
import sys
import uuid
from dataclasses import replace
from pathlib import Path

from .core import ROOT, Stopwatch, load_config, load_manifest, provenance, write_report

sys.path.insert(0, str(ROOT / "apps" / "api" / "tests"))  # the API's disposable-DB + signed-identity helpers

B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"


def _rows(articles: Path, n: int, seed: int) -> tuple[str, list[dict]]:
    text = articles.read_bytes().decode("utf-8")
    header, *lines = text.splitlines(keepends=True)
    picked = sorted(random.Random(seed).sample(range(len(lines)), n))
    chosen = [lines[i] for i in picked]
    rows = list(csv.DictReader(io.StringIO(header + "".join(chosen), newline="")))
    return header + "".join(chosen), rows


def random_code(rng: secrets.SystemRandom) -> str:
    raw = base64.b32encode(rng.getrandbits(80).to_bytes(10, "big")).decode()
    return "-".join(raw[i:i + 4] for i in range(0, 16, 4))


def alter(code: str, k: int, rng: random.Random) -> str:
    chars = [c for c in code if c != "-"]
    for pos in rng.sample(range(16), k):
        chars[pos] = rng.choice([c for c in B32 if c != chars[pos]])
    s = "".join(chars)
    return "-".join(s[i:i + 4] for i in range(0, 16, 4))


def _norm(resp) -> str:
    body = resp.json()
    body.pop("request_id", None)
    return json.dumps(body, sort_keys=True)


def design_checks(cfg: dict) -> dict:
    n, s_bits = cfg["garments_for_collision_check"], cfg["serial_bits"]
    collision = n * (n - 1) / 2 / 2 ** s_bits                               # Eq. 10 (birthday bound)
    attempts_per_year = cfg["attempts_per_user_per_hour"] * 24 * 365
    guess = attempts_per_year * cfg["unused_codes"] / 2 ** cfg["key_bits"]  # Eq. 11 (union bound)
    return {"label": "design checks, not research findings (thesis P0430)",
            "eq10_serial_collision_bound": {"n": n, "serial_bits": s_bits, "bound": collision,
                                            "target": "< 1e-20", "met": collision < 1e-20},
            "eq11_guessing_bound_one_year": {"attempts_per_year": attempts_per_year, "unused_codes": cfg["unused_codes"],
                                             "key_bits": cfg["key_bits"], "bound": guess, "target": "< 1e-10",
                                             "met": guess < 1e-10},
            "offline_bruteforce_years_at_1e10_per_s": round(2 ** cfg["key_bits"] / 1e10 / 3.156e7)}


def run(cfg: dict, *, out_dir: Path | None = None, log=print) -> dict:
    import conftest as fx  # noqa: E402  (apps/api/tests)
    from wearhouse.testing import LocalIssuer, create_test_app

    sw = Stopwatch()
    manifest = load_manifest(ROOT / cfg["manifest"])
    csv_text, rows = _rows(manifest.path("articles"), cfg["products"], cfg["seed"])
    expected = {}
    from wearhouse.catalogue.mapping import slot_for
    for r in rows:
        expected[r["article_id"]] = {"category": r["product_type_name"],
                                     "slot": slot_for(r["product_group_name"], r["product_type_name"]) or "unknown"}
    db = fx.create_database()
    try:
        issuer = LocalIssuer.neon()
        base = fx.make_settings(db, issuer)
        open_api = fx.Api(create_test_app(replace(base, redemption_actor_limit=None, redemption_ip_limit=None,
                                                   redemption_global_limit=None), issuer=issuer), issuer)
        open_api.grant("rq3-editor", "catalogue_editor")
        open_api.grant("rq3-inventory", "inventory_manager")
        perm = manifest.permission
        job = open_api.post("/api/v2/admin/catalogue/import-jobs", "rq3-editor", json={
            "source": {"namespace": "hm-pfr", "name": "H&M Personalized Fashion Recommendations",
                       "url": "https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data"},
            "snapshot": {"sha256": manifest.files["articles"].sha256, "file_name": "articles.csv",
                         "acquired_on": perm["accepted_on"]},
            "permission": {"basis": perm["basis"], "scope": perm["scope"], "accepted_on": perm["accepted_on"],
                           "accepted_by": perm["accepted_by"], "terms_url": perm["terms_url"]},
            "csv": csv_text})
        assert job.status_code == 201, job.text
        job = job.json()
        assert job["totals"]["rejected"] == 0, job["totals"]
        assert open_api.post(f"/api/v2/admin/catalogue/import-jobs/{job['id']}/publish", "rq3-editor").status_code == 200
        product_of = {r["external_id"]: r["product_id"] for r in job["rows"]}
        log(f"imported and published {len(product_of)} real H&M products ({sw.seconds()} s)")

        units = []
        for ext, pid in product_of.items():
            u = fx.issue(open_api, pid, sub="rq3-inventory")
            units.append({"external_id": ext, "product_id": pid, "serial": u["public_serial"],
                          "key": u["delivery"]["activation_key"]})
        log(f"issued {len(units)} units ({sw.seconds()} s)")

        # ---- genuine activations: each code once, by its own buyer; correct wardrobe + category + slot
        placed = misplaced = 0
        problems = []
        for i, u in enumerate(units):
            buyer = f"rq3-buyer-{i:04d}"
            r = fx.redeem(open_api, buyer, u["key"])
            items = open_api.get("/api/v2/me/wardrobe/items", buyer).json()["items"]
            exp = expected[u["external_id"]]
            ok = (r.status_code == 201 and len(items) == 1 and items[0]["product_id"] == u["product_id"]
                  and items[0]["category"] == exp["category"] and items[0]["slot"] == exp["slot"])
            if ok:
                placed += 1
            else:
                misplaced += 1
                problems.append({"external_id": u["external_id"], "status": r.status_code})
        log(f"genuine: {placed} placed correctly, {misplaced} problems ({sw.seconds()} s)")

        # ---- false claims at the validation layer (limits disabled), one attacker account
        rng_secure, rng = secrets.SystemRandom(), random.Random(cfg["seed"])
        bodies: set[str] = set()
        families = {}

        def attack(name, codes, sub="rq3-attacker"):
            accepted = statuses = 0
            seen = {}
            for code in codes:
                r = fx.redeem(open_api, sub, code)
                seen[r.status_code] = seen.get(r.status_code, 0) + 1
                if r.status_code < 400:
                    accepted += 1
                else:
                    bodies.add(_norm(r))
                statuses += 1
            families[name] = {"attempts": statuses, "accepted": accepted, "status_counts": seen}
            log(f"{name}: {statuses} attempts, {accepted} accepted ({sw.seconds()} s)")

        genuine = {u["key"].replace("-", "") for u in units}
        guesses = []
        while len(guesses) < cfg["random_guesses"]:
            c = random_code(rng_secure)
            if c.replace("-", "") not in genuine:  # a guess equal to a live code is astronomically unlikely
                guesses.append(c)
        attack("a_random_guesses", guesses)
        attack("b_altered_genuine", [alter(u["key"], k, rng) for u in units for k in cfg["altered_characters"]])
        public = [u["serial"] for u in units] + [f"{cfg['discovery_base_url']}/items/{u['serial']}" for u in units]
        attack("c_public_qr_contents", public)
        attack("d_reused_by_owner", [u["key"] for u in units[: cfg["reuse_sample"]]], sub="rq3-buyer-0000")
        attack("d_reused_by_other", [u["key"] for u in units[: cfg["reuse_sample"]]])
        # the owner-reuse attempts above use buyer-0000 for every key; also replay each key by its own buyer
        own = {"attempts": 0, "accepted": 0}
        for i, u in enumerate(units[: cfg["reuse_sample"]]):
            r = fx.redeem(open_api, f"rq3-buyer-{i:04d}", u["key"])
            own["attempts"] += 1
            own["accepted"] += r.status_code < 400
            if r.status_code >= 400:
                bodies.add(_norm(r))
        families["d_reused_by_own_redeemer"] = own

        # ---- rate limiting, production limits, separate app instance on the same database
        limited = fx.Api(create_test_app(base, issuer=issuer), issuer)
        codes = [random_code(rng_secure) for _ in range(cfg["attempts_per_user_per_hour"] + 1)]
        statuses = [fx.redeem(limited, "rq3-rate-a", c) for c in codes]
        other = fx.redeem(limited, "rq3-rate-b", random_code(rng_secure))
        rate = {"limit_per_user_per_hour": cfg["attempts_per_user_per_hour"],
                "first_n_statuses": sorted({r.status_code for r in statuses[:-1]}),
                "over_limit_status": statuses[-1].status_code,
                "over_limit_retry_after": statuses[-1].headers.get("retry-after"),
                "independent_user_status": other.status_code,
                "passed": (statuses[-1].status_code == 429 and statuses[-1].headers.get("retry-after") is not None
                           and all(r.status_code == 400 for r in statuses[:-1]) and other.status_code == 400)}
        log(f"rate limit: 11th -> {rate['over_limit_status']}, other user -> {rate['independent_user_status']}")
    finally:
        fx.drop_database(db.name)

    false_accepted = sum(f["accepted"] for f in families.values())
    report = {
        "rq": "RQ3", "question": "Can a two-code registration scheme add garments to the correct wardrobe and "
                                 "category while rejecting guessed, altered, copied, and reused codes?",
        "provenance": provenance(cfg, [manifest], {"sample_and_alter": cfg["seed"], "guesses": "SystemRandom (CSPRNG)"}),
        "wall_seconds": sw.seconds(),
        "genuine": {"products": len(units), "placed_correctly": placed, "problems": problems},
        "false_claims": families, "false_claims_accepted_total": false_accepted,
        "generic_error_bodies_distinct": len(bodies), "generic_error_body": sorted(bodies)[0] if bodies else None,
        "rate_limit": rate, "design_checks": design_checks(cfg),
        "deviations": cfg["declared_deviations"],
        "answer": {"all_genuine_placed": placed == len(units), "zero_false_acceptances": false_accepted == 0,
                   "single_generic_rejection": len(bodies) == 1, "rate_limit_enforced": rate["passed"]},
    }
    report["answer"]["rq3_positive"] = all(report["answer"].values())
    out = write_report("rq3", report, markdown(report), out_dir=out_dir)
    report["_written_to"] = str(out)
    return report


def markdown(r: dict) -> str:
    fam = "\n".join(f"| {k} | {v['attempts']:,} | {v['accepted']} |" for k, v in r["false_claims"].items())
    d = r["design_checks"]
    return f"""# RQ3 — Garment registration (methodology section 3.5.3)

**Answer: {"POSITIVE" if r["answer"]["rq3_positive"] else "NOT POSITIVE"}** — {r["answer"]}

Run {r["provenance"]["generated_at"]} · commit {r["provenance"]["git_commit"]} (dirty: {r["provenance"]["git_dirty"]}) · wall {r["wall_seconds"]} s

## Genuine activations
{r["genuine"]["placed_correctly"]} of {r["genuine"]["products"]} real H&M products placed in the correct buyer's wardrobe with the correct category and slot.

## False claims (validation layer, admission limits disabled)
| Family | Attempts | Accepted |
|---|---|---|
{fam}

Total accepted false claims: **{r["false_claims_accepted_total"]}**. Distinct rejection bodies: **{r["generic_error_bodies_distinct"]}** (`{r["generic_error_body"]}`).

## Rate limiting (production limits)
11th attempt within the hour: {r["rate_limit"]["over_limit_status"]} (Retry-After {r["rate_limit"]["over_limit_retry_after"]}); first 10: {r["rate_limit"]["first_n_statuses"]}; independent user: {r["rate_limit"]["independent_user_status"]}.

## Design checks (not findings)
- Eq. 10 serial collision bound, n = {d["eq10_serial_collision_bound"]["n"]:.0e}, {d["eq10_serial_collision_bound"]["serial_bits"]} bits: {d["eq10_serial_collision_bound"]["bound"]:.2e} (target < 1e-20)
- Eq. 11 one-year guessing bound: {d["eq11_guessing_bound_one_year"]["bound"]:.2e} (target < 1e-10)
- Offline brute force of one 80-bit key at 10^10 guesses/s: ~{d["offline_bruteforce_years_at_1e10_per_s"]:,} years

## Declared deviations
{chr(10).join("- " + x for x in r["deviations"])}

## Disclosure
{r["provenance"]["disclosure"]}
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None, help="override report directory (default research/reports/rq3)")
    a = ap.parse_args()
    report = run(load_config(Path(a.config)), out_dir=Path(a.out) if a.out else None)
    print(json.dumps(report["answer"]), report["_written_to"])
    return 0 if report["answer"]["rq3_positive"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
