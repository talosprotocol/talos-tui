"""Base HTTP adapter module for Talos TUI."""
from __future__ import annotations

import asyncio
import logging
import random
import time
import re
from typing import Any, Dict, Optional, TypeVar
import aiohttp
from yarl import URL
from aiohttp import ClientTimeout

from ..ports.errors import TuiError


logger = logging.getLogger(__name__)

DENYLIST = {
    "authorization", "token", "secret", "password", "private_key",
    "api_key", "cookie", "set-cookie", "session", "ciphertext",
    "header_b64u", "ciphertext_b64u", "nonce", "x-talos-token", "x-capability"
}

PEM_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]+-----(.*?)-----END [A-Z ]+-----", re.DOTALL
)
JWT_PATTERN = re.compile(
    r"eyJ[a-zA-Z0-9-_]+\.eyJ[a-zA-Z0-9-_]+\.[a-zA-Z0-9-_]+"
)


def redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Redact sensitive keys in a dictionary recursively."""

    new_data = {}
    for k, v in data.items():
        if k.lower() in DENYLIST:
            new_data[k] = "***REDACTED***"
        else:
            new_data[k] = redact_value(v)
    return new_data


def redact_value(v: Any) -> Any:
    """Redact a single value based on type and content patterns."""

    if isinstance(v, dict):
        return redact_dict(v)
    elif isinstance(v, list):
        return [redact_value(i) for i in v]
    elif isinstance(v, str):
        if PEM_PATTERN.search(v):
            return "***PEM REDACTED***"
        if len(v) > 100 and JWT_PATTERN.match(v):  # Heuristic for JWT
            return "***JWT REDACTED***"
        if len(v) > 65536:  # Cap large fields
            return v[:64] + "...(TRUNCATED)"
    return v


T = TypeVar("T")


class BaseHttpAdapter:
    """
    Base HTTP adapter with strict safety invariants:
    - Exponential backoff with jitter
    - Redacted structured logging
    - Hard timeouts and payload limits
    - Normalized error classification
    """

    def __init__(
        self,
        base_url: str,
        session: aiohttp.ClientSession,
        max_attempts: int = 5,
        connect_timeout: float = 3.0,
        total_timeout: float = 10.0,
        max_response_size: int = 1_000_000,  # 1MB
    ):
        self.base_url = URL(base_url)
        self.session = session
        self.max_attempts = max_attempts
        self.timeout = ClientTimeout(
            connect=connect_timeout, total=total_timeout
        )
        self.max_response_size = max_response_size

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = self.base_url / path.lstrip("/")

        attempt = 0
        while attempt < self.max_attempts:
            attempt += 1
            start_time = time.perf_counter()

            try:
                async with self.session.request(
                    method,
                    url,
                    params=params,
                    json=json_data,
                    timeout=self.timeout
                ) as resp:
                    latency_ms = int((time.perf_counter() - start_time) * 1000)

                    # Structured Log
                    logger.info(
                        "HTTP %s %s -> %s (%sms) [Attempt %s]",
                        method,
                        url,
                        resp.status,
                        latency_ms,
                        attempt,
                    )
                    if resp.status == 429:

                        retry_after = float(
                            resp.headers.get("Retry-After", 1.0)
                        )
                        logger.warning(
                            "Rate limited (429). Retrying after %ss",
                            retry_after,
                        )

                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status == 401 or resp.status == 403:

                        raise TuiError(
                            kind="AUTH",
                            message=f"Access denied ({resp.status})",
                            status_code=resp.status,
                        )

                    if resp.status == 404:
                        raise TuiError(
                            kind="BAD_RESPONSE",
                            message="Endpoint not found (404)",
                            status_code=resp.status,
                        )

                    if resp.status >= 500:
                        if attempt < self.max_attempts:
                            await self._backoff(attempt)
                            continue
                        raise TuiError(
                            kind="NETWORK",
                            message=f"Server error {resp.status}",
                            status_code=resp.status,
                            retryable=True,
                        )

                    if resp.status >= 400:
                        raise TuiError(
                            kind="BAD_RESPONSE",
                            message=f"Client error {resp.status}",
                            status_code=resp.status,
                        )

                    # Max payload check
                    if (
                        resp.content_length
                        and resp.content_length > self.max_response_size
                    ):
                        raise TuiError(
                            kind="PAYLOAD_TOO_LARGE",
                            message=f"Response exceeds limit "
                                    f"{self.max_response_size}",
                        )

                    data = await resp.json()
                    # We assume JSON response is a dict for our use cases
                    return redact_value(data)  # type: ignore

            except asyncio.TimeoutError as exc:
                logger.warning("Timeout on %s (Attempt %s)", url, attempt)
                if attempt < self.max_attempts:
                    await self._backoff(attempt)
                    continue
                raise TuiError(
                    kind="TIMEOUT",
                    message="Request timed out",
                    retryable=True
                ) from exc

            except aiohttp.ClientError as e:
                logger.warning(
                    "Network error on %s: %s (Attempt %s)", url, e, attempt
                )

                if attempt < self.max_attempts:
                    await self._backoff(attempt)
                    continue
                raise TuiError(
                    kind="NETWORK", message=str(e), retryable=True
                ) from e

            except TuiError:
                raise
            except Exception as e:
                logger.exception("Unexpected error on %s", url)
                raise TuiError(kind="UNKNOWN", message=str(e)) from e

        raise TuiError(
            kind="NETWORK",
            message="Max retry attempts reached",
            retryable=True,
        )

    async def _backoff(self, attempt: int) -> None:
        # Exponential backoff: base * 2^(attempt-1) + jitter
        base_delay = 0.5
        max_delay = 5.0
        delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
        jitter = random.uniform(0, 0.1 * delay)
        total_delay = delay + jitter
        logger.info("Backing off for %.2fs...", total_delay)
        await asyncio.sleep(total_delay)
