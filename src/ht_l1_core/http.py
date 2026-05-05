"""Resilient HTTP client with retry logic and ``Retry-After`` header support.

Exports ``HttpClient``, a thin wrapper around ``httpx.Client`` that retries on 429/5xx
errors and respects exponential backoff capped to a configurable maximum.
"""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential


def _parse_retry_after(value: str | None) -> float | None:
    if value is None:
        return None

    value = value.strip()
    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None

    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=timezone.utc)

    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())


def _is_retryable_exception(exc: BaseException) -> bool:
    if isinstance(exc, httpx.TimeoutException):
        return True

    if not isinstance(exc, httpx.HTTPStatusError):
        return False

    status_code = exc.response.status_code
    return status_code == 429 or 500 <= status_code <= 599


class _WaitRetryAfter:
    def __init__(
        self,
        *,
        multiplier: float = 1,
        minimum: float = 1,
        maximum: float = 60,
    ) -> None:
        self._fallback = wait_exponential(
            multiplier=multiplier,
            min=minimum,
            max=maximum,
        )

    def __call__(self, retry_state: Any) -> float:
        if retry_state.outcome is not None:
            exc = retry_state.outcome.exception()
            if (
                isinstance(exc, httpx.HTTPStatusError)
                and exc.response.status_code == 429
            ):
                retry_after = _parse_retry_after(exc.response.headers.get("Retry-After"))
                if retry_after is not None:
                    return retry_after

        return self._fallback(retry_state)


class HttpClient:
    def __init__(
        self,
        *,
        attempts: int = 5,
        backoff_multiplier: float = 1,
        backoff_min: float = 1,
        backoff_max: float = 60,
        trust_env: bool = True,
        **client_kwargs: Any,
    ) -> None:
        client_kwargs.setdefault("trust_env", trust_env)
        self._client = httpx.Client(**client_kwargs)
        self._retryer = Retrying(
            retry=retry_if_exception(_is_retryable_exception),
            wait=_WaitRetryAfter(
                multiplier=backoff_multiplier,
                minimum=backoff_min,
                maximum=backoff_max,
            ),
            stop=stop_after_attempt(attempts),
            reraise=True,
        )

    def get(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        return self._request("GET", url, **kwargs)

    def post(self, url: str | httpx.URL, **kwargs: Any) -> httpx.Response:
        return self._request("POST", url, **kwargs)

    def close(self) -> None:
        self._client.close()

    def _request(
        self,
        method: str,
        url: str | httpx.URL,
        **kwargs: Any,
    ) -> httpx.Response:
        def send() -> httpx.Response:
            response = self._client.request(method, url, **kwargs)
            response.raise_for_status()
            return response

        return self._retryer(send)
