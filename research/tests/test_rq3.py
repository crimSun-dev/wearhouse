"""RQ3 harness on a small scale (20 real products, 500 guesses). Runs in the API environment:

    WEARHOUSE_TEST_ADMIN_URL=... apps/api/.venv/Scripts/python.exe -m pytest research/tests/test_rq3.py
"""
from __future__ import annotations

import importlib.util
import os

import pytest

pytestmark = pytest.mark.api
if importlib.util.find_spec("wearhouse") is None or not os.environ.get("WEARHOUSE_TEST_ADMIN_URL"):
    pytest.skip("needs the Wearhouse API package and WEARHOUSE_TEST_ADMIN_URL (run with the API venv)",
                allow_module_level=True)

from wearhouse_research.core import load_config, ROOT  # noqa: E402
from wearhouse_research.rq3 import alter, design_checks, run  # noqa: E402


def test_alter_changes_exactly_k_characters():
    import random
    code = "ABCD-EFGH-IJKL-MNOP"
    for k in (1, 2, 3):
        new = alter(code, k, random.Random(k))
        assert sum(a != b for a, b in zip(code.replace("-", ""), new.replace("-", ""))) == k


def test_design_checks_meet_thesis_targets():
    d = design_checks(load_config(ROOT / "research" / "configs" / "rq3.json"))
    assert d["eq10_serial_collision_bound"]["met"] and d["eq11_guessing_bound_one_year"]["met"]


def test_small_rq3_run(tmp_path):
    cfg = load_config(ROOT / "research" / "configs" / "rq3.json")
    cfg.update(products=20, random_guesses=500, reuse_sample=20)
    report = run(cfg, out_dir=tmp_path, log=lambda *_: None)
    assert report["genuine"]["placed_correctly"] == 20
    assert report["false_claims_accepted_total"] == 0
    assert report["generic_error_bodies_distinct"] == 1
    assert report["rate_limit"]["passed"] is True
    assert report["answer"]["rq3_positive"] is True
    assert (tmp_path / os.path.basename(report["_written_to"]) / "report.md").exists()
