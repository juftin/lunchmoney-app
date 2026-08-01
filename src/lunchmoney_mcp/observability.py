"""Safe structured logging and Prometheus-compatible operational metrics."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter
from collections.abc import Mapping
from typing import Any


class MetricsRegistry:
    """Collect the small, bounded set of metrics exposed by this service."""

    def __init__(self) -> None:
        """Initialize thread-safe counters and timing aggregates."""
        self._lock = threading.Lock()
        self._http_requests: Counter[tuple[str, str, int]] = Counter()
        self._mcp_requests: Counter[int] = Counter()
        self._upstream_failures: Counter[tuple[str, int | None]] = Counter()
        self._sync_runs: Counter[str] = Counter()
        self._sync_duration_seconds: dict[str, tuple[int, float]] = {}
        self._cache_last_successful_sync_timestamp: float | None = None

    def record_http_request(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_seconds: float,
        is_mcp: bool,
    ) -> None:
        """Record one request without storing caller-supplied values.

        Parameters
        ----------
        method : str
            HTTP method selected by the client.
        path : str
            Matched application route template, never a query string or body.
        status_code : int
            HTTP response status code.
        duration_seconds : float
            Completed request duration in seconds.
        is_mcp : bool
            Whether the request was handled by the MCP transport.
        """
        del duration_seconds
        with self._lock:
            self._http_requests[(method, path, status_code)] += 1
            if is_mcp:
                self._mcp_requests[status_code] += 1

    def record_upstream_failure(self, error: Exception) -> None:
        """Count an upstream failure, recognizing rate limits when available.

        Parameters
        ----------
        error : Exception
            Exception raised by the generated Lunch Money client. Its text is
            intentionally never stored or logged here.
        """
        status_code = _exception_status_code(error)
        kind = "rate_limited" if status_code == 429 else "error"
        with self._lock:
            self._upstream_failures[(kind, status_code)] += 1

    def record_sync(self, *, status: str, duration_seconds: float) -> None:
        """Record the final outcome and duration of one synchronization.

        Parameters
        ----------
        status : str
            Bounded final result label, such as ``success`` or ``failure``.
        duration_seconds : float
            Time spent in the synchronization workflow.
        """
        with self._lock:
            self._sync_runs[status] += 1
            count, total = self._sync_duration_seconds.get(status, (0, 0.0))
            self._sync_duration_seconds[status] = (count + 1, total + duration_seconds)

    def record_cache_refresh(self, timestamp: float | None = None) -> None:
        """Record when a successful sync last refreshed the local cache.

        Parameters
        ----------
        timestamp : float | None
            Unix timestamp of the completed refresh. Defaults to the current time.
        """
        with self._lock:
            self._cache_last_successful_sync_timestamp = timestamp or time.time()

    def render(self) -> str:
        """Render metrics in Prometheus' text exposition format.

        Returns
        -------
        str
            A complete, deterministic text response with no user financial data.
        """
        with self._lock:
            http_requests = dict(self._http_requests)
            mcp_requests = dict(self._mcp_requests)
            upstream_failures = dict(self._upstream_failures)
            sync_runs = dict(self._sync_runs)
            sync_durations = dict(self._sync_duration_seconds)
            cache_timestamp = self._cache_last_successful_sync_timestamp

        lines = [
            "# HELP lunchmoney_mcp_http_requests_total Completed HTTP requests.",
            "# TYPE lunchmoney_mcp_http_requests_total counter",
        ]
        lines.extend(
            _metric_line(
                "lunchmoney_mcp_http_requests_total",
                {"method": method, "path": path, "status": str(status)},
                count,
            )
            for (method, path, status), count in sorted(http_requests.items())
        )
        lines.extend(
            [
                "# HELP lunchmoney_mcp_mcp_requests_total Completed MCP transport requests.",
                "# TYPE lunchmoney_mcp_mcp_requests_total counter",
            ]
        )
        lines.extend(
            _metric_line(
                "lunchmoney_mcp_mcp_requests_total",
                {"status": str(status)},
                count,
            )
            for status, count in sorted(mcp_requests.items())
        )
        lines.extend(
            [
                "# HELP lunchmoney_mcp_upstream_failures_total Lunch Money API failures.",
                "# TYPE lunchmoney_mcp_upstream_failures_total counter",
            ]
        )
        lines.extend(
            _metric_line(
                "lunchmoney_mcp_upstream_failures_total",
                {
                    "kind": kind,
                    "status": str(status) if status is not None else "unknown",
                },
                count,
            )
            for (kind, status), count in sorted(
                upstream_failures.items(),
                key=lambda item: (item[0][0], item[0][1] or 0),
            )
        )
        lines.extend(
            [
                "# HELP lunchmoney_mcp_sync_runs_total Completed synchronization runs.",
                "# TYPE lunchmoney_mcp_sync_runs_total counter",
            ]
        )
        lines.extend(
            _metric_line("lunchmoney_mcp_sync_runs_total", {"status": status}, count)
            for status, count in sorted(sync_runs.items())
        )
        lines.extend(
            [
                "# HELP lunchmoney_mcp_sync_duration_seconds Synchronization duration in seconds.",
                "# TYPE lunchmoney_mcp_sync_duration_seconds summary",
            ]
        )
        for status, (count, total) in sorted(sync_durations.items()):
            lines.append(
                _metric_line(
                    "lunchmoney_mcp_sync_duration_seconds_count",
                    {"status": status},
                    count,
                )
            )
            lines.append(
                _metric_line(
                    "lunchmoney_mcp_sync_duration_seconds_sum",
                    {"status": status},
                    total,
                )
            )
        lines.extend(
            [
                "# HELP lunchmoney_mcp_cache_last_successful_sync_timestamp_seconds Unix timestamp of the last successful cache refresh.",
                "# TYPE lunchmoney_mcp_cache_last_successful_sync_timestamp_seconds gauge",
            ]
        )
        if cache_timestamp is not None:
            lines.append(
                _metric_line(
                    "lunchmoney_mcp_cache_last_successful_sync_timestamp_seconds",
                    {},
                    cache_timestamp,
                )
            )
        return "\n".join(lines) + "\n"


def _exception_status_code(error: Exception) -> int | None:
    """Extract an HTTP status code from common generated-client exception shapes."""
    for attribute in ("status", "status_code", "http_status"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value
    return None


def _metric_line(name: str, labels: Mapping[str, str], value: int | float) -> str:
    """Build one safely escaped Prometheus sample line."""
    if not labels:
        return f"{name} {value}"
    rendered_labels = ",".join(
        f'{key}="{value.replace("\\", "\\\\").replace(chr(34), '\\\\"')}"'
        for key, value in sorted(labels.items())
    )
    return f"{name}{{{rendered_labels}}} {value}"


def log_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """Emit one JSON log event from explicitly selected, non-sensitive fields.

    Parameters
    ----------
    logger : logging.Logger
        Logger that owns the event.
    event : str
        Stable event name.
    **fields : Any
        Caller-selected scalar operational fields. Request bodies, query strings,
        headers, tokens, and financial records must never be passed here.
    """
    logger.info(json.dumps({"event": event, **fields}, separators=(",", ":")))


metrics = MetricsRegistry()
"""Process-local bounded metrics registry exposed by the protected HTTP endpoint."""


__all__ = ["MetricsRegistry", "log_event", "metrics"]
