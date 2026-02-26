from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict
from urllib import error, request

DEFAULT_USER_AGENT = "tokvera-python-sdk/0.1"


def ingest_event(event: Dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
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

    with request.urlopen(req, timeout=timeout):
        return


def ingest_event_async(event: Dict[str, Any], *, api_key: str, timeout: float = 2.0) -> None:
    def _worker() -> None:
        try:
            ingest_event(event, api_key=api_key, timeout=timeout)
        except (error.URLError, TimeoutError, ValueError, OSError):
            # Never fail caller flow because of analytics ingestion.
            return

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
