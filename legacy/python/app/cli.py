"""Offline CLI over the pure core (no DB, no HTTP).

    python -m app.cli recommend --rain --occasion campus
"""
from __future__ import annotations

import argparse
from datetime import date

from .domain import OCCASIONS
from .rules import Context
from .scoring import recommend
from .seed_data import seed_wardrobe


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    rec = sub.add_parser("recommend", help="recommend outfits from the synthetic seed wardrobe")
    rec.add_argument("--rain", action="store_true")
    rec.add_argument("--hot", action="store_true")
    rec.add_argument("--occasion", choices=OCCASIONS, default="campus")
    rec.add_argument("-k", type=int, default=5)
    args = parser.parse_args(argv)

    ctx = Context(rain=args.rain, hot=args.hot, occasion=args.occasion)
    recs = recommend(seed_wardrobe(), ctx, date.today(), k=args.k)
    print(f"Context: rain={ctx.rain} hot={ctx.hot} occasion={ctx.occasion}")
    if not recs:
        print("No allowed outfit. Add rain footwear/outer or items for this occasion.")
        return 1
    for i, r in enumerate(recs, 1):
        names = ", ".join(f"{g.slot}: {g.name}" for g in r.outfit.items)
        print(f"{i}. score={r.score:.3f} (compat={r.compat:.2f} pref={r.pref:.2f} recency={r.recency:.2f})  {names}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
