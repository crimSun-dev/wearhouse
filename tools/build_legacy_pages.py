"""Build the LEGACY v1 GitHub Pages artifact (public frontend files only).

    python tools/build_legacy_pages.py                 # -> _site/  (what pages.yml uploads)
    python tools/build_legacy_pages.py --out <dir>     # build somewhere else (verification)
    python tools/build_legacy_pages.py --verify-only <dir>

Builds legacy/web with VITE_BASE_PATH (default /LIVE-DEMO/) and writes config.js with the public
legacy API base. Never copies backend settings, credentials, databases, datasets or source.
This builds legacy v1 only; v2 has no Pages rollout in the foundation change.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "legacy" / "web"

# Public artifact policy: an allowlist of file types plus explicit denials.
ALLOWED_SUFFIXES = {".html", ".js", ".css", ".webp", ".png", ".jpg", ".jpeg", ".svg", ".ico", ".woff", ".woff2",
                    ".txt", ".map", ""}
ALLOWED_NAMES = {".nojekyll", "config.js"}
DENIED_NAMES = {".env", ".env.example", "package.json", "package-lock.json"}
DENIED_SUFFIXES = {".py", ".pyc", ".db", ".db-wal", ".db-shm", ".sqlite", ".env", ".csv", ".parquet", ".zip",
                   ".docx", ".pdf", ".mjs", ".ts", ".toml", ".pem", ".key"}
DENIED_DIRS = {"node_modules", ".venv", "__pycache__", ".git", "fixtures", "Assets", "Reference", "Research Resources"}


class ArtifactPolicyError(RuntimeError):
    pass


def validate_api_base(api_base: str) -> str:
    api_base = api_base.strip().rstrip("/")
    if api_base:
        url = urlsplit(api_base)
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("API_BASE_URL must be a public HTTPS backend URL without credentials, query, or fragment")
    return api_base


def verify_artifact(target: Path) -> list[str]:
    """Return the artifact's relative file list or raise ArtifactPolicyError on any non-public file."""
    files, problems = [], []
    for p in sorted(target.rglob("*")):
        if p.is_dir():
            if p.name in DENIED_DIRS:
                problems.append(f"forbidden directory {p.relative_to(target)}")
            continue
        rel = p.relative_to(target).as_posix()
        files.append(rel)
        name, suffix = p.name, p.suffix.lower()
        if name in DENIED_NAMES or suffix in DENIED_SUFFIXES or name.startswith(".env"):
            problems.append(f"forbidden file {rel}")
        elif name not in ALLOWED_NAMES and suffix not in ALLOWED_SUFFIXES:
            problems.append(f"unexpected file type {rel}")
    if not (target / "index.html").is_file() or not (target / "app" / "index.html").is_file():
        problems.append("missing index.html or app/index.html (needed for /LIVE-DEMO/ and /LIVE-DEMO/app/)")
    if problems:
        raise ArtifactPolicyError("; ".join(problems))
    return files


def _safe_target(target: Path) -> Path:
    target = target.resolve()
    if target == ROOT or target in ROOT.parents or (target / ".git").exists() or target == FRONTEND:
        raise ValueError(f"refusing to replace {target}: not a dedicated build output directory")
    return target


def build(out: Path | None = None, api_base: str | None = None, base_path: str | None = None) -> Path:
    api_base = validate_api_base(os.environ.get("API_BASE_URL", "") if api_base is None else api_base)
    base_path = base_path or os.environ.get("SITE_BASE_PATH", "/LIVE-DEMO/")
    target = _safe_target(out or ROOT / "_site")
    env = {**os.environ, "VITE_API_BASE": api_base, "VITE_BASE_PATH": base_path}
    subprocess.run(["npm.cmd" if os.name == "nt" else "npm", "run", "build"], cwd=FRONTEND, env=env, check=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(FRONTEND / "dist", target)
    (target / "config.js").write_text("window.DW_API_BASE = " + json.dumps(api_base) + ";\n", encoding="utf-8")
    (target / ".nojekyll").touch()
    verify_artifact(target)
    return target


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--verify-only", type=Path, default=None)
    a = p.parse_args(argv)
    if a.verify_only:
        files = verify_artifact(a.verify_only)
        print(f"artifact OK: {len(files)} public files")
        return 0
    target = build(a.out)
    print(f"built {target} ({len(verify_artifact(target))} public files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
