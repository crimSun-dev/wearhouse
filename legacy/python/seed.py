"""Seed the synthetic demo data into DATABASE_URL (Neon or SQLite). Idempotent.

    python seed.py              # create tables, add missing products + 28 garments
    python seed.py --reset      # wipe outfits / wear log / registrations / logs, then re-seed
    python seed.py --issue-codes 3 [--gtin 08999000000110]   # print fresh tag codes (shown once)
    python seed.py --register-legacy-environment   # mark a remote DB as the legacy demo (needed before --reset)
"""
from __future__ import annotations

import argparse

from sqlalchemy.orm import Session

from app.config import Settings
from app.db import assert_legacy_target, backend_name, init_db, make_engine, register_legacy_environment
from app.registration import issue_codes
from app.seed_data import PRODUCTS
from app.seeding import reset_demo, seed


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reset", action="store_true")
    p.add_argument("--register-legacy-environment", action="store_true")
    p.add_argument("--issue-codes", type=int, default=0)
    p.add_argument("--gtin", default=PRODUCTS[0]["gtin"], choices=[x["gtin"] for x in PRODUCTS])
    a = p.parse_args(argv)
    settings = Settings.from_env()
    engine = make_engine(settings.database_url)
    if a.register_legacy_environment or engine.dialect.name == "sqlite":
        register_legacy_environment(engine)  # explicit setup command; local SQLite is always legacy
    assert_legacy_target(engine, destructive=a.reset)
    init_db(engine)
    with Session(engine) as s:
        if a.reset:
            reset_demo(s)
            print("reset done")
        print(f"[{backend_name(settings.database_url)}] seed: {seed(s)}")
        for c in issue_codes(s, a.gtin, a.issue_codes) if a.issue_codes else []:
            print(f"serial {c['serial']}  activation code {c['activation_code']}  (scan: /01/{c['gtin']}/21/{c['serial']})")
    engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
