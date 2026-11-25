"""Label the 200 H&M transfer pairs for RQ2 (thesis §3.5.2; complete-wearhouse-tdd 4.2). YOU label; nothing is generated.

    research/.venv/Scripts/python.exe research/tools/label_pairs.py sample     # once: 200 seeded, stratified pairs
    research/.venv/Scripts/python.exe research/tools/label_pairs.py serve      # open http://127.0.0.1:8765, label
    research/.venv/Scripts/python.exe research/tools/label_pairs.py finalize   # pin labels in a sha256 manifest

The page shows two H&M articles (name, type, colour, description; no images) and asks "Would these be worn together
in one outfit?": Yes / No / Unsure. Each answer is appended to research/data/hm_transfer_labels.csv (git-ignored,
resumable, the latest answer per pair counts). Localhost only; nothing leaves this machine.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import sys
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "src"))
from wearhouse_research.core import load_manifest  # noqa: E402
from wearhouse_research.rq2.transfer import labelled, read_csv, sample_pairs, write_pairs  # noqa: E402

DATA = ROOT / "research" / "data"
PAIRS, LABELS = DATA / "hm_transfer_pairs.csv", DATA / "hm_transfer_labels.csv"
MANIFEST = ROOT / "research" / "manifests" / "hm_transfer_labels.json"


def cmd_sample() -> int:
    if PAIRS.exists():
        print(f"{PAIRS} already exists; delete it first to resample (labels refer to its pair ids)", file=sys.stderr)
        return 2
    m = load_manifest(ROOT / "research" / "manifests" / "hm_articles.json")
    with m.path("articles").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    pairs = sample_pairs(rows)
    write_pairs(PAIRS, pairs)
    print(f"wrote {len(pairs)} pairs to {PAIRS}")
    return 0


def page(pairs: list[dict], done: dict) -> str:
    todo = [p for p in pairs if p["pair_id"] not in done]
    if not todo:
        return "<h1>All pairs labelled</h1><p>Run <code>label_pairs.py finalize</code>.</p>"
    p = todo[0]
    card = lambda s, t: f"<section><h2>{html.escape(t)}</h2><p>{html.escape(s)}</p></section>"  # noqa: E731
    return (f"<h1>Would these be worn together in one outfit?</h1><p>{len(done)} / {len(pairs)} labelled</p>"
            f"{card(p['a_text'], p['a_type'])}{card(p['b_text'], p['b_type'])}"
            f"<form method=post><input type=hidden name=pair_id value={p['pair_id']}>"
            "<button name=label value=yes>Yes</button> <button name=label value=no>No</button> "
            "<button name=label value=unsure>Unsure</button></form>")


class Handler(BaseHTTPRequestHandler):
    pairs: list[dict] = []

    def _send(self, body: str):
        doc = ("<!doctype html><meta charset=utf-8><title>RQ2 transfer labels</title><style>body{font-family:system-ui;"
               "max-width:46rem;margin:2rem auto}section{border:1px solid #ccc;padding:.5rem 1rem;margin:.5rem 0}"
               "button{font-size:1.2rem;padding:.4rem 1.2rem}</style>" + body)
        data = doc.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _done(self) -> dict:
        return {r["pair_id"]: r["label"] for r in read_csv(LABELS)} if LABELS.exists() else {}

    def do_GET(self):  # noqa: N802
        self._send(page(self.pairs, self._done()))

    def do_POST(self):  # noqa: N802
        form = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode("utf-8"))
        pid, label = form.get("pair_id", [""])[0], form.get("label", [""])[0]
        if label in ("yes", "no", "unsure") and any(p["pair_id"] == pid for p in self.pairs):
            new = not LABELS.exists()
            with LABELS.open("a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if new:
                    w.writerow(["pair_id", "label", "labelled_at"])
                w.writerow([pid, label, datetime.now(timezone.utc).isoformat()])
        self._send(page(self.pairs, self._done()))

    def log_message(self, *args):
        pass


def cmd_serve() -> int:
    if not PAIRS.exists():
        print("run `label_pairs.py sample` first", file=sys.stderr)
        return 2
    Handler.pairs = read_csv(PAIRS)
    print("labelling at http://127.0.0.1:8765 (Ctrl+C to stop; progress is saved after every answer)")
    HTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
    return 0


def cmd_finalize() -> int:
    rows = labelled(PAIRS, LABELS)
    total = len(read_csv(PAIRS))
    if len(rows) < total:
        print(f"only {len(rows)} of {total} pairs labelled; finish labelling first", file=sys.stderr)
        return 2
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()  # noqa: E731
    MANIFEST.write_text(json.dumps({
        "name": "hm_transfer_labels", "status": "permitted",
        "permission": {"basis": "labels authored by the project owner",
                       "accepted_on": datetime.now(timezone.utc).date().isoformat(),
                       "accepted_by": "Wearhouse project owner", "scope": "RQ2 domain-transfer evaluation only",
                       "terms_url": "research/tools/label_pairs.py"},
        "counts": {lab: sum(1 for r in rows if r["label"] == lab) for lab in ("yes", "no", "unsure")},
        "files": {"pairs": {"path": "research/data/hm_transfer_pairs.csv", "sha256": digest(PAIRS)},
                  "labels": {"path": "research/data/hm_transfer_labels.csv", "sha256": digest(LABELS)}}},
        indent=2) + "\n", encoding="utf-8")
    print(f"pinned {len(rows)} labels in {MANIFEST}")
    return 0


if __name__ == "__main__":
    cmds = {"sample": cmd_sample, "serve": cmd_serve, "finalize": cmd_finalize}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(2)
    sys.exit(cmds[sys.argv[1]]())
