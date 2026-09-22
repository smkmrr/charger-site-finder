"""HTTP access with retry and a disk cache, shared by every source."""

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from charger_finder.config import CACHE_DIR, CACHE_MAX_AGE_DAYS

logger = logging.getLogger(__name__)

#: Connect quickly, but allow a slow body: EPDK returns ~16 MB.
TIMEOUT = httpx.Timeout(10.0, read=120.0)

#: Status codes that mean "try again later", not "your request was wrong".
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryableStatusError(Exception):
    """A response whose status code is worth trying again."""


def _cache_path(name: str) -> Path:
    return CACHE_DIR / f"{name}.json"


def _cache_age_days(path: Path) -> float:
    return (time.time() - path.stat().st_mtime) / 86_400


@retry(
    retry=retry_if_exception_type(
        (httpx.TimeoutException, httpx.TransportError, RetryableStatusError)
    ),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    """Make one HTTP request, retrying only transient failures."""
    response = httpx.request(method, url, timeout=TIMEOUT, **kwargs)
    if response.status_code in RETRYABLE_STATUS:
        raise RetryableStatusError(f"{response.status_code} from {url}")
    response.raise_for_status()
    return response


def fetch_json(
    name: str, url: str, method: str = "GET", **kwargs: Any
) -> dict[str, Any] | list[Any]:
    """Return parsed JSON for `url`, using the cached copy while it is fresh."""
    path = _cache_path(name)

    if path.exists():
        age = _cache_age_days(path)
        if age < CACHE_MAX_AGE_DAYS:
            logger.info("cache hit: %s (%.1f days old)", name, age)
            return json.loads(path.read_text(encoding="utf-8"))
        logger.info("cache stale: %s (%.1f days old), refetching", name, age)

    response = _request(method, url, **kwargs)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(response.content)
    logger.info("fetched %s (%d bytes)", name, len(response.content))

    return response.json()