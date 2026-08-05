"""Tests for operational health checks, request telemetry, and metrics."""

import json
import logging
from importlib import import_module
from unittest.mock import AsyncMock

import pytest
from starlette.testclient import TestClient

from lunchmoney_mcp.app.main import fastapi_app
from lunchmoney_mcp.observability import MetricsRegistry, log_event


class RateLimitedError(Exception):
    """Synthetic generated-client error carrying an HTTP rate-limit status."""

    status: int = 429
    """HTTP status exposed by the generated Lunch Money client."""


def test_health_liveness_bypasses_rest_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a process liveness probe available when the REST API is protected."""
    from lunchmoney_mcp.config import get_secret_settings, get_settings

    monkeypatch.setenv("LUNCHMONEY_MCP_API_KEY", "synthetic-api-key")
    get_settings.cache_clear()
    get_secret_settings.cache_clear()
    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    finally:
        get_settings.cache_clear()
        get_secret_settings.cache_clear()


def test_readiness_reports_database_and_scheduler_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose database readiness while identifying a disabled embedded scheduler."""
    from lunchmoney_mcp.config import RuntimeSettings, get_settings

    health_module = import_module("lunchmoney_mcp.app.routers.health")
    lifespan_module = import_module("lunchmoney_mcp.app.lifespan")
    settings = RuntimeSettings(embed_scheduler=False)
    monkeypatch.setattr(health_module, "get_settings", lambda: settings)
    monkeypatch.setattr(lifespan_module, "get_settings", lambda: settings)

    monkeypatch.setattr(
        health_module, "database_is_ready", AsyncMock(return_value=True)
    )
    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/ready")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "database": "ready",
        "scheduler": "not_configured",
    }


def test_readiness_hides_database_error_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return only a bounded unavailable status when a dependency is unhealthy."""
    from lunchmoney_mcp.config import RuntimeSettings, get_settings

    health_module = import_module("lunchmoney_mcp.app.routers.health")
    lifespan_module = import_module("lunchmoney_mcp.app.lifespan")
    settings = RuntimeSettings(embed_scheduler=False)
    monkeypatch.setattr(health_module, "get_settings", lambda: settings)
    monkeypatch.setattr(lifespan_module, "get_settings", lambda: settings)

    monkeypatch.setattr(
        health_module, "database_is_ready", AsyncMock(return_value=False)
    )
    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/ready")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "database": "unavailable",
        "scheduler": "not_configured",
    }


def test_metrics_require_configured_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject metric scrapes unless the operator configured REST authentication."""
    from lunchmoney_mcp.config import get_secret_settings, get_settings

    monkeypatch.delenv("LUNCHMONEY_MCP_API_KEY", raising=False)
    get_settings.cache_clear()
    get_secret_settings.cache_clear()
    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/metrics")

        assert response.status_code == 403
        assert response.json() == {
            "detail": "Metrics endpoint requires API key configuration"
        }
    finally:
        get_settings.cache_clear()
        get_secret_settings.cache_clear()


def test_metrics_include_safe_http_and_mcp_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expose bounded route labels and require the configured API key."""
    from lunchmoney_mcp.config import get_secret_settings, get_settings

    monkeypatch.setenv("LUNCHMONEY_MCP_API_KEY", "synthetic-api-key")
    get_settings.cache_clear()
    get_secret_settings.cache_clear()
    try:
        with TestClient(fastapi_app) as client:
            response = client.get("/api", headers={"X-API-Key": "synthetic-api-key"})
            metrics_response = client.get(
                "/metrics", headers={"X-API-Key": "synthetic-api-key"}
            )

        assert response.headers["X-Request-ID"]
        assert metrics_response.status_code == 200
        assert metrics_response.headers["content-type"].startswith("text/plain")
        assert (
            'lunchmoney_mcp_http_requests_total{method="GET",path="/api",status="200"}'
            in metrics_response.text
        )
        assert "lunchmoney_mcp_mcp_requests_total" in metrics_response.text
        assert "synthetic-api-key" not in metrics_response.text
    finally:
        get_settings.cache_clear()
        get_secret_settings.cache_clear()


def test_metrics_registry_tracks_sync_and_rate_limit_without_error_text() -> None:
    """Track useful failures and freshness without retaining exception details."""
    registry = MetricsRegistry()
    error = RateLimitedError("sensitive upstream response")

    registry.record_upstream_failure(error)
    registry.record_sync(status="success", duration_seconds=1.5)
    registry.record_cache_refresh(timestamp=123.0)
    rendered = registry.render()

    assert (
        'lunchmoney_mcp_upstream_failures_total{kind="rate_limited",status="429"} 1'
        in rendered
    )
    assert 'lunchmoney_mcp_sync_runs_total{status="success"} 1' in rendered
    assert (
        "lunchmoney_mcp_cache_last_successful_sync_timestamp_seconds 123.0" in rendered
    )
    assert "sensitive upstream response" not in rendered


def test_structured_request_log_omits_sensitive_values(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Emit parseable operational events containing only supplied safe fields."""
    logger = logging.getLogger("tests.observability")
    with caplog.at_level(logging.INFO, logger=logger.name):
        log_event(
            logger,
            "http_request",
            request_id="request-id",
            method="GET",
            path="/transactions",
            status_code=200,
        )

    assert len(caplog.records) == 1
    assert json.loads(caplog.records[0].message) == {
        "event": "http_request",
        "request_id": "request-id",
        "method": "GET",
        "path": "/transactions",
        "status_code": 200,
    }
