from __future__ import annotations

import json
from typing import Protocol
from urllib.request import Request, urlopen


class LightingAdapter(Protocol):
    def set_state(self, state: str) -> None:
        ...


class HttpLightingAdapter:
    """Call a real user-configured HTTP lighting API, never a mock service."""

    def __init__(self, endpoint: str, timeout_seconds: float = 2.0) -> None:
        if not endpoint.lower().startswith(("http://", "https://")):
            raise ValueError("Lighting endpoint must use HTTP or HTTPS")
        if timeout_seconds <= 0:
            raise ValueError("Lighting timeout must be positive")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def set_state(self, state: str) -> None:
        if state not in {"focused", "break", "idle"}:
            raise ValueError("Unsupported lighting state")
        request = Request(
            self.endpoint,
            data=json.dumps({"state": state}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            if response.status >= 400:
                raise RuntimeError(f"Lighting API returned HTTP {response.status}")
