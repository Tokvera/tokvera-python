from __future__ import annotations

import json
import os
import threading
import time
import warnings
from typing import Any, Dict
from urllib import error, request

DEFAULT_USER_AGENT = "tokvera-python-sdk/0.2.3"
DEFAULT_MAX_RETRIES = 2
DEFAULT_RETRY_DELAY_SECONDS = 0.25
MAX_ERROR_BODY_LENGTH = 256
RETRYABLE_HTTP_STATUS_CODES = {408, 409, 425, 429, 500, 502, 503, 504}


def _format_ingest_error(exc: Exception) -> str:
    if isinstance(exc, error.HTTPError):
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        detail = detail[:MAX_ERROR_BODY_LENGTH]
        if detail:
            return f"Tokvera ingestion failed (HTTP {exc.code}): {detail}"
        return f"Tokvera ingestion failed (HTTP {exc.code}): {exc.reason}"
    return f"Tokvera ingestion failed: {exc}"


def ingest_event(
    event: Dict[str, Any],
    *,
    api_key: str,
    timeout: float = 2.0,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> None:
    ingest_url = os.getenv("TOKVERA_INGEST_URL")
    if not ingest_url:
        return

    body = json.dumps(event).encode("utf-8")
    req = request.Request(
        ingest_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": DEFAULT_USER_AGENT,
        },
        method="POST",
    )

    for attempt in range(max_retries + 1):
        try:
            with request.urlopen(req, timeout=timeout):
                return
        except error.HTTPError as exc:
            if attempt >= max_retries or exc.code not in RETRYABLE_HTTP_STATUS_CODES:
                raise
        except (error.URLError, TimeoutError, OSError):
            if attempt >= max_retries:
                raise

        time.sleep(DEFAULT_RETRY_DELAY_SECONDS * (attempt + 1))


def ingest_event_async(event: Dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
    def _worker() -> None:
        try:
            ingest_event(event, api_key=api_key, timeout=timeout)
        except (error.URLError, error.HTTPError, TimeoutError, ValueError, OSError) as exc:
            # Never fail caller flow because of analytics ingestion.
            warnings.warn(_format_ingest_error(exc), RuntimeWarning, stacklevel=2)
            return

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
