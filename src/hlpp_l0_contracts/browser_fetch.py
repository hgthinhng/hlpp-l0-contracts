"""BrowserFetchClient — sync HTTP client for the hlpp-l0-browser L0 service.

Provides typed access to ``POST /render`` and ``GET /health`` on the
hlpp-l0-browser headless-Chromium rendering service (ADR-019).

Usage::

    from hlpp_l0_contracts import BrowserFetchClient

    client = BrowserFetchClient()          # picks up HLPP_BROWSER_FETCH_URL / HLPP_BROWSER_FETCH_TOKEN from env
    result = client.render("https://data.hnx.vn/...", wait_for="networkidle")
    print(result.rendered_html)

Base-URL resolution (first wins):
  1. Explicit ``base_url`` constructor argument
  2. ``HLPP_BROWSER_FETCH_URL`` environment variable (fallback: ``HT_BROWSER_FETCH_URL``)
  3. Default ``http://localhost:18766``

Bearer-token resolution (first wins):
  1. Explicit ``bearer_token`` constructor argument
  2. ``HLPP_BROWSER_FETCH_TOKEN`` environment variable (fallback: ``HT_BROWSER_FETCH_TOKEN``)
  3. None (no auth — local dev default)

Sync API only for v0.1.7. Async client deferred to v0.1.8+. If a future
collector needs async, use ``AsyncBrowserFetchClient`` (to be added) rather
than wrapping this class in ``asyncio.to_thread``.

Retry policy: ``429 POOL_EXHAUSTED_QUEUE_TIMEOUT`` is retried automatically
up to 3 attempts with exponential backoff (base 1 s, cap 8 s) before raising
``BrowserFetchPoolTimeout``. All other errors raise immediately.

Error hierarchy::

    BrowserFetchError               (base — catch-all for consumers)
    ├── BrowserFetchUnavailable     (service down / connection refused / 503)
    ├── BrowserFetchAuthError       (401 / 403)
    ├── BrowserFetchTimeoutError    (client-side TCP/read timeout)
    ├── BrowserFetchBadRequest      (400 from service)
    ├── BrowserFetchUpstreamFailed  (502 UPSTREAM_FAILED — target site failed)
    ├── BrowserFetchPoolTimeout     (429 exhausted after retries)
    └── BrowserFetchServerError     (5xx other than 502)
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Literal

import httpx

# ---------------------------------------------------------------------------
# Public error hierarchy
# ---------------------------------------------------------------------------


class BrowserFetchError(Exception):
    """Base exception for all hlpp-l0-browser client errors.

    All specific sub-exceptions inherit from this so consumers can catch
    ``BrowserFetchError`` as a broad handler, or a specific sub-class for
    precise handling.

    ``fetch_ms`` is the upstream render duration reported by the service in the
    error envelope (SERVICE_SPEC §3).  It is ``None`` when the error occurred
    before the service produced a response body (e.g. TCP timeout, connection
    refused).  For service-originated errors (4xx / 5xx) it reflects how long
    the service worked before giving up — useful for diagnosing slow targets.
    """

    def __init__(
        self,
        message: str,
        *,
        http_code: int | None = None,
        service_message: str = "",
        request_url: str = "",
        fetch_ms: int | None = None,
    ) -> None:
        super().__init__(message)
        self.http_code = http_code
        self.service_message = service_message
        self.request_url = request_url
        self.fetch_ms = fetch_ms


class BrowserFetchUnavailable(BrowserFetchError):
    """Service unreachable: connection refused, DNS failure, 503, or health-check failure.

    This is an *infrastructure* error — the hlpp-l0-browser service itself is
    not reachable or not ready, not a problem with the target URL.
    """


class BrowserFetchAuthError(BrowserFetchError):
    """401 or 403 from service — missing or wrong bearer token.

    Set ``HLPP_BROWSER_FETCH_TOKEN`` env var (or legacy ``HT_BROWSER_FETCH_TOKEN``)
    or pass ``bearer_token`` to the constructor.
    """


class BrowserFetchTimeoutError(BrowserFetchError):
    """Client-side TCP connect or read timeout exceeded.

    The service did not respond within the configured ``timeout`` seconds.
    Distinct from 504 RENDER_TIMEOUT (which is a server-side per-render
    timeout returned as a normal HTTP response).
    """


class BrowserFetchBadRequest(BrowserFetchError):
    """400 from service — programmer error in request construction.

    error_code will be one of: BAD_URL, BAD_WAIT_FOR, BAD_RETURN.
    """

    def __init__(
        self,
        message: str,
        *,
        http_code: int = 400,
        service_message: str = "",
        request_url: str = "",
        error_code: str = "",
        fetch_ms: int | None = None,
    ) -> None:
        super().__init__(
            message,
            http_code=http_code,
            service_message=service_message,
            request_url=request_url,
            fetch_ms=fetch_ms,
        )
        self.error_code = error_code


class BrowserFetchUpstreamFailed(BrowserFetchError):
    """502 UPSTREAM_FAILED — service worked, but the target site returned a bad status.

    The ``upstream_http_code`` attribute contains what the target site returned
    (e.g. 404, 403, 5xx). Collectors should branch on this:

    - 404 → skip / mark missing
    - 403 → rotate cookie / proxy (future)
    - 5xx → retry later
    """

    def __init__(
        self,
        message: str,
        *,
        http_code: int = 502,
        service_message: str = "",
        request_url: str = "",
        upstream_http_code: int | None = None,
        fetch_ms: int | None = None,
    ) -> None:
        super().__init__(
            message,
            http_code=http_code,
            service_message=service_message,
            request_url=request_url,
            fetch_ms=fetch_ms,
        )
        self.upstream_http_code = upstream_http_code


class BrowserFetchPoolTimeout(BrowserFetchError):
    """429 POOL_EXHAUSTED_QUEUE_TIMEOUT — pool still full after all retry attempts.

    The client retried 3 times with exponential backoff before raising this.
    Callers may catch this and implement their own longer back-off strategy if
    they disabled the built-in retry (not recommended).
    """


class BrowserFetchServerError(BrowserFetchError):
    """5xx response from service other than 502 (covers 500 INTERNAL, 504 RENDER_TIMEOUT)."""


# ---------------------------------------------------------------------------
# Typed result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cookie:
    """Cookie to pre-set before Playwright navigation.

    ``name`` and ``value`` are required (validated on construction).
    ``domain`` and ``path`` are optional; Playwright requires at least ``domain``
    OR the page URL's origin — omitting both is valid when the service infers the
    domain from the target URL.
    """

    name: str
    value: str
    domain: str | None = None
    path: str | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Cookie.name must be a non-empty string")
        if self.value is None:
            # value="" is valid (clearing a cookie); None is not
            raise ValueError("Cookie.value must not be None")

    def to_dict(self) -> dict[str, str | None]:
        """Serialize to the JSON-ready dict expected by POST /render cookies array."""
        return {
            "name": self.name,
            "value": self.value,
            "domain": self.domain,
            "path": self.path,
        }


@dataclass(frozen=True)
class RenderResult:
    """Result of a successful POST /render call.

    All fields are always present. ``rendered_html`` and ``extracted_json`` are
    nullable depending on the ``return_mode`` requested:

    - ``return_mode="html"``  → ``rendered_html`` is str, ``extracted_json`` is None
    - ``return_mode="json"``  → ``extracted_json`` is list, ``rendered_html`` is None
    - ``return_mode="both"``  → both are populated

    ``upstream_http_code`` is the HTTP status returned by the *target site*
    (e.g. 200, 404), NOT the hlpp-l0-browser service's own status code.

    ``extracted_json`` is ``list[dict[str, Any]]`` with no further schema —
    the service extracts JSON from ``<script type="application/ld+json">`` and
    ``<script type="application/json">`` blocks; the shape of each object
    depends entirely on the target site.
    """

    rendered_html: str | None
    extracted_json: list[dict[str, Any]] | None
    upstream_http_code: int
    fetch_ms: int
    cache_key: str


@dataclass(frozen=True)
class HealthResult:
    """Result of a GET /health call.

    ``status`` is one of: ``"ok"``, ``"degraded"``, ``"unhealthy"``.
    ``"ok"`` means the service is ready to serve.
    ``"degraded"`` means the browser pool is still warming up.
    """

    status: str
    service: str
    version: str
    browser_pool_size: int
    browser_pool_available: int
    uptime_s: int


# ---------------------------------------------------------------------------
# Main client
# ---------------------------------------------------------------------------

#: Default client-side HTTP timeout in seconds.
#:
#: The hlpp-l0-browser service can legally spend up to::
#:
#:   QUEUE_TIMEOUT_MS (default 10 000 ms)   — wait for a free pool slot
#:   + MAX_RENDER_MS  (default 30 000 ms)   — actual Playwright render
#:   + ~5 s overhead                        — network RTT, response serialisation
#:   ─────────────────────────────────────────
#:   ≈ 45 s total end-to-end wall time
#:
#: Setting this below 45 s causes ``BrowserFetchTimeoutError`` on valid,
#: queued requests and doubles load when callers retry.  If you change
#: ``QUEUE_TIMEOUT_MS`` or ``MAX_RENDER_MS`` on the service side, bump this
#: constant accordingly.
DEFAULT_TIMEOUT_S: float = 45.0

_DEFAULT_BASE_URL = "http://localhost:18766"
_DEFAULT_TIMEOUT = DEFAULT_TIMEOUT_S
_POOL_TIMEOUT_RETRY_ATTEMPTS = 3
_POOL_TIMEOUT_BACKOFF_BASE = 1.0
_POOL_TIMEOUT_BACKOFF_CAP = 8.0


class BrowserFetchClient:
    """Sync HTTP client for the hlpp-l0-browser L0 rendering service.

    Thread-safety: instances share a single ``httpx.Client`` (connection pool).
    Do not share a single instance across threads without external locking.
    Construct one instance per thread or use ``close()`` between sequential
    batches.

    Examples::

        # Minimal — env-var config
        client = BrowserFetchClient()
        result = client.render("https://data.hnx.vn/...")

        # Explicit config (useful in tests)
        client = BrowserFetchClient(
            base_url="http://localhost:18766",
            timeout=60.0,
            bearer_token="secret",
        )

        # Wait-for helpers
        result = client.render(url, wait_for=BrowserFetchClient.css("#data-table"))
        result = client.render(url, wait_for=BrowserFetchClient.timeout_ms(5000))

        # Convenience shortcuts
        html: str = client.render_html(url)
        items: list[dict] = client.render_json(url)

        # Explicit cleanup (optional — GC will close on destruction)
        client.close()
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        bearer_token: str | None = None,
    ) -> None:
        resolved_url = (
            base_url
            or os.environ.get("HLPP_BROWSER_FETCH_URL")
            or os.environ.get("HT_BROWSER_FETCH_URL")
            or _DEFAULT_BASE_URL
        )
        self._base_url: str = resolved_url.rstrip("/")

        resolved_token = (
            bearer_token
            or os.environ.get("HLPP_BROWSER_FETCH_TOKEN")
            or os.environ.get("HT_BROWSER_FETCH_TOKEN")
        )
        self._timeout = timeout

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if resolved_token:
            headers["Authorization"] = f"Bearer {resolved_token}"

        self._client = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # wait_for DSL helpers
    # ------------------------------------------------------------------

    @staticmethod
    def css(selector: str) -> str:
        """Return a ``wait_for`` string that waits until a CSS selector matches.

        Example::

            result = client.render(url, wait_for=BrowserFetchClient.css("#data-table"))
        """
        return f"css:{selector}"

    @staticmethod
    def timeout_ms(ms: int) -> str:
        """Return a ``wait_for`` string that waits a fixed number of milliseconds.

        Example::

            result = client.render(url, wait_for=BrowserFetchClient.timeout_ms(5000))
        """
        return f"timeout:{ms}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(
        self,
        url: str,
        *,
        wait_for: str = "networkidle",
        cookies: list[Cookie] | None = None,
        user_agent: str | None = None,
        return_mode: Literal["html", "json", "both"] = "html",
    ) -> RenderResult:
        """Render a URL via headless Chromium and return the result.

        Args:
            url: Absolute target URL (must be ``http://`` or ``https://``).
            wait_for: Wait condition. One of: ``"networkidle"``,
                ``"domcontentloaded"``, ``"css:<selector>"``,
                ``"timeout:<ms>"``. Use ``BrowserFetchClient.css()`` and
                ``BrowserFetchClient.timeout_ms()`` helpers to build the latter two.
            cookies: Cookies to pre-set before navigation. Each must have
                ``name`` and ``value``; ``domain`` and ``path`` are optional.
            user_agent: Override the default Chromium User-Agent string.
            return_mode: What to return. ``"html"`` populates ``rendered_html``
                (``extracted_json`` is None). ``"json"`` populates
                ``extracted_json`` (``rendered_html`` is None). ``"both"``
                populates both. Note: ``return_mode`` maps to the service's
                ``return`` field — the Python alias avoids the keyword clash.

        Returns:
            ``RenderResult`` with all fields populated.

        Raises:
            BrowserFetchUnavailable: Service unreachable or returned 503.
            BrowserFetchAuthError: 401 or 403.
            BrowserFetchTimeoutError: Client-side timeout exceeded.
            BrowserFetchBadRequest: 400 (bad URL, bad wait_for, bad return value).
            BrowserFetchUpstreamFailed: 502 — target site returned non-2xx/3xx.
            BrowserFetchPoolTimeout: 429 exhausted after 3 retry attempts.
            BrowserFetchServerError: 500 or 504 from service.
        """
        body: dict[str, Any] = {
            "url": url,
            "wait_for": wait_for,
            "return": return_mode,  # alias: Python return_mode → service "return"
        }
        if cookies:
            body["cookies"] = [c.to_dict() for c in cookies]
        if user_agent is not None:
            body["user_agent"] = user_agent

        request_url = f"{self._base_url}/render"
        response = self._post_with_429_retry(request_url, body)
        return self._parse_render_response(response, request_url)

    def render_html(
        self,
        url: str,
        *,
        wait_for: str = "networkidle",
        cookies: list[Cookie] | None = None,
        user_agent: str | None = None,
    ) -> str:
        """Convenience shorthand: render and return the HTML string directly.

        Equivalent to ``render(..., return_mode="html").rendered_html`` with
        a guaranteed non-None return (raises if service returns no HTML).

        Raises:
            BrowserFetchError: (same hierarchy as ``render``)
            RuntimeError: Service returned 200 but rendered_html is None
                (should never happen with return_mode="html" — indicates a
                service contract violation).
        """
        result = self.render(
            url,
            wait_for=wait_for,
            cookies=cookies,
            user_agent=user_agent,
            return_mode="html",
        )
        if result.rendered_html is None:
            raise RuntimeError(
                f"Service returned 200 but rendered_html is None for {url!r}. "
                "This is a service contract violation."
            )
        return result.rendered_html

    def render_json(
        self,
        url: str,
        *,
        wait_for: str = "networkidle",
        cookies: list[Cookie] | None = None,
        user_agent: str | None = None,
    ) -> list[dict[str, Any]]:
        """Convenience shorthand: render and return the extracted JSON list directly.

        Equivalent to ``render(..., return_mode="json").extracted_json`` with
        a guaranteed non-None return.

        Raises:
            BrowserFetchError: (same hierarchy as ``render``)
            RuntimeError: Service returned 200 but extracted_json is None.
        """
        result = self.render(
            url,
            wait_for=wait_for,
            cookies=cookies,
            user_agent=user_agent,
            return_mode="json",
        )
        if result.extracted_json is None:
            raise RuntimeError(
                f"Service returned 200 but extracted_json is None for {url!r}. "
                "This is a service contract violation."
            )
        return result.extracted_json

    def health(self) -> HealthResult:
        """Call GET /health and return the parsed result.

        Useful for pre-flight checks in collector scripts and CI smoke tests.

        Returns:
            ``HealthResult`` with pool capacity and uptime info.

        Raises:
            BrowserFetchUnavailable: Service returned 503 or is unreachable.
            BrowserFetchTimeoutError: Client-side timeout exceeded.
        """
        request_url = f"{self._base_url}/health"
        try:
            response = self._client.get("/health")
        except httpx.TimeoutException as exc:
            raise BrowserFetchTimeoutError(
                f"Timeout reaching {request_url}",
                request_url=request_url,
            ) from exc
        except httpx.ConnectError as exc:
            raise BrowserFetchUnavailable(
                f"Cannot connect to hlpp-l0-browser at {request_url}: {exc}",
                request_url=request_url,
            ) from exc

        if response.status_code == 503:
            body = _safe_json(response)
            raise BrowserFetchUnavailable(
                "hlpp-l0-browser health check returned 503 — service not ready",
                http_code=503,
                service_message=body.get("error_message", ""),
                request_url=request_url,
            )
        if not response.is_success:
            raise BrowserFetchUnavailable(
                f"hlpp-l0-browser health check returned unexpected {response.status_code}",
                http_code=response.status_code,
                request_url=request_url,
            )

        data = response.json()
        return HealthResult(
            status=data["status"],
            service=data["service"],
            version=data["version"],
            browser_pool_size=data["browser_pool_size"],
            browser_pool_available=data["browser_pool_available"],
            uptime_s=data["uptime_s"],
        )

    def close(self) -> None:
        """Close the underlying httpx connection pool.

        Optional — the pool will be garbage-collected if not called, but
        explicit close avoids ResourceWarning in test suites.
        """
        self._client.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_with_429_retry(
        self,
        request_url: str,
        body: dict[str, Any],
    ) -> httpx.Response:
        """POST to ``request_url`` with built-in 429 exponential retry.

        Retries up to ``_POOL_TIMEOUT_RETRY_ATTEMPTS`` times on 429.
        All other errors surface immediately.
        """
        last_exc: BrowserFetchPoolTimeout | None = None
        for attempt in range(_POOL_TIMEOUT_RETRY_ATTEMPTS):
            try:
                response = self._client.post("/render", json=body)
            except httpx.TimeoutException as exc:
                raise BrowserFetchTimeoutError(
                    f"Timeout reaching {request_url}",
                    request_url=request_url,
                ) from exc
            except httpx.ConnectError as exc:
                raise BrowserFetchUnavailable(
                    f"Cannot connect to hlpp-l0-browser at {request_url}: {exc}",
                    request_url=request_url,
                ) from exc

            if response.status_code == 429:
                error_body = _safe_json(response)
                last_exc = BrowserFetchPoolTimeout(
                    f"hlpp-l0-browser pool exhausted (attempt {attempt + 1}/"
                    f"{_POOL_TIMEOUT_RETRY_ATTEMPTS}): "
                    f"{error_body.get('error_message', 'POOL_EXHAUSTED_QUEUE_TIMEOUT')}",
                    http_code=429,
                    service_message=error_body.get("error_message", ""),
                    request_url=request_url,
                )
                # Exponential backoff: 1s, 2s, 4s (capped at 8s)
                if attempt < _POOL_TIMEOUT_RETRY_ATTEMPTS - 1:
                    wait = min(
                        _POOL_TIMEOUT_BACKOFF_BASE * (2 ** attempt),
                        _POOL_TIMEOUT_BACKOFF_CAP,
                    )
                    time.sleep(wait)
                continue

            return response

        # All attempts exhausted on 429
        assert last_exc is not None
        raise last_exc

    def _parse_render_response(
        self,
        response: httpx.Response,
        request_url: str,
    ) -> RenderResult:
        """Map an httpx.Response from POST /render to ``RenderResult`` or raise."""
        code = response.status_code

        if response.is_success:
            data = response.json()
            return RenderResult(
                rendered_html=data.get("rendered_html"),
                extracted_json=data.get("extracted_json"),
                upstream_http_code=data["http_code"],
                fetch_ms=data["fetch_ms"],
                cache_key=data["cache_key"],
            )

        error_body = _safe_json(response)
        error_code = error_body.get("error_code", "")
        error_message = error_body.get("error_message", "")
        fetch_ms: int | None = error_body.get("fetch_ms")

        if code in (401, 403):
            raise BrowserFetchAuthError(
                f"hlpp-l0-browser auth error {code}: {error_message}",
                http_code=code,
                service_message=error_message,
                request_url=request_url,
                fetch_ms=fetch_ms,
            )

        if code == 400:
            raise BrowserFetchBadRequest(
                f"hlpp-l0-browser bad request ({error_code}): {error_message}",
                http_code=code,
                service_message=error_message,
                request_url=request_url,
                error_code=error_code,
                fetch_ms=fetch_ms,
            )

        if code == 502:
            upstream_http_code: int | None = error_body.get("http_code")
            raise BrowserFetchUpstreamFailed(
                f"hlpp-l0-browser upstream failed ({upstream_http_code}): {error_message}",
                http_code=code,
                service_message=error_message,
                request_url=request_url,
                upstream_http_code=upstream_http_code,
                fetch_ms=fetch_ms,
            )

        if code == 503:
            raise BrowserFetchUnavailable(
                f"hlpp-l0-browser returned 503 — not ready: {error_message}",
                http_code=503,
                service_message=error_message,
                request_url=request_url,
                fetch_ms=fetch_ms,
            )

        # 500, 504, and anything else unexpected
        raise BrowserFetchServerError(
            f"hlpp-l0-browser server error {code} ({error_code}): {error_message}",
            http_code=code,
            service_message=error_message,
            request_url=request_url,
            fetch_ms=fetch_ms,
        )


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    """Parse response body as JSON, returning empty dict on failure."""
    try:
        data = response.json()
        if isinstance(data, dict):
            return data
        return {}
    except Exception:
        return {}


__all__ = [
    # Client
    "BrowserFetchClient",
    # Constants
    "DEFAULT_TIMEOUT_S",
    # Result types
    "Cookie",
    "RenderResult",
    "HealthResult",
    # Errors
    "BrowserFetchError",
    "BrowserFetchUnavailable",
    "BrowserFetchAuthError",
    "BrowserFetchTimeoutError",
    "BrowserFetchBadRequest",
    "BrowserFetchUpstreamFailed",
    "BrowserFetchPoolTimeout",
    "BrowserFetchServerError",
]
