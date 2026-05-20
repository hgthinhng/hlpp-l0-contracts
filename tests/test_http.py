import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hlpp_l0_contracts.http import HttpClient


def test_get_retries_429_then_returns_success():
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": "rate limited"},
                request=request,
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    client = HttpClient(transport=httpx.MockTransport(handler))

    response = client.get("https://example.test/data")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert attempts == 2
