from __future__ import annotations

import importlib.util
import io
from pathlib import Path
from urllib import error

import pytest

INGEST_PATH = Path(__file__).resolve().parents[1] / "tokvera" / "ingest.py"
SPEC = importlib.util.spec_from_file_location("tokvera_local_ingest", INGEST_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Failed to load ingest module from {INGEST_PATH}")

ingest_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ingest_module)

ingest_event = ingest_module.ingest_event
ingest_event_async = ingest_module.ingest_event_async


class _DummyResponse:
    def __enter__(self) -> "_DummyResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False


def _http_error(url: str, status: int, message: str, body: str = "") -> error.HTTPError:
    return error.HTTPError(url, status, message, hdrs=None, fp=io.BytesIO(body.encode("utf-8")))


def test_ingest_event_retries_retryable_http_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKVERA_INGEST_URL", "https://ingest.example.test/v1/events")
    monkeypatch.setattr(ingest_module.time, "sleep", lambda _: None)

    calls = {"count": 0}

    def fake_urlopen(req, timeout):  # noqa: ANN001
        _ = timeout
        calls["count"] += 1
        if calls["count"] == 1:
            raise _http_error(req.full_url, 500, "Internal Server Error", '{"ok":false}')
        return _DummyResponse()

    monkeypatch.setattr(ingest_module.request, "urlopen", fake_urlopen)

    ingest_event({"schema_version": "2026-02-16"}, api_key="test_key")
    assert calls["count"] == 2


def test_ingest_event_raises_non_retryable_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOKVERA_INGEST_URL", "https://ingest.example.test/v1/events")
    monkeypatch.setattr(ingest_module.time, "sleep", lambda _: None)

    def fake_urlopen(req, timeout):  # noqa: ANN001
        _ = timeout
        raise _http_error(req.full_url, 402, "Payment Required", '{"code":"PROJECT_HARD_CAP_REACHED"}')

    monkeypatch.setattr(ingest_module.request, "urlopen", fake_urlopen)

    with pytest.raises(error.HTTPError) as exc_info:
        ingest_event({"schema_version": "2026-02-16"}, api_key="test_key")

    assert exc_info.value.code == 402


def test_ingest_event_async_warns_on_non_2xx_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ImmediateThread:
        def __init__(self, target, daemon):  # noqa: ANN001
            _ = daemon
            self._target = target

        def start(self) -> None:
            self._target()

    def failing_ingest(*args, **kwargs):  # noqa: ANN002, ANN003
        raise _http_error("https://ingest.example.test/v1/events", 402, "Payment Required", '{"ok":false}')

    monkeypatch.setattr(ingest_module.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(ingest_module, "ingest_event", failing_ingest)

    with pytest.warns(RuntimeWarning, match="HTTP 402"):
        ingest_event_async({"schema_version": "2026-02-16"}, api_key="test_key")
