"""Backup/restore rehearsal (ecosystem TDD §14 Recovery; complete-wearhouse-tdd 4.1).

pg_dump (custom format) of the source database, then a restore into a NEW database. On the restored copy it runs:
- the release migration (expected to be a no-op at head);
- the API's own startup readiness checks as the runtime role;
- a comparison of row counts for every Wearhouse table.

The restored copy is dropped afterwards unless --keep is passed. The results go to
docs/architecture/release-evidence-backup.md (generated; do not edit by hand).

    source <scratchpad>/dev/env.sh && apps/api/.venv/Scripts/python.exe tools/backup_restore.py \
        --admin-url postgresql://postgres@127.0.0.1:55432/postgres --source wh_smoke \
        --migrator-url postgresql://wh_migrator:...@127.0.0.1:55432/wh_smoke
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
from wearhouse.bootstrap.config import Settings  # noqa: E402
from wearhouse.bootstrap.schema import RUNTIME_PRIVILEGES, SCHEMA_HEAD  # noqa: E402
from wearhouse.bootstrap.startup import verify_database  # noqa: E402

PG_BIN = Path(os.environ.get("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"))


def with_db(url: str, db: str) -> str:
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, "/" + db, p.query, p.fragment))


def sa(url: str) -> str:
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


def counts(url: str) -> dict[str, int]:
    eng = create_engine(sa(url))
    with eng.connect() as c:
        out = {t: c.execute(text(f'SELECT count(*) FROM "{t}"')).scalar_one() for t in sorted(RUNTIME_PRIVILEGES)}
    eng.dispose()
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-url", required=True)
    ap.add_argument("--source", required=True)
    ap.add_argument("--migrator-url", required=True, help="migration role URL for the SOURCE database")
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    target = f"{a.source}_restore_{datetime.now(timezone.utc):%Y%m%d%H%M%S}"
    admin = create_engine(sa(a.admin_url), isolation_level="AUTOCOMMIT")
    src_url = with_db(a.admin_url, a.source)
    dst_url = with_db(a.admin_url, target)
    dump = Path(tempfile.mkdtemp(prefix="wh-backup-")) / f"{a.source}.dump"
    result: dict = {"source": a.source, "restored_as": target, "at": datetime.now(timezone.utc).isoformat()}
    try:
        t = time.perf_counter()
        subprocess.run([str(PG_BIN / "pg_dump.exe"), "-Fc", "-f", str(dump), "-d", src_url], check=True)
        result["dump_seconds"] = round(time.perf_counter() - t, 1)
        result["dump_mb"] = round(dump.stat().st_size / 1e6, 1)
        with admin.connect() as c:
            c.execute(text(f'CREATE DATABASE "{target}"'))
        t = time.perf_counter()
        subprocess.run([str(PG_BIN / "pg_restore.exe"), "-d", dst_url, "--exit-on-error", str(dump)], check=True)
        result["restore_seconds"] = round(time.perf_counter() - t, 1)
        env = {**os.environ, "PYTHONPATH": str(ROOT / "apps" / "api" / "src")}
        migrate = subprocess.run([sys.executable, "-m", "wearhouse.bootstrap.cli", "migrate", "--environment",
                                  os.environ.get("WEARHOUSE_ENV", "development"), "--database-url",
                                  with_db(a.migrator_url, target)], env=env, capture_output=True, text=True)
        result["migrate"] = (migrate.stdout + migrate.stderr).strip().splitlines()[-1] if migrate.returncode == 0 \
            else f"FAILED: {migrate.stderr.strip()[-300:]}"
        runtime = with_db(os.environ["WEARHOUSE_DATABASE_URL"], target)
        settings = replace(Settings.from_env(), database_url=runtime)
        rt = create_engine(sa(runtime))
        checks = verify_database(rt, settings)
        rt.dispose()
        result["readiness"] = checks
        before, after = counts(src_url), counts(dst_url)
        result["tables"] = len(before)
        result["rows_source"] = sum(before.values())
        result["rows_restored"] = sum(after.values())
        result["mismatches"] = {t: [before[t], after.get(t)] for t in before if before[t] != after.get(t)}
        result["schema_head"] = SCHEMA_HEAD
        result["pass"] = (not result["mismatches"] and migrate.returncode == 0
                          and checks.get("schema") == SCHEMA_HEAD and checks.get("privileges") == "ok")
    finally:
        if not a.keep:
            with admin.connect() as c:
                c.execute(text(f'DROP DATABASE IF EXISTS "{target}" WITH (FORCE)'))
            result["restored_copy"] = "dropped after verification"
        dump.unlink(missing_ok=True)
        admin.dispose()
    write(result)
    print(result)
    return 0 if result.get("pass") else 1


def write(r: dict) -> None:
    md = ["# Release evidence: backup and restore (generated by tools/backup_restore.py; do not edit by hand)", "",
          f"Rehearsed {r['at']} on the local development PostgreSQL 18 cluster (not production hosting).", "",
          "| Step | Result |", "|---|---|",
          f"| pg_dump (custom format) of `{r['source']}` | {r.get('dump_mb')} MB in {r.get('dump_seconds')} s |",
          f"| pg_restore into a new database `{r['restored_as']}` | {r.get('restore_seconds')} s |",
          f"| Release migration on the restored copy | {r.get('migrate')} |",
          f"| Startup readiness checks (runtime role) | {r.get('readiness')} |",
          f"| Row counts, {r.get('tables')} Wearhouse tables | source {r.get('rows_source'):,} / restored {r.get('rows_restored'):,}; "
          f"mismatches: {r.get('mismatches') or 'none'} |",
          f"| Restored copy | {r.get('restored_copy', 'kept')} |", "",
          f"**Result: {'PASS' if r.get('pass') else 'FAIL'}.** Recovery point = the dump time; a deployment still needs "
          "its host's scheduled backups and a restore into staging before cutover (TDD §14 RPO 24 h / RTO 4 h)."]
    (ROOT / "docs" / "architecture" / "release-evidence-backup.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
