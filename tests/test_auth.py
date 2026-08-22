"""Tests for REST API-key and remote MCP OAuth configuration."""

from unittest.mock import Mock

import pytest

from lunchmoney_app.app import auth
from lunchmoney_app.config import RuntimeSettings, SecretSettings


def test_mcp_oauth_is_disabled_without_configuration() -> None:
    """Leave local MCP clients unauthenticated when OAuth is not configured."""
    assert auth.get_mcp_oauth_provider(settings=RuntimeSettings()) is None


def test_mcp_oauth_requires_complete_configuration() -> None:
    """Reject partial OAuth configuration before a server starts."""
    settings = RuntimeSettings.model_construct(
        mcp_oauth_config_url="https://id.example.com/.well-known/openid-configuration"
    )

    with pytest.raises(ValueError, match="LUNCHMONEY_APP_OAUTH_CLIENT_ID"):
        auth.get_mcp_oauth_provider(settings=settings)


def test_mcp_oauth_configures_oidc_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pass configured OIDC details to FastMCP's standards-compliant proxy."""
    proxy = Mock()
    oidc_proxy = Mock(return_value=proxy)
    settings = RuntimeSettings.model_construct(
        mcp_oauth_config_url="https://id.example.com/.well-known/openid-configuration",
        mcp_oauth_client_id="lunchmoney-app",
        mcp_oauth_base_url="https://mcp.example.com",
        mcp_oauth_audience="https://mcp.example.com",
    )
    secret_settings = SecretSettings.model_construct(
        mcp_oauth_client_secret="synthetic-secret"
    )
    monkeypatch.setattr(auth, "_oidc_proxy_class", lambda: oidc_proxy)

    assert (
        auth.get_mcp_oauth_provider(
            settings=settings,
            secret_settings=secret_settings,
        )
        is proxy
    )
    oidc_proxy.assert_called_once_with(
        config_url="https://id.example.com/.well-known/openid-configuration",
        client_id="lunchmoney-app",
        client_secret="synthetic-secret",
        audience="https://mcp.example.com",
        base_url="https://mcp.example.com",
    )
