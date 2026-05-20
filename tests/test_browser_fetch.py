"""Tests for BrowserFetchClient in hlpp_l0_contracts.browser_fetch.

Uses unittest.mock to patch httpx.Client — respx is not available in this env.
All tests are synchronous and isolated (no real network calls).
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest

from hlpp_l0_contracts.browser_fetch import (
    DEFAULT_TIMEOUT_S,
    BrowserFetchAuthError,
    BrowserFetchBadRequest,
    BrowserFetchClient,
    BrowserFetchError,
    BrowserFetchPoolTimeout,
    BrowserFetchServerError,
    BrowserFetchTimeoutError,
    BrowserFetchUnavailable,
    BrowserFetchUpstreamFailed,
    Cookie,
    HealthResult,
    RenderResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(
    status_code: int,
    body: dict[str, Any],
) -> MagicMock:
    """Build a mock httpx.Response with the given status and JSON body."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.is_success = 200 <= status_code < 300
    resp.json.return_value = body
    return resp


def _success_render_body(
    *,
    rendered_html: str | None = "<html>Hello</html>",
    extracted_json: list[dict[str, Any]] | None = None,
    upstream_http_code: int = 200,
    fetch_ms: int = 1234,
    cache_key: str = "abc123",
) -> dict[str, Any]:
    return {
        "status": "ok",
        "rendered_html": rendered_html,
        "extracted_json": extracted_json,
        "http_code": upstream_http_code,
        "fetch_ms": fetch_ms,
        "cache_key": cache_key,
    }


def _error_body(
    error_code: str = "INTERNAL",
    error_message: str = "something broke",
    http_code: int | None = None,
    fetch_ms: int = 0,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "status": "error",
        "error_code": error_code,
        "error_message": error_message,
        "fetch_ms": fetch_ms,
    }
    if http_code is not None:
        body["http_code"] = http_code
    return body


# ---------------------------------------------------------------------------
# Constructor / configuration tests
# ---------------------------------------------------------------------------


def test_constructor_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """No args + no env → default base_url and no auth header."""
    monkeypatch.delenv("HT_BROWSER_FETCH_URL", raising=False)
    monkeypatch.delenv("HT_BROWSER_FETCH_TOKEN", raising=False)

    with patch("hlpp_l0_contracts.browser_fetch.httpx.Client") as mock_cls:
        BrowserFetchClient()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["base_url"] == "http://localhost:18766"
        headers = call_kwargs["headers"]
        assert "Authorization" not in headers


def test_constructor_env_url_used(monkeypatch: pytest.MonkeyPatch) -> None:
    """HT_BROWSER_FETCH_URL env is respected when no explicit base_url."""
    monkeypatch.setenv("HT_BROWSER_FETCH_URL", "http://prod-vps:18766")
    monkeypatch.delenv("HT_BROWSER_FETCH_TOKEN", raising=False)

    with patch("hlpp_l0_contracts.browser_fetch.httpx.Client") as mock_cls:
        BrowserFetchClient()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["base_url"] == "http://prod-vps:18766"


def test_constructor_explicit_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Explicit args always win over env vars."""
    monkeypatch.setenv("HT_BROWSER_FETCH_URL", "http://from-env:18766")
    monkeypatch.setenv("HT_BROWSER_FETCH_TOKEN", "env-token")

    with patch("hlpp_l0_contracts.browser_fetch.httpx.Client") as mock_cls:
        BrowserFetchClient(
            base_url="http://explicit:9000",
            bearer_token="explicit-token",
        )
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["base_url"] == "http://explicit:9000"
        assert call_kwargs["headers"]["Authorization"] == "Bearer explicit-token"


def test_constructor_env_token_sets_auth_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """HT_BROWSER_FETCH_TOKEN env sets Authorization header."""
    monkeypatch.delenv("HT_BROWSER_FETCH_URL", raising=False)
    monkeypatch.setenv("HT_BROWSER_FETCH_TOKEN", "secret-from-env")

    with patch("hlpp_l0_contracts.browser_fetch.httpx.Client") as mock_cls:
        BrowserFetchClient()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer secret-from-env"


def test_constructor_timeout_passed_to_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    """Custom timeout is forwarded to httpx.Client."""
    monkeypatch.delenv("HT_BROWSER_FETCH_URL", raising=False)
    monkeypatch.delenv("HT_BROWSER_FETCH_TOKEN", raising=False)

    with patch("hlpp_l0_contracts.browser_fetch.httpx.Client") as mock_cls:
        BrowserFetchClient(timeout=60.0)
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["timeout"] == 60.0


# ---------------------------------------------------------------------------
# render() — success paths
# ---------------------------------------------------------------------------


def test_render_success_html() -> None:
    """200 response with html mode: RenderResult populated, extracted_json is None."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        200,
        _success_render_body(rendered_html="<html>OK</html>", extracted_json=None),
    )
    client._client = mock_http

    result = client.render("https://example.com", return_mode="html")

    assert isinstance(result, RenderResult)
    assert result.rendered_html == "<html>OK</html>"
    assert result.extracted_json is None
    assert result.upstream_http_code == 200
    assert result.fetch_ms == 1234
    assert result.cache_key == "abc123"


def test_render_success_both_populates_all_fields() -> None:
    """return_mode='both' populates rendered_html and extracted_json."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        200,
        _success_render_body(
            rendered_html="<html>data</html>",
            extracted_json=[{"key": "value"}],
        ),
    )
    client._client = mock_http

    result = client.render("https://example.com", return_mode="both")

    assert result.rendered_html == "<html>data</html>"
    assert result.extracted_json == [{"key": "value"}]


def test_render_return_mode_alias() -> None:
    """return_mode='html' serializes to 'return': 'html' in the JSON body sent to service."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(200, _success_render_body())
    client._client = mock_http

    client.render("https://example.com", return_mode="html")

    _, call_kwargs = mock_http.post.call_args
    sent_body = call_kwargs["json"]
    assert "return" in sent_body, "Service 'return' field must be in request body"
    assert sent_body["return"] == "html"
    assert "return_mode" not in sent_body, "Python alias must not leak into wire format"


# ---------------------------------------------------------------------------
# render() — error paths
# ---------------------------------------------------------------------------


def test_render_400_raises_bad_request() -> None:
    """400 response raises BrowserFetchBadRequest with error_code."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        400, _error_body("BAD_URL", "url must be absolute http(s)")
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchBadRequest) as exc_info:
        client.render("not-a-url")

    exc = exc_info.value
    assert exc.http_code == 400
    assert exc.error_code == "BAD_URL"
    assert "BAD_URL" in str(exc)
    assert isinstance(exc, BrowserFetchError)


def test_render_500_raises_server_error() -> None:
    """500 response raises BrowserFetchServerError."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        500, _error_body("INTERNAL", "Playwright crash")
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchServerError) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.http_code == 500
    assert isinstance(exc_info.value, BrowserFetchError)


def test_render_504_raises_server_error() -> None:
    """504 RENDER_TIMEOUT raises BrowserFetchServerError."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        504, _error_body("RENDER_TIMEOUT", "render exceeded MAX_RENDER_MS")
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchServerError) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.http_code == 504


def test_render_auth_error_401() -> None:
    """401 raises BrowserFetchAuthError."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        401, _error_body("UNAUTHORIZED", "missing bearer token")
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchAuthError) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.http_code == 401
    assert isinstance(exc_info.value, BrowserFetchError)


def test_render_auth_error_403() -> None:
    """403 also raises BrowserFetchAuthError."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        403, _error_body("UNAUTHORIZED", "wrong token")
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchAuthError) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.http_code == 403


def test_render_502_upstream_failed_includes_upstream_http_code() -> None:
    """502 raises BrowserFetchUpstreamFailed with upstream_http_code from body."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        502,
        _error_body("UPSTREAM_FAILED", "upstream returned 404", http_code=404),
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchUpstreamFailed) as exc_info:
        client.render("https://example.com/missing")

    exc = exc_info.value
    assert exc.http_code == 502
    assert exc.upstream_http_code == 404
    assert isinstance(exc, BrowserFetchError)


def test_render_timeout_raises_browser_fetch_timeout_error() -> None:
    """httpx.TimeoutException raises BrowserFetchTimeoutError."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.side_effect = httpx.TimeoutException("timed out")
    client._client = mock_http

    with pytest.raises(BrowserFetchTimeoutError) as exc_info:
        client.render("https://example.com")

    assert isinstance(exc_info.value, BrowserFetchError)


def test_render_connection_refused_raises_unavailable() -> None:
    """httpx.ConnectError raises BrowserFetchUnavailable."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.side_effect = httpx.ConnectError("connection refused")
    client._client = mock_http

    with pytest.raises(BrowserFetchUnavailable) as exc_info:
        client.render("https://example.com")

    assert isinstance(exc_info.value, BrowserFetchError)


# ---------------------------------------------------------------------------
# 429 retry logic
# ---------------------------------------------------------------------------


def test_429_retries_then_succeeds() -> None:
    """429 twice then 200: 3 total calls, final result is RenderResult."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    pool_resp = _make_response(429, _error_body("POOL_EXHAUSTED_QUEUE_TIMEOUT", "pool full"))
    success_resp = _make_response(200, _success_render_body())
    mock_http.post.side_effect = [pool_resp, pool_resp, success_resp]
    client._client = mock_http

    with patch("hlpp_l0_contracts.browser_fetch.time.sleep") as mock_sleep:
        result = client.render("https://example.com")

    assert mock_http.post.call_count == 3
    assert mock_sleep.call_count == 2
    assert isinstance(result, RenderResult)


def test_429_retries_exhausted_raises_pool_timeout() -> None:
    """429 on all 3 attempts raises BrowserFetchPoolTimeout."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    pool_resp = _make_response(429, _error_body("POOL_EXHAUSTED_QUEUE_TIMEOUT", "pool full"))
    mock_http.post.return_value = pool_resp
    client._client = mock_http

    with patch("hlpp_l0_contracts.browser_fetch.time.sleep"):
        with pytest.raises(BrowserFetchPoolTimeout) as exc_info:
            client.render("https://example.com")

    assert mock_http.post.call_count == 3
    assert exc_info.value.http_code == 429
    assert isinstance(exc_info.value, BrowserFetchError)


def test_429_backoff_timing() -> None:
    """Backoff sleeps use exponential schedule: 1s, 2s (base 1s, cap 8s)."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    pool_resp = _make_response(429, _error_body("POOL_EXHAUSTED_QUEUE_TIMEOUT", "full"))
    mock_http.post.return_value = pool_resp
    client._client = mock_http

    with patch("hlpp_l0_contracts.browser_fetch.time.sleep") as mock_sleep:
        with pytest.raises(BrowserFetchPoolTimeout):
            client.render("https://example.com")

    sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
    assert sleep_calls == [1.0, 2.0], f"Expected [1.0, 2.0], got {sleep_calls}"


# ---------------------------------------------------------------------------
# render() — cookies
# ---------------------------------------------------------------------------


def test_render_passes_cookies_in_body() -> None:
    """Cookies are serialized into the request body's cookies array."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(200, _success_render_body())
    client._client = mock_http

    cookies = [
        Cookie(name="session_id", value="abc123", domain="data.hnx.vn", path="/"),
        Cookie(name="csrf", value="xyz"),
    ]
    client.render("https://data.hnx.vn/", cookies=cookies)

    _, call_kwargs = mock_http.post.call_args
    body = call_kwargs["json"]
    assert "cookies" in body
    assert body["cookies"] == [
        {"name": "session_id", "value": "abc123", "domain": "data.hnx.vn", "path": "/"},
        {"name": "csrf", "value": "xyz", "domain": None, "path": None},
    ]


def test_render_no_cookies_key_omitted_when_none() -> None:
    """When cookies=None (default), 'cookies' key is NOT sent in the body."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(200, _success_render_body())
    client._client = mock_http

    client.render("https://example.com")

    _, call_kwargs = mock_http.post.call_args
    body = call_kwargs["json"]
    assert "cookies" not in body


# ---------------------------------------------------------------------------
# health()
# ---------------------------------------------------------------------------


def test_health_success() -> None:
    """GET /health returns parsed HealthResult."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    health_body = {
        "status": "ok",
        "service": "ht-browser-fetch",
        "version": "0.1.0",
        "browser_pool_size": 2,
        "browser_pool_available": 1,
        "uptime_s": 9999,
    }
    mock_resp = _make_response(200, health_body)
    mock_http.get.return_value = mock_resp
    client._client = mock_http

    result = client.health()

    assert isinstance(result, HealthResult)
    assert result.status == "ok"
    assert result.service == "ht-browser-fetch"
    assert result.version == "0.1.0"
    assert result.browser_pool_size == 2
    assert result.browser_pool_available == 1
    assert result.uptime_s == 9999


def test_health_503_raises_unavailable() -> None:
    """GET /health returning 503 raises BrowserFetchUnavailable."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_resp = _make_response(503, {"status": "unhealthy", "error_message": "pool failed"})
    mock_http.get.return_value = mock_resp
    client._client = mock_http

    with pytest.raises(BrowserFetchUnavailable):
        client.health()


def test_health_timeout_raises_timeout_error() -> None:
    """httpx.TimeoutException on /health raises BrowserFetchTimeoutError."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.TimeoutException("timeout")
    client._client = mock_http

    with pytest.raises(BrowserFetchTimeoutError):
        client.health()


def test_health_connection_error_raises_unavailable() -> None:
    """httpx.ConnectError on /health raises BrowserFetchUnavailable."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 30.0
    mock_http = MagicMock()
    mock_http.get.side_effect = httpx.ConnectError("refused")
    client._client = mock_http

    with pytest.raises(BrowserFetchUnavailable):
        client.health()


# ---------------------------------------------------------------------------
# wait_for DSL helpers
# ---------------------------------------------------------------------------


def test_css_helper_formats_correctly() -> None:
    assert BrowserFetchClient.css("#data-table") == "css:#data-table"
    assert BrowserFetchClient.css(".yield-curve") == "css:.yield-curve"


def test_timeout_ms_helper_formats_correctly() -> None:
    assert BrowserFetchClient.timeout_ms(5000) == "timeout:5000"
    assert BrowserFetchClient.timeout_ms(0) == "timeout:0"


# ---------------------------------------------------------------------------
# No silent fallback
# ---------------------------------------------------------------------------


def test_no_silent_fallback_error_responses_always_raise() -> None:
    """Explicit assertion: every non-2xx status code raises, never returns RenderResult."""
    error_cases = [
        (400, _error_body("BAD_URL", "bad")),
        (401, _error_body("UNAUTHORIZED", "auth")),
        (403, _error_body("UNAUTHORIZED", "auth")),
        (500, _error_body("INTERNAL", "crash")),
        (502, _error_body("UPSTREAM_FAILED", "upstream", http_code=503)),
        (503, _error_body("INTERNAL", "not ready")),
        (504, _error_body("RENDER_TIMEOUT", "timeout")),
    ]

    for status_code, body in error_cases:
        client = BrowserFetchClient.__new__(BrowserFetchClient)
        client._base_url = "http://localhost:18766"
        client._timeout = 30.0
        mock_http = MagicMock()
        mock_http.post.return_value = _make_response(status_code, body)
        client._client = mock_http

        with pytest.raises(BrowserFetchError, match=r".*"), \
             patch("hlpp_l0_contracts.browser_fetch.time.sleep"):
            client.render("https://example.com")


# ---------------------------------------------------------------------------
# Dataclass contracts
# ---------------------------------------------------------------------------


def test_render_result_is_frozen() -> None:
    """RenderResult.frozen=True prevents mutation."""
    result = RenderResult(
        rendered_html="<html/>",
        extracted_json=None,
        upstream_http_code=200,
        fetch_ms=100,
        cache_key="k1",
    )
    with pytest.raises(FrozenInstanceError):
        result.rendered_html = "mutated"  # type: ignore[misc]


def test_render_result_fields_always_present() -> None:
    """RenderResult has exactly the expected field set."""
    field_names = [f.name for f in fields(RenderResult)]
    assert field_names == [
        "rendered_html",
        "extracted_json",
        "upstream_http_code",
        "fetch_ms",
        "cache_key",
    ]


def test_cookie_validation_requires_name() -> None:
    with pytest.raises(ValueError, match="name"):
        Cookie(name="", value="val")


def test_cookie_validation_allows_empty_value() -> None:
    """Empty string value is valid (clears a cookie)."""
    c = Cookie(name="session", value="")
    assert c.value == ""


def test_cookie_to_dict_serializes_correctly() -> None:
    c = Cookie(name="s", value="v", domain="example.com", path="/")
    assert c.to_dict() == {
        "name": "s",
        "value": "v",
        "domain": "example.com",
        "path": "/",
    }


# ---------------------------------------------------------------------------
# Bearer token in header
# ---------------------------------------------------------------------------


def test_bearer_token_sent_in_authorization_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bearer token constructor arg adds Authorization header to all requests."""
    monkeypatch.delenv("HT_BROWSER_FETCH_URL", raising=False)
    monkeypatch.delenv("HT_BROWSER_FETCH_TOKEN", raising=False)

    with patch("hlpp_l0_contracts.browser_fetch.httpx.Client") as mock_cls:
        BrowserFetchClient(bearer_token="my-secret")
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["headers"]["Authorization"] == "Bearer my-secret"


# ---------------------------------------------------------------------------
# Public module exports
# ---------------------------------------------------------------------------


def test_browser_fetch_module_all_exports() -> None:
    """__all__ contains the expected public names."""
    from hlpp_l0_contracts import browser_fetch

    assert set(browser_fetch.__all__) == {
        "BrowserFetchClient",
        "DEFAULT_TIMEOUT_S",
        "Cookie",
        "RenderResult",
        "HealthResult",
        "BrowserFetchError",
        "BrowserFetchUnavailable",
        "BrowserFetchAuthError",
        "BrowserFetchTimeoutError",
        "BrowserFetchBadRequest",
        "BrowserFetchUpstreamFailed",
        "BrowserFetchPoolTimeout",
        "BrowserFetchServerError",
    }


def test_public_exports_reachable_from_package() -> None:
    """All browser_fetch types are importable from hlpp_l0_contracts top-level."""
    import hlpp_l0_contracts

    for name in (
        "BrowserFetchClient",
        "Cookie",
        "RenderResult",
        "HealthResult",
        "BrowserFetchError",
        "BrowserFetchUnavailable",
        "BrowserFetchAuthError",
        "BrowserFetchTimeoutError",
        "BrowserFetchBadRequest",
        "BrowserFetchUpstreamFailed",
        "BrowserFetchPoolTimeout",
        "BrowserFetchServerError",
    ):
        assert hasattr(hlpp_l0_contracts, name), f"hlpp_l0_contracts.{name} not exported"
        assert name in hlpp_l0_contracts.__all__, f"{name} missing from hlpp_l0_contracts.__all__"


# ---------------------------------------------------------------------------
# MAJOR fix: client default timeout (0.1.7)
# ---------------------------------------------------------------------------


def test_default_timeout_constant_is_45s() -> None:
    """DEFAULT_TIMEOUT_S module constant must equal 45.0.

    Service legal max = QUEUE_TIMEOUT_MS (10s) + MAX_RENDER_MS (30s) + 5s overhead.
    Any value below 45s causes false BrowserFetchTimeoutError under valid queued renders.
    """
    assert DEFAULT_TIMEOUT_S == 45.0


def test_constructor_default_timeout_is_45s(monkeypatch: pytest.MonkeyPatch) -> None:
    """BrowserFetchClient() with no timeout arg uses DEFAULT_TIMEOUT_S (45.0)."""
    monkeypatch.delenv("HT_BROWSER_FETCH_URL", raising=False)
    monkeypatch.delenv("HT_BROWSER_FETCH_TOKEN", raising=False)

    with patch("hlpp_l0_contracts.browser_fetch.httpx.Client") as mock_cls:
        BrowserFetchClient()
        call_kwargs = mock_cls.call_args[1]
        assert call_kwargs["timeout"] == 45.0, (
            f"Expected default timeout 45.0, got {call_kwargs['timeout']}. "
            "Service budget = QUEUE_TIMEOUT_MS(10s) + MAX_RENDER_MS(30s) + 5s overhead."
        )


# ---------------------------------------------------------------------------
# MINOR fix: fetch_ms plumbed through error classes (0.1.7)
# ---------------------------------------------------------------------------


def test_browser_fetch_error_base_accepts_fetch_ms() -> None:
    """BrowserFetchError base class stores fetch_ms attribute."""
    exc = BrowserFetchError("msg", fetch_ms=123)
    assert exc.fetch_ms == 123


def test_browser_fetch_error_fetch_ms_defaults_to_none() -> None:
    """BrowserFetchError.fetch_ms defaults to None (e.g. TCP-level errors)."""
    exc = BrowserFetchError("msg")
    assert exc.fetch_ms is None


def test_render_400_preserves_fetch_ms() -> None:
    """400 BAD_URL error: fetch_ms from service body is preserved on raised exception."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 45.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        400, _error_body("BAD_URL", "bad url", fetch_ms=5)
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchBadRequest) as exc_info:
        client.render("not-a-url")

    assert exc_info.value.fetch_ms == 5


def test_render_401_preserves_fetch_ms() -> None:
    """401 auth error: fetch_ms from service body is preserved on raised exception."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 45.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        401, _error_body("UNAUTHORIZED", "missing token", fetch_ms=0)
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchAuthError) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.fetch_ms == 0


def test_render_502_preserves_fetch_ms() -> None:
    """502 UPSTREAM_FAILED: fetch_ms from service body is preserved on raised exception."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 45.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        502, _error_body("UPSTREAM_FAILED", "upstream 404", http_code=404, fetch_ms=8200)
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchUpstreamFailed) as exc_info:
        client.render("https://example.com/missing")

    assert exc_info.value.fetch_ms == 8200


def test_render_503_preserves_fetch_ms() -> None:
    """503 not-ready: fetch_ms from service body is preserved on raised exception."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 45.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        503, _error_body("INTERNAL", "not ready", fetch_ms=0)
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchUnavailable) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.fetch_ms == 0


def test_render_504_preserves_fetch_ms() -> None:
    """504 RENDER_TIMEOUT: fetch_ms reflects how long service rendered before giving up."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 45.0
    mock_http = MagicMock()
    mock_http.post.return_value = _make_response(
        504, _error_body("RENDER_TIMEOUT", "render exceeded MAX_RENDER_MS", fetch_ms=30001)
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchServerError) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.fetch_ms == 30001


def test_render_500_preserves_fetch_ms() -> None:
    """500 INTERNAL: fetch_ms preserved; None when service omits it from body."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 45.0
    mock_http = MagicMock()
    # Service may omit fetch_ms on crash — _safe_json returns {} → .get("fetch_ms") = None
    mock_http.post.return_value = _make_response(
        500, {"status": "error", "error_code": "INTERNAL", "error_message": "crash"}
    )
    client._client = mock_http

    with pytest.raises(BrowserFetchServerError) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.fetch_ms is None


def test_fetch_ms_none_on_transport_error() -> None:
    """BrowserFetchTimeoutError (TCP-level) has fetch_ms=None — no service response body."""
    client = BrowserFetchClient.__new__(BrowserFetchClient)
    client._base_url = "http://localhost:18766"
    client._timeout = 45.0
    mock_http = MagicMock()
    mock_http.post.side_effect = httpx.TimeoutException("timed out")
    client._client = mock_http

    with pytest.raises(BrowserFetchTimeoutError) as exc_info:
        client.render("https://example.com")

    assert exc_info.value.fetch_ms is None
