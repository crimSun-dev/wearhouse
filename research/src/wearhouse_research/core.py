"""Reproducibility core (stdlib only): dataset manifests gated by sha256, frozen configs, split roles with a
test-data guard, provenance, and report writing (research-reproducibility spec)."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]  # repository root
RESEARCH = ROOT / "research"
REPORTS = RESEARCH / "reports"
DISCLOSURE = ("Code for this pipeline was written with AI assistance (Claude Code, Anthropic) under the author's "
              "direction; the author designed the study, reviewed the code and is responsible for the results. "
              "Disclose this in the thesis as required by the course's GenAI policy.")


class ManifestError(RuntimeError):
    """A dataset manifest is missing, incomplete, or does not match the files on disk."""


class TestDataAccess(RuntimeError):
    """Selection/tuning code asked for test or reporting data (no tuning on test data)."""

    __test__ = False  # not a pytest test class


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


# ------------------------------------------------------------------ manifests
@dataclass(frozen=True)
class DatasetFile:
    key: str
    path: Path
    sha256: str


@dataclass(frozen=True)
class Manifest:
    name: str
    status: str  # permitted | pending
    permission: dict
    files: dict[str, DatasetFile]
    synthetic: bool = False

    def path(self, key: str) -> Path:
        return self.files[key].path


REQUIRED_PERMISSION = ("basis", "accepted_on", "accepted_by", "terms_url", "scope")


def load_manifest(path: Path, *, verify: bool = True) -> Manifest:
    """Read a manifest; refuse unless status is permitted, permission is complete and every sha256 matches."""
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ManifestError(f"manifest not found: {path}") from None
    if raw.get("status") != "permitted":
        raise ManifestError(f"{raw.get('name', path)}: status is {raw.get('status')!r}, not 'permitted' "
                            f"({raw.get('pending_reason', 'dataset not supplied yet')})")
    missing = [k for k in REQUIRED_PERMISSION if not raw.get("permission", {}).get(k)]
    if missing:
        raise ManifestError(f"{raw['name']}: permission record incomplete: {missing}")
    base = Path(path).parent
    files = {}
    for key, spec in raw["files"].items():
        p = Path(spec["path"])
        p = p if p.is_absolute() else (ROOT / p if not (base / p).exists() else base / p)
        files[key] = DatasetFile(key, p, spec["sha256"].lower())
        if verify:
            if not p.exists():
                raise ManifestError(f"{raw['name']}: file {key} missing at {p}")
            actual = sha256_file(p)
            if actual != files[key].sha256:
                raise ManifestError(f"{raw['name']}: file {key} sha256 {actual} != manifest {files[key].sha256}")
    return Manifest(raw["name"], raw["status"], raw["permission"], files, bool(raw.get("synthetic", False)))


# ------------------------------------------------------------------ splits
ROLES = ("train", "validation", "test", "tuning", "reporting")
SELECTABLE = ("train", "validation", "tuning")


@dataclass(frozen=True)
class Split:
    role: str
    data: Any = None
    note: str = ""

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"unknown split role {self.role!r}")


def for_selection(*splits: Split) -> tuple:
    """Unwrap splits for model/setting selection; test and reporting data are refused (no test tuning)."""
    for s in splits:
        if s.role not in SELECTABLE:
            raise TestDataAccess(f"selection received the {s.role!r} split ({s.note})")
    return tuple(s.data for s in splits)


# ------------------------------------------------------------------ provenance and reports
def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def provenance(config: dict, manifests: Iterable[Manifest], seeds: dict, libraries: Iterable[str] = ()) -> dict:
    versions = {}
    for lib in libraries:
        try:
            versions[lib] = __import__(lib).__version__
        except Exception:  # noqa: BLE001 - report absence, never fail the run on it
            versions[lib] = None
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": _git("rev-parse", "HEAD"), "git_dirty": bool(_git("status", "--porcelain")),
            "python": sys.version.split()[0], "platform": platform.platform(), "libraries": versions,
            "config_hash": canonical_hash(config), "seeds": seeds,
            "datasets": {m.name: {"synthetic": m.synthetic, "permission_basis": m.permission.get("basis"),
                                  "files": {k: f.sha256 for k, f in m.files.items()}} for m in manifests},
            "disclosure": DISCLOSURE}


class Stopwatch:
    def __init__(self):
        self.t0 = time.perf_counter()

    def seconds(self) -> float:
        return round(time.perf_counter() - self.t0, 3)


def write_report(rq: str, report: dict, markdown: str, *, out_dir: Path | None = None) -> Path:
    """Write report.json + report.md. Synthetic data can never be written under research/reports/."""
    synthetic = any(d.get("synthetic") for d in report.get("provenance", {}).get("datasets", {}).values())
    target_root = Path(out_dir) if out_dir else REPORTS / rq
    if synthetic and REPORTS in [target_root, *target_root.parents]:
        raise ManifestError("synthetic datasets cannot produce reports under research/reports/")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + report["provenance"]["config_hash"][:8]
    out = target_root / run_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    (out / "report.md").write_text(markdown, encoding="utf-8")
    return out


def load_config(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def env_flag(name: str) -> bool:
    return os.environ.get(name, "").lower() in ("1", "true", "yes")
