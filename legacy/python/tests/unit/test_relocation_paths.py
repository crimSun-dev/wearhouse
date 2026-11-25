"""Relocation guards: legacy/python must resolve the repository root, fixtures and outputs correctly."""
from __future__ import annotations

from pathlib import Path

import measure
from app.config import BACKEND_DIR, DEFAULT_FIXTURE, REPO_DIR
from app.db import normalize_url

HERE = Path(__file__).resolve()


def test_backend_dir_is_legacy_python():
    assert BACKEND_DIR == HERE.parents[2]
    assert BACKEND_DIR.parts[-2:] == ("legacy", "python")


def test_repo_dir_is_repository_root():
    assert REPO_DIR == BACKEND_DIR.parents[1]
    assert (REPO_DIR / "legacy" / "python").is_dir()
    assert (REPO_DIR / "README.md").is_file()


def test_fixture_stays_adjacent_to_legacy_python():
    assert DEFAULT_FIXTURE == BACKEND_DIR / "fixtures" / "bmkg_real_sample.json"
    assert DEFAULT_FIXTURE.is_file()


def test_measure_defaults_write_to_root_results_and_docs():
    parser_defaults = {a.dest: a.default for a in _measure_parser()._actions}
    assert parser_defaults["out_dir"] == REPO_DIR / "results"
    assert parser_defaults["report"] == REPO_DIR / "docs" / "RESULTS.md"


def test_relative_sqlite_resolves_inside_legacy_python():
    assert normalize_url("sqlite:///demo.db") == "sqlite:///" + (BACKEND_DIR / "demo.db").as_posix()


def _measure_parser():
    import argparse

    captured = {}
    real = argparse.ArgumentParser.parse_args

    def capture(self, *a, **k):
        captured["parser"] = self
        raise SystemExit(0)

    argparse.ArgumentParser.parse_args = capture
    try:
        try:
            measure.main([])
        except SystemExit:
            pass
    finally:
        argparse.ArgumentParser.parse_args = real
    return captured["parser"]


def test_static_mount_resolves_legacy_web_dist(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    dist = tmp_path / "dist"
    (dist / "app").mkdir(parents=True)
    (dist / "index.html").write_text("<html>landing</html>", encoding="utf-8")
    (dist / "app" / "index.html").write_text("<html>wardrobe</html>", encoding="utf-8")
    monkeypatch.setenv("LEGACY_WEB_DIST", str(dist))
    app = create_app(Settings(database_url="sqlite:///" + (tmp_path / "t.db").as_posix(), weather_mode="mock"))
    with TestClient(app) as c:
        assert "landing" in c.get("/LIVE-DEMO/").text
        assert "wardrobe" in c.get("/LIVE-DEMO/app/").text
        assert c.get("/api/v1/health").status_code == 200


def test_static_mount_falls_back_when_dist_missing(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.config import Settings
    from app.main import create_app

    monkeypatch.setenv("LEGACY_WEB_DIST", str(tmp_path / "absent"))
    app = create_app(Settings(database_url="sqlite:///" + (tmp_path / "t.db").as_posix(), weather_mode="mock"))
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200 and "html" in r.headers["content-type"]
