"""Non-mutating deep-link smoke test for the legacy Pages artifact.

    python tools/smoke_legacy_pages.py [_site]

Serves the artifact exactly as GitHub Pages would, under /LIVE-DEMO/, and checks that
/LIVE-DEMO/ and /LIVE-DEMO/app/ load with every referenced asset. Makes no API calls and
writes nothing, unlike e2e/pages.spec.js, which registers clothing on the live demo backend.
"""
from __future__ import annotations

import re
import shutil
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = "/LIVE-DEMO/"
REF = re.compile(r'(?:src|href)="([^"#]+)"')


class _Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *a):  # keep test output readable
        pass


def _get(url: str) -> tuple[int, str]:
    with urllib.request.urlopen(url, timeout=10) as r:  # noqa: S310 - localhost only
        return r.status, r.read().decode("utf-8", "replace")


def smoke(artifact: Path) -> list[str]:
    checked = []
    with tempfile.TemporaryDirectory() as root:
        shutil.copytree(artifact, Path(root) / BASE.strip("/"))
        server = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Quiet, directory=root))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            for page in (BASE, BASE + "app/"):
                status, html = _get(origin + page)
                assert status == 200 and "<html" in html.lower(), f"{page} did not return HTML"
                checked.append(page)
                for ref in REF.findall(html):
                    if ref.startswith(("http:", "https:", "mailto:", "data:")):
                        continue
                    url = ref if ref.startswith("/") else urllib.parse.urljoin(page, ref)
                    assert url.startswith(BASE), f"{page} references {ref} outside {BASE}"
                    status, _ = _get(origin + url)
                    assert status == 200, f"{url} -> {status}"
                    checked.append(url)
        finally:
            server.shutdown()
    return checked


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "_site")
    urls = smoke(target)
    print(f"Pages smoke OK: {len(urls)} URLs under {BASE}")
    for u in urls:
        print("  " + u)
