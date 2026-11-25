"""Runtime settings, read from environment / legacy/python/.env (never committed).

Legacy v1 demo runtime. Relocated from `backend/` to `legacy/python/` by the
rearchitect-wearhouse-foundation change; v2 lives in `apps/api` and never imports this package.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .seed_data import DEFAULT_ADM4

BACKEND_DIR = Path(__file__).resolve().parents[1]  # legacy/python
REPO_DIR = BACKEND_DIR.parents[1]  # repository root (legacy/python -> legacy -> root)
OLD_BACKEND_ENV = REPO_DIR / "backend" / ".env"  # pre-relocation location, read only as a fallback
DEFAULT_FIXTURE = BACKEND_DIR / "fixtures" / "bmkg_real_sample.json"


def _bool(v: str | None, default: bool) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    database_url: str = "sqlite:///demo.db"
    weather_mode: str = "mock"  # mock | live
    api_key: str = "demo-key"
    default_adm4: str = DEFAULT_ADM4
    bmkg_timeout_s: float = 3.0
    cache_ttl_s: int = 10800  # 3 h
    cache_stale_max_s: int = 21600  # 6 h
    fixture_path: Path = field(default_factory=lambda: DEFAULT_FIXTURE)
    auto_seed: bool = True
    cors_origins: tuple[str, ...] = ()

    def __post_init__(self):
        if self.weather_mode not in ("mock", "live"):
            raise ValueError("WEATHER_MODE must be 'mock' or 'live'")

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            from dotenv import load_dotenv

            if (BACKEND_DIR / ".env").is_file():
                load_dotenv(BACKEND_DIR / ".env")
            elif OLD_BACKEND_ENV.is_file():
                import warnings

                warnings.warn(f"reading legacy settings from {OLD_BACKEND_ENV}; move it to {BACKEND_DIR / '.env'}",
                              stacklevel=2)
                load_dotenv(OLD_BACKEND_ENV)
        except ImportError:  # pragma: no cover
            pass
        e = os.environ.get
        return cls(
            database_url=e("DATABASE_URL") or "sqlite:///demo.db",
            weather_mode=(e("WEATHER_MODE") or "mock").lower(),
            api_key=e("DEMO_API_KEY") or "demo-key",
            default_adm4=e("DEFAULT_ADM4") or DEFAULT_ADM4,
            bmkg_timeout_s=float(e("BMKG_TIMEOUT_S") or 3.0),
            auto_seed=_bool(e("AUTO_SEED"), True),
            cors_origins=tuple(o.strip() for o in (e("CORS_ORIGINS") or "").split(",") if o.strip()),
        )
