"""Rehearse v1/v2 environment isolation and the foundation rollback (task 7.6). Non-destructive.

    apps/api/.venv/Scripts/python.exe tools/rehearse_isolation.py --admin-url postgresql://postgres@127.0.0.1:55432/postgres

Uses a DISPOSABLE PostgreSQL server only. It:
  1. creates a migrated v2 database and a claimed item through the real API (signed test identities);
  2. points legacy startup, `seed.py --reset` and `measure.py --db-url --yes` at it -> each must refuse
     before writing; the claimed item and all counts must be unchanged;
  3. creates a legacy demo database with the legacy setup command and points v2 startup and the v2 release
     migration at it -> both must refuse; legacy data unchanged;
  4. rolls back: v2 traffic stops (its app is discarded), v2 data is RETAINED (not deleted or reset), and the
     legacy runtime starts independently and serves /api/v1/health;
  5. verifies the brand/research checksum manifest.
The two disposable rehearsal databases are dropped only after all checks (rehearsal cleanup, not rollback).
Prints a JSON report; exit code 0 only if every check passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "legacy" / "python"
LEGACY_PY = LEGACY / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
sys.path.insert(0, str(ROOT / "apps" / "api" / "tests"))
warnings.filterwarnings("ignore")


def legacy(args: list[str], db_url: str, timeout: int = 120) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": db_url, "WEATHER_MODE": "mock"}
    return subprocess.run([str(LEGACY_PY), *args], cwd=LEGACY, env=env, capture_output=True, text=True, timeout=timeout)


def check_manifest() -> tuple[bool, list[str]]:
    bad = []
    for line in (ROOT / "docs" / "architecture" / "source-asset-checksums.sha256").read_text(encoding="utf-8").splitlines():
        digest, name = line.split(" ", 1)
        path = ROOT / name.lstrip("*")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            bad.append(name)
    return not bad, bad


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--admin-url", required=True, help="superuser URL of a DISPOSABLE PostgreSQL server")
    a = p.parse_args()
    os.environ["WEARHOUSE_TEST_ADMIN_URL"] = a.admin_url
    import conftest as fx  # v2 test fixtures: disposable DB creation, roles, signed identities
    from wearhouse.bootstrap.startup import StartupError
    from wearhouse.testing import LocalIssuer, create_test_app

    report: dict = {"checks": {}}
    ok = report["checks"]
    issuer = LocalIssuer()
    v2 = fx.create_database()
    legacy_db = "dw_rehearse_" + uuid.uuid4().hex[:8]
    tables = ("owned_item", "garment_unit", "activation_credential", "ownership_event", "product", "app_user")
    try:
        # 1. v2 database with a claimed item
        api = fx.Api(create_test_app(fx.make_settings(v2, issuer), issuer=issuer), issuer)
        api.grant("editor", "catalogue_editor")
        api.grant("inventory", "inventory_manager")
        pid = api.post("/api/v2/admin/source-products", "editor", json=fx.synthetic_product()).json()["product_id"]
        unit = fx.issue(api, pid, sub="inventory")
        item = fx.redeem(api, "customer", unit["delivery"]["activation_key"]).json()
        before = fx.counts(v2, *tables)
        ok["v2_claimed_item_created"] = before["owned_item"] == 1

        # 2. legacy utilities against the v2 database (as the superuser: the guard, not privileges, must stop it)
        v2_super = a.admin_url.rsplit("/", 1)[0] + "/" + v2.name
        r_seed = legacy(["seed.py", "--reset"], v2_super)
        r_measure = legacy(["measure.py", "--db-url", v2_super, "--yes", "--runs", "2", "--cold-runs", "1",
                            "--out-dir", str(ROOT / "ci-results" / "rehearsal"), "--report",
                            str(ROOT / "ci-results" / "rehearsal" / "RESULTS.md")], v2_super)
        r_start = legacy(["-c", "from app.main import create_app; create_app()"], v2_super)
        for name, r in (("legacy_seed_reset_refused", r_seed), ("legacy_measure_refused", r_measure),
                        ("legacy_startup_refused", r_start)):
            ok[name] = r.returncode != 0 and "LegacyTargetError" in r.stderr and "Wearhouse v2" in r.stderr
        after = fx.counts(v2, *tables)
        ok["v2_data_unchanged_after_legacy_attempts"] = after == before
        owner_view = api.get(f"/api/v2/me/items/{item['id']}", "customer")
        ok["claimed_item_still_owned"] = owner_view.status_code == 200 and owner_view.json()["id"] == item["id"]

        # 3. v2 against a legacy demo database created by the legacy setup command
        eng = fx.admin_engine()
        with eng.connect() as c:
            c.execute(fx.text(f"CREATE DATABASE {legacy_db}"))
        eng.dispose()
        legacy_url = a.admin_url.rsplit("/", 1)[0] + "/" + legacy_db
        r_setup = legacy(["seed.py", "--register-legacy-environment"], legacy_url)
        ok["legacy_setup_registers_demo_db"] = r_setup.returncode == 0
        legacy_counts = fx.query(fx.V2Database(legacy_db, "", ""), "SELECT count(*) FROM garment")
        try:
            from dataclasses import replace
            create_test_app(replace(fx.make_settings(v2, issuer), database_url=legacy_url), issuer=issuer)
            ok["v2_startup_refuses_legacy_db"] = False
        except StartupError as exc:
            ok["v2_startup_refuses_legacy_db"] = "legacy v1 demo database" in str(exc)
        from alembic import command
        from wearhouse.bootstrap.cli import alembic_config
        try:
            command.upgrade(alembic_config(legacy_url, "test", None), "head")
            ok["v2_migration_refuses_legacy_db"] = False
        except Exception as exc:  # noqa: BLE001
            ok["v2_migration_refuses_legacy_db"] = "legacy v1 demo database" in str(exc)
        ok["legacy_data_unchanged"] = fx.query(fx.V2Database(legacy_db, "", ""),
                                               "SELECT count(*) FROM garment") == legacy_counts
        ok["no_v2_tables_in_legacy_db"] = fx.query(fx.V2Database(legacy_db, "", ""),
                                                   "SELECT count(*) FROM pg_tables WHERE tablename = "
                                                   "'wearhouse_environment'") == [(0,)]

        # 4. rollback: stop v2 traffic, retain v2 data, legacy runs independently
        del api
        ok["v2_data_retained_after_rollback"] = fx.counts(v2, *tables) == before
        port = 8019
        proc = subprocess.Popen([str(LEGACY_PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                 "--port", str(port)], cwd=LEGACY,
                                env={**os.environ, "DATABASE_URL": legacy_url, "WEATHER_MODE": "mock"},
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            health = None
            for _ in range(60):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health", timeout=2) as r:
                        health = json.loads(r.read())
                        break
                except OSError:
                    time.sleep(0.5)
            ok["legacy_runs_independently"] = bool(health) and health.get("status") == "ok"
        finally:
            proc.terminate()
            proc.wait(timeout=20)

        # 5. originals intact
        ok["brand_research_checksums_match"], report["checksum_mismatches"] = check_manifest()
    finally:
        fx.drop_database(v2.name)
        fx.drop_database(legacy_db)
    report["all_passed"] = all(ok.values())
    print(json.dumps(report, indent=2))
    return 0 if report["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
