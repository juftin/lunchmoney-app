"""Regression tests for distributed MCP client manifests."""

from __future__ import annotations

import json
from pathlib import Path
import re
from runpy import run_path
from typing import Any


ROOT = Path(__file__).parents[1]
"""Repository root used to inspect distribution artifacts."""


def _read_json(relative_path: str) -> dict[str, Any]:
    """Read a JSON distribution artifact relative to the repository root."""
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_agent_bundles_use_the_published_stdio_server() -> None:
    """Keep Claude, Codex, and Gemini bundles aligned with the CLI entrypoint."""
    mcp_bundle = _read_json("plugins/lunchmoney-mcp/.mcp.json")
    claude_marketplace = _read_json(".claude-plugin/marketplace.json")
    codex_marketplace = _read_json(".agents/plugins/marketplace.json")
    gemini_extension = _read_json("gemini-extension.json")

    server = mcp_bundle["mcpServers"]["lunchmoney"]
    assert server["command"] == "uvx"
    assert server["args"] == ["lunchmoney-app", "mcp"]
    assert claude_marketplace["plugins"][0]["source"] == "./plugins/lunchmoney-mcp"
    assert codex_marketplace["plugins"][0]["source"]["path"] == (
        "./plugins/lunchmoney-mcp"
    )
    assert gemini_extension["mcpServers"]["lunchmoney"] == {
        "command": "uvx",
        "args": ["lunchmoney-app", "mcp"],
    }


def test_gemini_extension_declares_a_sensitive_token_setting() -> None:
    """Ensure Gemini installs request the only secret needed by the server."""
    gemini_extension = _read_json("gemini-extension.json")

    assert gemini_extension["settings"] == [
        {
            "name": "Lunch Money access token",
            "description": (
                "Personal access token used to query your Lunch Money account."
            ),
            "envVar": "LUNCHMONEY_ACCESS_TOKEN",
            "sensitive": True,
        }
    ]


def test_mcpb_declares_the_host_managed_uv_runtime() -> None:
    """Ensure the Claude Desktop bundle avoids a platform-specific virtualenv."""
    mcpb_manifest = _read_json("mcpb/manifest.json")

    assert mcpb_manifest["manifest_version"] == "0.4"
    assert mcpb_manifest["server"] == {
        "type": "uv",
        "entry_point": "src/lunchmoney_app/cli.py",
        "mcp_config": {
            "command": "uv",
            "args": [
                "run",
                "--directory",
                "${__dirname}",
                "lunchmoney-app",
                "mcp",
            ],
            "env": {
                "LUNCHMONEY_ACCESS_TOKEN": ("${user_config.lunchmoney_access_token}")
            },
        },
    }
    assert mcpb_manifest["user_config"]["lunchmoney_access_token"]["sensitive"]


def test_registry_manifest_binds_the_mcpb_integrity_hash(tmp_path: Path) -> None:
    """Publish both PyPI and immutable MCPB package metadata for each release."""
    mcpb_path = tmp_path / "lunchmoney-app.mcpb"
    mcpb_path.write_bytes(b"lunchmoney-mcpb")
    module = run_path(str(ROOT / "scripts/render_mcp_registry_manifest.py"))
    render_manifest = module["render_manifest"]

    manifest = render_manifest(
        version="1.2.3",
        mcpb_path=mcpb_path,
        mcpb_url="https://example.com/lunchmoney-app.mcpb",
    )

    assert manifest["name"] == "io.github.juftin/lunchmoney-app"
    assert manifest["version"] == "1.2.3"
    assert manifest["packages"][0]["registryType"] == "pypi"
    assert manifest["packages"][0]["version"] == "1.2.3"
    assert manifest["packages"][1] == {
        "registryType": "mcpb",
        "identifier": "https://example.com/lunchmoney-app.mcpb",
        "fileSha256": (
            "4c752cae036b0d2d1d734f71a9531675106dc0f163862a4b6fd3c20c5f80f690"
        ),
        "transport": {"type": "stdio"},
    }


def test_versioned_manifests_match_the_project_version() -> None:
    """Keep every installable bundle synchronized with the Python distribution."""
    module = run_path(str(ROOT / "scripts/sync_bundle_versions.py"))
    synchronize_versions = module["synchronize_versions"]
    project_metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version_match = re.search(
        r'^version = "(?P<version>[^"]+)"$',
        project_metadata,
        flags=re.MULTILINE,
    )
    assert project_version_match is not None

    assert (
        synchronize_versions(
            version=project_version_match["version"],
            check=True,
        )
        == []
    )


def test_version_sync_check_reports_mismatched_manifest(tmp_path: Path) -> None:
    """Reject release metadata that was not updated with the package version."""
    module = run_path(str(ROOT / "scripts/sync_bundle_versions.py"))
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"version": "0.0.1"}\n', encoding="utf-8")
    assert module["synchronize_versions"](
        version="1.0.0",
        check=True,
        manifest_paths=(manifest_path,),
    ) == [manifest_path]


def test_semantic_release_builds_and_publishes_mcp_artifacts() -> None:
    """Keep MCP artifact creation and registry publication in Semantic Release."""
    release_config = _read_json(".releaserc.json")
    plugin_options = [
        plugin[1]
        for plugin in release_config["plugins"]
        if isinstance(plugin, list) and len(plugin) == 2
    ]
    prepare_command = next(
        options["prepareCmd"] for options in plugin_options if "prepareCmd" in options
    )
    publish_command = next(
        options["publishCmd"] for options in plugin_options if "publishCmd" in options
    )
    github_assets = next(
        options["assets"]
        for options in plugin_options
        if "assets" in options
        and any("dist/" in str(asset) for asset in options["assets"])
    )

    assert "task mcpb" in prepare_command
    assert "task registry:manifest" in prepare_command
    assert "${nextRelease.gitTag}" in prepare_command
    assert {"path": "dist/lunchmoney-app.mcpb"} in github_assets
    assert {"path": "dist/mcp-registry/server.json"} in github_assets
    assert "mcp-publisher login github-oidc" in publish_command
    assert "mcp-publisher publish dist/mcp-registry/server.json" in publish_command
