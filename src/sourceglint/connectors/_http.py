"""Injectable stdlib HTTP transport for public-source connectors.

Requests use a per-call socket timeout and bounded retries for transient errors.
The timeout is not a total wall-clock deadline. Response bodies stay out of error
messages; adapters handle authorization and map transport failures to source status.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qsl, urlencode, urlsplit
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable

from ..deadline import limit_timeout, remaining_time
from ._paid import charge_attempt


DEFAULT_USER_AGENT = "sourceglint/0.2.0"
DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_ATTEMPTS = 3  # 1 initial + 2 retries
DEFAULT_BACKOFF_SECONDS = 0.5  # bounded; tests inject a 0 to skip sleeps


_METERED = {"api.scrapecreators.com", "api.x.com", "api.twitter.com", "api.brightdata.com"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


# ---------- exception taxonomy ------------------------------------------


class HttpError(Exception):
    """Base class for HTTP errors."""


class HttpTransientError(HttpError):
    """5xx / 429 / timeout — may be retried."""

    def __init__(self, status: int | None, url: str, body_preview: str = "") -> None:
        # Never include the response body in the message text — only a
        # length count, without including the response body.
        body_kb = len(body_preview) if body_preview else 0
        if status is None:
            super().__init__(f"transient error fetching {url} (no status); body {body_kb} bytes")
        else:
            super().__init__(
                f"transient error fetching {url} (status={status}); body {body_kb} bytes"
            )
        self.status = status
        self.url = url


class HttpPermanentError(HttpError):
    """4xx (excluding 429) — must NOT be retried."""

    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"permanent error fetching {url} (status={status})")
        self.status = status
        self.url = url


def _looks_rate_limited(exc: Exception, body_preview: str) -> bool:
    """Distinguish an abuse/rate-limit 403 from a real permission denial."""
    headers = getattr(exc, "headers", None)
    if headers is not None:
        if (headers.get("X-RateLimit-Remaining") or "").strip() == "0":
            return True
        if (headers.get("Retry-After") or "").strip():
            return True
    lowered = body_preview.casefold()
    return "rate limit" in lowered or "too many requests" in lowered


class HttpTimeoutError(HttpError):
    """The request exceeded its budget."""

    def __init__(self, url: str, timeout: float) -> None:
        super().__init__(f"timeout fetching {url} after {timeout}s")
        self.url = url
        self.timeout = timeout


# ---------- response DTO ------------------------------------------------


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""
    url: str = ""

    def json(self) -> Any:
        """Parse body as JSON. Raises json.JSONDecodeError on bad data."""

        return json.loads(self.body.decode("utf-8"))

    def text(self, encoding: str = "utf-8") -> str:
        return self.body.decode(encoding)


# ---------- HTTP client protocol ---------------------------------------


@runtime_checkable
class HttpClient(Protocol):
    """A small neutral HTTP contract every real connector speaks.

    Concrete implementations:
      * StdlibHttpClient   — production / live path
      * RecorderHttpClient — fixture-backed test double
    """

    user_agent: str

    def request(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        method: str = "GET",
        json_data: object | None = None,
        form_data: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> HttpResponse:
        ...


# ---------- stdlib implementation ---------------------------------------


@dataclass
class StdlibHttpClient:
    """Production HTTP client using Python's stdlib (urllib + socket)."""

    user_agent: str = DEFAULT_USER_AGENT
    default_timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    backoff_seconds: float = DEFAULT_BACKOFF_SECONDS
    # Injectable sleep hook for tests (avoid test sleep).
    sleep: callable = staticmethod(time.sleep)

    def request(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout: float | None = None,
        method: str = "GET",
        json_data: object | None = None,
        form_data: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> HttpResponse:
        """Issue a bounded HTTP request; retry only transient failures."""
        if json_data is not None and form_data is not None:
            raise ValueError("json_data and form_data are mutually exclusive")
        bound_timeout = float(timeout if timeout is not None else self.default_timeout)
        last_exc: Exception | None = None

        for attempt in range(1, max(1, self.max_attempts) + 1):
            try:
                attempt_timeout = limit_timeout(bound_timeout)
            except TimeoutError as exc:
                raise HttpTimeoutError(urlsplit(url)._replace(query="", fragment="").geturl(), bound_timeout) from exc
            try:
                return self._request_once(
                    url,
                    headers=headers,
                    timeout=attempt_timeout,
                    method=method,
                    json_data=json_data,
                    form_data=form_data,
                    max_bytes=max_bytes,
                )
            except (HttpTransientError, HttpTimeoutError) as exc:
                last_exc = exc
                if attempt >= self.max_attempts:
                    break
                delay = self.backoff_seconds * (2 ** (attempt - 1))
                remaining = remaining_time()
                if remaining is not None and remaining <= delay:
                    break
                try:
                    self.sleep(delay)
                except Exception:  # pragma: no cover - sleep injection is best-effort
                    pass
        assert last_exc is not None
        raise last_exc

    # -- internal -----------------------------------------------------

    def _request_once(
        self,
        url: str,
        *,
        headers: Mapping[str, str] | None,
        timeout: float,
        method: str,
        json_data: object | None,
        form_data: Mapping[str, str] | None = None,
        max_bytes: int | None = None,
    ) -> HttpResponse:
        # Build headers with User-Agent always first.
        merged: dict[str, str] = {"User-Agent": self.user_agent}
        if headers:
            for k, v in headers.items():
                if k.lower() == "user-agent":
                    continue  # never let caller override UA
                merged[k] = v
        body: bytes | None = None
        if json_data is not None:
            body = json.dumps(json_data, separators=(",", ":")).encode("utf-8")
            merged.setdefault("Content-Type", "application/json")
        elif form_data is not None:
            body = urlencode(form_data).encode("utf-8")
            merged.setdefault("Content-Type", "application/x-www-form-urlencoded")

        # Keep timeout state local to this request, including parallel enrichments.
        req = urllib.request.Request(
            url=url,
            headers=merged,
            data=body,
            method=method.upper(),
        )
        parsed = urlsplit(url)
        query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
        sensitive = query_keys & {"api_key", "access_token", "apikey", "client_secret"}
        protected = bool(sensitive or any(key.lower() in {"authorization", "x-api-key"} for key in merged))
        host = parsed.hostname
        metered = host in _METERED or (host == "api.openalex.org" and "api_key" in sensitive)
        safe_url = parsed._replace(query="", fragment="").geturl() if sensitive else url
        opener = urllib.request.build_opener(_NoRedirect()).open if protected or metered else urllib.request.urlopen
        if metered:
            charge_attempt(host or "metered source")
        try:
            with opener(req, timeout=timeout) as resp:
                status = int(getattr(resp, "status", 200) or 200)
                body = resp.read(max_bytes + 1) if max_bytes is not None else resp.read()
                if max_bytes is not None and len(body) > max_bytes:
                    # Oversized bodies are refused as a permanent error so a
                    # connector can report a bounded-access limitation.
                    raise HttpPermanentError(status=413, url=safe_url)
                # Map urllib's http.client.HTTPMessage to a plain dict.
                hdrs: dict[str, str] = {
                    k.lower(): v for k, v in resp.headers.items()
                }
                return HttpResponse(
                    status=status,
                    headers=hdrs,
                    body=body,
                    url=safe_url,
                )
        except urllib.error.HTTPError as exc:
            status = int(exc.code)
            body_preview = ""
            try:
                body_preview = (exc.read() or b"").decode("utf-8", "replace")
            except Exception:  # pragma: no cover - body-read is best-effort
                body_preview = ""
            if status == 429 or 500 <= status < 600 or (status == 403 and _looks_rate_limited(exc, body_preview)):
                raise HttpTransientError(
                    status=status,
                    url=safe_url,
                    body_preview="" if protected else body_preview,
                ) from None
            raise HttpPermanentError(status=status, url=safe_url) from None
        except urllib.error.URLError as exc:
            reason = str(getattr(exc, "reason", exc))
            if "timed out" in reason.lower() or "timeout" in reason.lower():
                raise HttpTimeoutError(url=safe_url, timeout=timeout) from None
            raise HttpTransientError(
                status=None, url=safe_url, body_preview="" if protected else reason
            ) from None
        except socket.timeout:
            raise HttpTimeoutError(url=safe_url, timeout=timeout) from None


# ---------- Re-exports --------------------------------------------------


__all__ = [
    "DEFAULT_USER_AGENT",
    "DEFAULT_TIMEOUT_SECONDS",
    "DEFAULT_MAX_ATTEMPTS",
    "DEFAULT_BACKOFF_SECONDS",
    "HttpError",
    "HttpTransientError",
    "HttpPermanentError",
    "HttpTimeoutError",
    "HttpResponse",
    "HttpClient",
    "StdlibHttpClient",
]
