"""Shared HTTP helper: one place for the User-Agent, timeouts and retry policy."""
from __future__ import annotations

import logging
import time

import requests

USER_AGENT = "WebProductIntelligencePortfolio/1.0 (educational project)"
LOGGER = logging.getLogger(__name__)


def new_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def get_response(url: str, session: requests.Session, *, params: dict | None = None,
                 timeout: int = 20, retries: int = 3) -> requests.Response:
    """GET with retries; the pause grows with each failed attempt."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_error = exc
            LOGGER.warning("Request failed (%s/%s) for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(attempt)
    raise RuntimeError(f"Could not fetch {url}: {last_error}") from last_error
