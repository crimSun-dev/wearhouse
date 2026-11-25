"""Build the LOCAL, git-ignored source-backed fixture (foundation task 7.5) from a permitted H&M articles.csv.

    apps/api/.venv/Scripts/python.exe tools/make_hm_fixture.py --csv "H&M DATABASE/articles.csv" \
        --accepted-on 2026-11-25 --accepted-by "Wearhouse project owner (own Kaggle account)" [--article 0108775015]

Writes apps/api/fixtures/source-products/local/ (ignored by git: the Kaggle rules forbid redistribution):
  hm-articles-subset.csv          the header + the chosen original rows, byte-for-byte
  hm-<article_id>.request.json    the ingestion request built with mapping hm-articles@1 (original fields verbatim)
  manifest.json                   status "permitted", permission record, snapshot + per-row checksums
The tool refuses when the CSV does not match its recorded .sha256. It contains no data itself.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from wearhouse.catalogue.domain import Permission, SnapshotRef, SourceRef, revision_content, validate  # noqa: E402
from wearhouse.catalogue.mapping import JobContext, map_hm_row  # noqa: E402

OUT = ROOT / "apps" / "api" / "fixtures" / "source-products" / "local"
TERMS = "https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/rules"
SOURCE_URL = "https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations/data"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--accepted-on", required=True)
    p.add_argument("--accepted-by", required=True)
    p.add_argument("--acquired-on", default=None, help="default: --accepted-on")
    p.add_argument("--article", action="append", default=None, help="article_id(s); default 0108775015")
    a = p.parse_args()
    src = Path(a.csv)
    raw = src.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    recorded = Path(str(src) + ".sha256").read_text(encoding="utf-8").split()[0].lower()
    if digest != recorded:
        print(f"refusing: sha256 {digest} != recorded {recorded}", file=sys.stderr)
        return 2
    wanted = a.article or ["0108775015"]
    text = raw.decode("utf-8")
    lines = text.splitlines(keepends=True)
    header, chosen = lines[0], [ln for ln in lines[1:] if ln.split(",", 1)[0] in wanted]
    if len(chosen) != len(wanted):
        print("refusing: not every requested article_id exists in the file", file=sys.stderr)
        return 2
    perm = Permission("kaggle-competition-rules-accepted",
                      "private academic test fixture; not redistributed (git-ignored)",
                      date.fromisoformat(a.accepted_on), a.accepted_by, TERMS)
    snap = SnapshotRef(digest, src.name, date.fromisoformat(a.acquired_on or a.accepted_on))
    ctx = JobContext(SourceRef("hm-pfr", "H&M Personalized Fashion Recommendations (H&M Group, distributed via Kaggle)",
                               SOURCE_URL), snap, perm)
    OUT.mkdir(parents=True, exist_ok=True)
    subset = header + "".join(chosen)
    (OUT / "hm-articles-subset.csv").write_bytes(subset.encode("utf-8"))
    records, first_request = [], None
    for row in csv.DictReader(io.StringIO(subset, newline="")):
        inp, errors = map_hm_row(row, ctx)
        errors = errors or validate(inp)
        if errors:
            print(f"refusing: row {row.get('article_id')} invalid: {errors}", file=sys.stderr)
            return 2
        content = revision_content(inp)
        body = {"source": {"namespace": inp.source.namespace, "name": inp.source.name, "url": inp.source.url},
                "snapshot": {"sha256": snap.sha256, "file_name": snap.file_name, "acquired_on": snap.acquired_on.isoformat()},
                "permission": {"basis": perm.basis, "scope": perm.scope, "accepted_on": perm.accepted_on.isoformat(),
                               "accepted_by": perm.accepted_by, "terms_url": perm.terms_url},
                "external_id": inp.external_id, "original_fields": inp.original_fields,
                "facts": content["facts"], "annotations": content["annotations"]}
        name = f"hm-{inp.external_id}.request.json"
        (OUT / name).write_text(json.dumps(body, indent=2, ensure_ascii=False), encoding="utf-8")
        first_request = first_request or name
        line = next(ln for ln in chosen if ln.split(",", 1)[0] == inp.external_id)
        records.append({"external_id": inp.external_id, "row_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest()})
    manifest = {"status": "permitted",
                "permission": {"basis": perm.basis, "accepted_by": perm.accepted_by,
                               "accepted_on": perm.accepted_on.isoformat(), "scope": perm.scope, "terms_url": TERMS},
                "snapshot": {"file": "hm-articles-subset.csv", "sha256": hashlib.sha256(subset.encode()).hexdigest(),
                             "acquired_on": snap.acquired_on.isoformat(), "original_file": src.name,
                             "original_sha256": digest},
                "records": records, "request_file": first_request}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({len(records)} record(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
