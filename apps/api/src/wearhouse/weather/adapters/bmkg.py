"""Real BMKG client (api.bmkg.go.id public forecast). Synchronous httpx with a 3 s budget; every failure becomes a
FetchError with a short safe reason. Tests never use this class (they inject a fake fetcher)."""
from __future__ import annotations

import httpx

from ..ports import FetchError

BMKG_URL = "https://api.bmkg.go.id/publik/prakiraan-cuaca"


class BmkgFetcher:
    def __init__(self, url: str = BMKG_URL, timeout_s: float = 3.0, transport: httpx.BaseTransport | None = None):
        self.url, self.timeout_s, self.transport = url, timeout_s, transport

    def fetch(self, adm4: str) -> dict:
        try:
            with httpx.Client(timeout=self.timeout_s, transport=self.transport,
                              headers={"User-Agent": "wearhouse-weather/2"}) as client:
                resp = client.get(self.url, params={"adm4": adm4})
        except httpx.TimeoutException:
            raise FetchError("timeout") from None
        except httpx.HTTPError:
            raise FetchError("network_error") from None
        if resp.status_code != 200:
            raise FetchError(f"http_{resp.status_code}")
        try:
            data = resp.json()
        except ValueError:
            raise FetchError("bad_json") from None
        if not isinstance(data, dict):
            raise FetchError("bad_json")
        return data
