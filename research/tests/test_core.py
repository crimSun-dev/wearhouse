"""research-reproducibility: manifest gate, split guard, provenance determinism, synthetic report refusal."""
from __future__ import annotations

import json

import pytest

from wearhouse_research.core import (REPORTS, ManifestError, Split, TestDataAccess, canonical_hash, for_selection,
                                     load_manifest, provenance, sha256_file, write_report)

PERM = {"basis": "synthetic-test", "accepted_on": "2026-11-25", "accepted_by": "tests", "scope": "tests",
        "terms_url": "https://wearhouse.invalid/terms"}


def manifest(tmp_path, content=b"a,b\n1,2\n", status="permitted", sha=None, permission=PERM, synthetic=True):
    data = tmp_path / "data.csv"
    data.write_bytes(content)
    m = tmp_path / "m.json"
    m.write_text(json.dumps({"name": "toy", "status": status, "permission": permission, "synthetic": synthetic,
                             "files": {"data": {"path": str(data), "sha256": sha or sha256_file(data)}}}))
    return m


def test_manifest_passes_when_checksums_match(tmp_path):
    m = load_manifest(manifest(tmp_path))
    assert m.status == "permitted" and m.path("data").name == "data.csv"


def test_manifest_refuses_mismatch_pending_and_incomplete_permission(tmp_path):
    with pytest.raises(ManifestError, match="sha256"):
        load_manifest(manifest(tmp_path, sha="0" * 64))
    with pytest.raises(ManifestError, match="not 'permitted'"):
        load_manifest(manifest(tmp_path, status="pending"))
    with pytest.raises(ManifestError, match="permission record incomplete"):
        load_manifest(manifest(tmp_path, permission={"basis": "x"}))
    with pytest.raises(ManifestError, match="not found"):
        load_manifest(tmp_path / "nope.json")


def test_selection_guard():
    assert for_selection(Split("train", 1), Split("validation", 2)) == (1, 2)
    for role in ("test", "reporting"):
        with pytest.raises(TestDataAccess):
            for_selection(Split("validation", 1), Split(role, 2, note="final week"))
    with pytest.raises(ValueError):
        Split("holdout")


def test_config_hash_is_canonical_and_provenance_records_it(tmp_path):
    assert canonical_hash({"a": 1, "b": [1, 2]}) == canonical_hash({"b": [1, 2], "a": 1})
    p = provenance({"a": 1}, [load_manifest(manifest(tmp_path))], {"bpr": 7}, ["json"])
    assert p["config_hash"] == canonical_hash({"a": 1}) and p["seeds"] == {"bpr": 7}
    assert p["datasets"]["toy"]["synthetic"] is True and "AI assistance" in p["disclosure"]


def test_synthetic_reports_cannot_go_to_reports_dir(tmp_path):
    report = {"provenance": provenance({}, [load_manifest(manifest(tmp_path))], {})}
    with pytest.raises(ManifestError, match="synthetic"):
        write_report("rq0", report, "# x")
    out = write_report("rq0", report, "# x", out_dir=tmp_path / "out")
    assert (out / "report.json").exists() and REPORTS not in out.parents
