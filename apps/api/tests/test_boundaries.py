"""3.2 architecture boundaries, checked on real import statements (AST), not on directory names."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "wearhouse"
MODULES = ("identity", "catalogue", "ownership", "accounts", "commerce", "wardrobe", "social", "recommendations", "weather", "platform", "bootstrap",
           "testing")
FRAMEWORKS = ("fastapi", "starlette", "sqlalchemy", "psycopg", "alembic", "httpx", "jwt", "uvicorn")
PURE_LAYERS = ("domain", "ports", "application", "publication", "mapping", "placeholder")


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    pkg = ".".join(path.relative_to(SRC.parent).with_suffix("").parts[:-1])
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg.split(".")[: len(pkg.split(".")) - node.level + 1]
                out.append(".".join(base + ([node.module] if node.module else [])))
            else:
                out.append(node.module or "")
    return out


def _files():
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _layer(p: Path) -> tuple[str, str]:
    rel = p.relative_to(SRC).parts
    return rel[0], p.stem


def test_every_module_parses():
    assert len(_files()) > 20


@pytest.mark.parametrize("path", _files(), ids=lambda p: str(p.relative_to(SRC)))
def test_no_legacy_imports(path):
    for name in _imports(path):
        top = name.split(".")[0]
        assert top not in ("app", "legacy", "measure", "seed"), f"{path.name} imports legacy module {name}"


def _framework_free(p: Path) -> bool:
    # recommendations/weather are pure except their own adapters/ and api.py (wardrobe-planning D1)
    if _layer(p)[0] in ("recommendations", "weather"):
        return "adapters" not in p.relative_to(SRC).parts and p.stem != "api"
    return p.stem in PURE_LAYERS


@pytest.mark.parametrize("path", [p for p in _files() if _framework_free(p)], ids=lambda p: str(p.relative_to(SRC)))
def test_domain_and_application_are_framework_free(path):
    for name in _imports(path):
        assert name.split(".")[0] not in FRAMEWORKS, f"{path.relative_to(SRC)} imports {name}"
        assert ".adapters" not in name and not name.endswith(".api"), f"{path.relative_to(SRC)} imports {name}"


@pytest.mark.parametrize("path", _files(), ids=lambda p: str(p.relative_to(SRC)))
def test_cross_module_access_uses_public_interfaces(path):
    mine = _layer(path)[0]
    if mine in ("bootstrap", "testing"):
        return  # composition root / explicit test factory
    for name in _imports(path):
        parts = name.split(".")
        if parts[0] != "wearhouse" or len(parts) < 2 or parts[1] in (mine, "__init__"):
            continue
        other = parts[1]
        assert other in MODULES, name
        if other == "platform":
            continue
        assert mine != "platform", f"platform must not depend on {name} (no business rules in platform)"
        allowed = {"domain", "ports", "application"} if mine != "catalogue" or other != "identity" else {"domain"}
        if path.stem == "api":
            allowed = allowed | {"api"}  # routers may reuse the identity dependency
        assert len(parts) >= 3 and parts[2] in allowed, f"{path.relative_to(SRC)} reaches into {name}"


def test_platform_tables_do_not_reference_business_modules():
    for p in (SRC / "platform").rglob("*.py"):
        if p.name == "migration_helpers.py":
            continue  # imports bootstrap.schema (privilege contract) for migrations only
        for name in _imports(p):
            assert not name.startswith(("wearhouse.identity", "wearhouse.catalogue", "wearhouse.ownership")), (p, name)


def test_accounts_reaches_other_modules_only_through_ports_domain_application():
    for p in (SRC / "accounts").rglob("*.py"):
        for name in _imports(p):
            parts = name.split(".")
            if parts[0] == "wearhouse" and len(parts) > 2 and parts[1] in ("identity", "ownership", "catalogue"):
                allowed = {"ports", "domain", "application"} | ({"api"} if p.stem == "api" else set())
                assert parts[2] in allowed, f"{p.relative_to(SRC)} imports {name}"
            assert not (parts[0] == "wearhouse" and "adapters" in parts and parts[1] != "accounts"), (p, name)
