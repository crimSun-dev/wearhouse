"""`wearhouse` operator CLI (also `python -m wearhouse.bootstrap.cli`).

    wearhouse migrate --environment ENV [--runtime-role ROLE]   # release command; WEARHOUSE_MIGRATION_DATABASE_URL
    wearhouse check                                             # config + read-only startup checks
    wearhouse grant-role --issuer ISS --subject SUB --role inventory_manager
    wearhouse revoke-role --issuer ISS --subject SUB --role inventory_manager
    wearhouse export-openapi --out packages/contracts/openapi-v2.json   # offline: no DB/network
    wearhouse outbox-dispatch [--loop SECONDS]
    wearhouse purge-deliveries
    wearhouse generate-secret

There is deliberately no HTTP endpoint for role grants (no self-elevation).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path


def migrations_dir() -> Path:
    env = os.environ.get("WEARHOUSE_MIGRATIONS_DIR")
    return Path(env) if env else Path(__file__).resolve().parents[3] / "migrations"


def alembic_config(url: str, environment: str, runtime_role: str | None):
    from alembic.config import Config

    cfg = Config()
    cfg.set_main_option("script_location", str(migrations_dir()))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    cfg.cmd_opts = argparse.Namespace(x=[f"environment={environment}"] +
                                      ([f"runtime_role={runtime_role}"] if runtime_role else []))
    return cfg


def cmd_migrate(a) -> int:
    from alembic import command

    url = a.database_url or os.environ.get("WEARHOUSE_MIGRATION_DATABASE_URL")
    if not url:
        print("WEARHOUSE_MIGRATION_DATABASE_URL (or --database-url) is required; migrations use the migration "
              "role, never the runtime role.", file=sys.stderr)
        return 2
    command.upgrade(alembic_config(url, a.environment, a.runtime_role), a.revision)
    print(f"migrated {a.environment} to {a.revision}")
    return 0


def _runtime():
    from ..platform.db import make_engine
    from .config import Settings
    from .startup import verify_database

    settings = Settings.from_env().validate()
    engine = make_engine(settings.database_url)
    checks = verify_database(engine, settings)
    return settings, engine, checks


def cmd_check(a) -> int:
    from .startup import StartupError
    from .config import ConfigError

    try:
        _, _, checks = _runtime()
    except (ConfigError, StartupError) as exc:
        print(f"NOT READY: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "ready", "checks": checks}, indent=2))
    return 0


def _identity_service():
    from .container import build_services
    from ..identity.ports import InvalidToken

    settings, engine, _ = _runtime()

    class _NoTokens:
        def verify(self, token):
            raise InvalidToken("cli")

    return build_services(settings, engine, _NoTokens()).identity


def cmd_grant(a) -> int:
    svc = _identity_service()
    user_id, changed = svc.grant_role(issuer=a.issuer, subject=a.subject, role=a.role,
                                      granted_by=a.granted_by or f"cli:{os.environ.get('USERNAME') or os.environ.get('USER') or 'operator'}")
    print(f"{'granted' if changed else 'already had'} {a.role} -> user {user_id}")
    return 0


def cmd_revoke(a) -> int:
    svc = _identity_service()
    changed = svc.revoke_role(issuer=a.issuer, subject=a.subject, role=a.role, revoked_by="cli")
    print("revoked" if changed else "no such grant")
    return 0


def offline_settings():
    from .config import Settings

    return Settings(environment="development", oidc_issuer="https://issuer.invalid", oidc_audience="wearhouse-api")


def export_openapi() -> str:
    from .app import build_app

    spec = build_app(offline_settings()).openapi()
    return json.dumps(spec, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def cmd_export(a) -> int:
    text = export_openapi()
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {a.out}")
    else:
        sys.stdout.write(text)
    return 0


def cmd_outbox(a) -> int:
    from ..platform.outbox import OutboxDispatcher, log_consumer

    _, engine, _ = _runtime()
    d = OutboxDispatcher(engine, {"event-log": log_consumer})
    while True:
        print(json.dumps(d.dispatch_once()))
        if not a.loop:
            return 0
        time.sleep(a.loop)


def cmd_purge(a) -> int:
    from .container import build_services
    from ..identity.ports import InvalidToken

    settings, engine, _ = _runtime()

    class _NoTokens:
        def verify(self, token):
            raise InvalidToken("cli")

    n = build_services(settings, engine, _NoTokens()).issuance.purge_expired_deliveries()
    print(f"erased {n} expired deliveries")
    return 0


def cmd_secret(a) -> int:
    from ..platform.crypto import generate_secret

    print(generate_secret())
    return 0


def cmd_import_catalogue(a) -> int:
    """Import a permitted source catalogue CSV (e.g. H&M articles.csv) in job-sized chunks, as an existing staff
    account. Refuses to run when the file does not match its recorded SHA-256. Permission fields are REQUIRED and
    stored on the snapshot: nothing is assumed on the operator's behalf."""
    import hashlib
    from datetime import date as _date

    from ..catalogue.domain import Permission, SnapshotRef, SourceRef
    from ..catalogue.mapping import JobContext
    from ..catalogue.publication import chunk_csv
    from ..identity.ports import InvalidToken
    from .container import build_services

    raw = Path(a.csv).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    sha_file = Path(a.sha256_file or a.csv + ".sha256")
    expected = sha_file.read_text(encoding="utf-8").split()[0].strip().lower() if sha_file.exists() else None
    if expected is None:
        print(f"refusing: no checksum file {sha_file}", file=sys.stderr)
        return 2
    if digest != expected:
        print(f"refusing: {a.csv} sha256 {digest} != recorded {expected}", file=sys.stderr)
        return 2
    settings, engine, _ = _runtime()

    class _NoTokens:
        def verify(self, token):
            raise InvalidToken("cli")

    services = build_services(settings, engine, _NoTokens())
    try:
        principal = services.identity.operator_principal(issuer=a.operator_issuer, subject=a.operator_subject)
    except LookupError as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
    ctx = JobContext(SourceRef(a.namespace, a.source_name, a.source_url),
                     SnapshotRef(digest, Path(a.csv).name, _date.fromisoformat(a.acquired_on)),
                     Permission(a.basis, a.scope, _date.fromisoformat(a.accepted_on), a.accepted_by, a.terms_url))
    chunks = chunk_csv(raw.decode("utf-8"))
    if a.max_jobs:
        chunks = chunks[:a.max_jobs]
    grand = {"created": 0, "revised": 0, "unchanged": 0, "rejected": 0}
    published = 0
    for n, chunk in enumerate(chunks, start=1):
        job = services.publication.run_import(principal, ctx, a.mapping, chunk)
        for k, v in job["totals"].items():
            grand[k] = grand.get(k, 0) + v
        line = f"job {n}/{len(chunks)} {job['id']}: {job['totals']}"
        if a.publish:
            pub = services.publication.publish_job(principal, uuid.UUID(job["id"]))
            published += pub["published"]
            line += f" published={pub['published']}"
        print(line, flush=True)
    print(json.dumps({"sha256": digest, "jobs": len(chunks), "totals": grand, "published": published}))
    return 0 if grand["rejected"] == 0 else 1


def cmd_generate_media(a) -> int:
    """Generated placeholder media objects for every published product without active media (batched,
    idempotent), as an EXISTING account holding catalogue:media."""
    from ..identity.ports import InvalidToken
    from .container import build_services

    settings, engine, _ = _runtime()

    class _NoTokens:
        def verify(self, token):
            raise InvalidToken("cli")

    services = build_services(settings, engine, _NoTokens())
    try:
        principal = services.identity.operator_principal(issuer=a.operator_issuer, subject=a.operator_subject)
    except LookupError as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
    total = 0
    while True:
        out = services.media.generate_missing(principal, limit=a.batch)
        total += out["generated"]
        print(f"generated {out['generated']} (total {total})", flush=True)
        if not out["more_remaining"] or out["generated"] == 0:
            break
    print(json.dumps({"generated": total}))
    return 0


def cmd_assign_sizes(a) -> int:
    """Mock sizes for published products without any (rule: common sizes of the system for the product's slot),
    batched and idempotent, as an EXISTING account holding catalogue:ingest (add-wearhouse-sizes)."""
    from ..identity.ports import InvalidToken
    from .container import build_services

    settings, engine, _ = _runtime()

    class _NoTokens:
        def verify(self, token):
            raise InvalidToken("cli")

    services = build_services(settings, engine, _NoTokens())
    try:
        principal = services.identity.operator_principal(issuer=a.operator_issuer, subject=a.operator_subject)
    except LookupError as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
    total = 0
    while True:
        out = services.sizing.assign_missing(principal, limit=a.batch)
        total += out["assigned"]
        print(f"assigned {out['assigned']} (total {total})", flush=True)
        if not out["more_remaining"] or out["assigned"] == 0:
            break
    print(json.dumps({"assigned": total}))
    return 0


def cmd_import_recommendations(a) -> int:
    """Import a sha-verified recommendation artifact directory (manifest.json + neighbours.csv) and activate it."""
    from ..identity.ports import InvalidToken
    from ..platform.errors import ApiError
    from .container import build_services

    folder = Path(a.artifact)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    settings, engine, _ = _runtime()

    class _NoTokens:
        def verify(self, token):
            raise InvalidToken("cli")

    services = build_services(settings, engine, _NoTokens())
    try:
        principal = services.identity.operator_principal(issuer=a.operator_issuer, subject=a.operator_subject)
        out = services.recommendations.import_similar_items(principal, manifest, (folder / "neighbours.csv").read_bytes())
    except (LookupError, ApiError) as exc:
        print(f"refusing: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(out))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="wearhouse", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("migrate")
    m.add_argument("--environment", required=True, choices=["development", "test", "staging", "production"])
    m.add_argument("--runtime-role", default=None, help="role to GRANT least-privilege runtime access to")
    m.add_argument("--database-url", default=None)
    m.add_argument("--revision", default="head")
    m.set_defaults(fn=cmd_migrate)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    for name, fn in (("grant-role", cmd_grant), ("revoke-role", cmd_revoke)):
        g = sub.add_parser(name)
        g.add_argument("--issuer", required=True)
        g.add_argument("--subject", required=True)
        g.add_argument("--role", required=True, choices=["catalogue_editor", "inventory_manager", "admin"])
        if name == "grant-role":
            g.add_argument("--granted-by", default=None)
        g.set_defaults(fn=fn)
    e = sub.add_parser("export-openapi")
    e.add_argument("--out", default=None)
    e.set_defaults(fn=cmd_export)
    o = sub.add_parser("outbox-dispatch")
    o.add_argument("--loop", type=float, default=None)
    o.set_defaults(fn=cmd_outbox)
    ic = sub.add_parser("import-catalogue", help="import a permitted source catalogue CSV in chunks")
    ic.add_argument("--csv", required=True)
    ic.add_argument("--sha256-file", default=None, help="default: <csv>.sha256 (the import refuses on mismatch)")
    ic.add_argument("--mapping", default="hm-articles@1")
    ic.add_argument("--namespace", required=True)
    ic.add_argument("--source-name", required=True)
    ic.add_argument("--source-url", required=True)
    ic.add_argument("--acquired-on", required=True, help="YYYY-MM-DD")
    ic.add_argument("--basis", required=True)
    ic.add_argument("--scope", required=True)
    ic.add_argument("--accepted-on", required=True, help="YYYY-MM-DD the terms were accepted")
    ic.add_argument("--accepted-by", required=True)
    ic.add_argument("--terms-url", required=True)
    ic.add_argument("--operator-issuer", required=True, help="issuer of an EXISTING catalogue_editor/admin account")
    ic.add_argument("--operator-subject", required=True)
    ic.add_argument("--publish", action="store_true", help="publish each job's products after importing it")
    ic.add_argument("--max-jobs", type=int, default=None)
    ic.set_defaults(fn=cmd_import_catalogue)
    gm = sub.add_parser("generate-media", help="generated placeholder images for products without media")
    gm.add_argument("--operator-issuer", required=True)
    gm.add_argument("--operator-subject", required=True)
    gm.add_argument("--batch", type=int, default=1000)
    gm.set_defaults(fn=cmd_generate_media)
    asz = sub.add_parser("assign-sizes", help="mock sizes (rule) for published products without sizes")
    asz.add_argument("--operator-issuer", required=True)
    asz.add_argument("--operator-subject", required=True)
    asz.add_argument("--batch", type=int, default=5000)
    asz.set_defaults(fn=cmd_assign_sizes)
    ir = sub.add_parser("import-recommendations", help="import + activate a sha-verified recommendation artifact")
    ir.add_argument("--artifact", required=True, help="directory with manifest.json and neighbours.csv")
    ir.add_argument("--operator-issuer", required=True)
    ir.add_argument("--operator-subject", required=True)
    ir.set_defaults(fn=cmd_import_recommendations)
    sub.add_parser("purge-deliveries").set_defaults(fn=cmd_purge)
    sub.add_parser("generate-secret").set_defaults(fn=cmd_secret)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
