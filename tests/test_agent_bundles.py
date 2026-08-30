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


def _read_json_from_path(path: Path) -> dict[str, Any]:
    """Read a JSON distribution artifact from an explicit filesystem path."""
    return json.loads(path.read_text(encoding="utf-8"))


def _project_version() -> str:
    """Read the current Python distribution version from project metadata."""
    project_metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    project_version_match = re.search(
        r'^version = "(?P<version>[^"]+)"$',
        project_metadata,
        flags=re.MULTILINE,
    )
    assert project_version_match is not None
    return project_version_match["version"]


def test_agent_bundles_use_the_published_stdio_server() -> None:
    """Keep Claude, Codex, and Gemini bundles aligned with the CLI entrypoint."""
    mcp_bundle = _read_json("plugins/lunchmoney-mcp/.mcp.json")
    claude_marketplace = _read_json(".claude-plugin/marketplace.json")
    codex_marketplace = _read_json(".agents/plugins/marketplace.json")
    gemini_extension = _read_json("gemini-extension.json")

    server = mcp_bundle["mcpServers"]["lunchmoney"]
    assert server["command"] == "uvx"
    expected_arguments = [
        "--from",
        f"lunchmoney-app=={_project_version()}",
        "lunchmoney-app",
        "mcp",
    ]
    assert server["args"] == expected_arguments
    assert claude_marketplace["plugins"][0]["source"] == "./plugins/lunchmoney-mcp"
    assert claude_marketplace["plugins"][0]["category"] == "finance"
    assert codex_marketplace["plugins"][0]["source"]["path"] == (
        "./plugins/lunchmoney-mcp"
    )
    assert codex_marketplace["plugins"][0]["category"] == "Personal Finance"
    assert gemini_extension["mcpServers"]["lunchmoney"] == {
        "command": "uvx",
        "args": expected_arguments,
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
                "--locked",
                "--no-dev",
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
    """Publish immutable MCPB package metadata without waiting for PyPI."""
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
    assert manifest["packages"] == [
        {
            "registryType": "mcpb",
            "identifier": "https://example.com/lunchmoney-app.mcpb",
            "fileSha256": (
                "4c752cae036b0d2d1d734f71a9531675106dc0f163862a4b6fd3c20c5f80f690"
            ),
            "transport": {"type": "stdio"},
        }
    ]


def test_registry_source_starts_the_pypi_server() -> None:
    """Keep the source manifest usable for direct PyPI registry installs."""
    registry_manifest = _read_json("mcp-registry/server.json")

    assert registry_manifest["repository"]["id"] == "1314484565"
    assert registry_manifest["packages"][0]["runtimeHint"] == "uvx"
    assert registry_manifest["packages"][0]["packageArguments"] == [
        {"type": "positional", "value": "mcp"}
    ]


def test_codex_plugin_uses_supported_starter_prompt_shape() -> None:
    """Keep Codex starter prompts compatible with the marketplace contract."""
    plugin_manifest = _read_json("plugins/lunchmoney-mcp/.codex-plugin/plugin.json")

    assert plugin_manifest["interface"]["defaultPrompt"] == [
        "How much did I spend on dining this month?"
    ]
    assert plugin_manifest["interface"]["category"] == "Personal Finance"


def test_versioned_manifests_match_the_project_version() -> None:
    """Keep every installable bundle synchronized with the Python distribution."""
    module = run_path(str(ROOT / "scripts/sync_bundle_versions.py"))
    synchronize_versions = module["synchronize_versions"]
    assert (
        synchronize_versions(
            version=_project_version(),
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
        package_command_paths=(),
    ) == [manifest_path]


def test_version_sync_normalizes_prerelease_package_pins(tmp_path: Path) -> None:
    """Keep SemVer bundle metadata separate from PEP 440 package pins."""
    module = run_path(str(ROOT / "scripts/sync_bundle_versions.py"))
    manifest_path = tmp_path / "manifest.json"
    command_path = tmp_path / "command.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "0.0.1",
                "packages": [{"registryType": "pypi", "version": "0.0.1"}],
            }
        ),
        encoding="utf-8",
    )
    command_path.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "lunchmoney": {
                        "args": ["lunchmoney-app", "mcp"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    assert module["synchronize_versions"](
        version="1.0.0-beta.1",
        package_version="1.0.0b1",
        check=False,
        manifest_paths=(manifest_path,),
        package_command_paths=(command_path,),
    ) == [manifest_path, command_path]

    assert _read_json_from_path(manifest_path) == {
        "version": "1.0.0-beta.1",
        "packages": [{"registryType": "pypi", "version": "1.0.0b1"}],
    }
    assert _read_json_from_path(command_path)["mcpServers"]["lunchmoney"]["args"] == [
        "--from",
        "lunchmoney-app==1.0.0b1",
        "lunchmoney-app",
        "mcp",
    ]


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
    assert "PACKAGE_VERSION=$(uv version --short)" in prepare_command
    assert "--package-version $PACKAGE_VERSION" in prepare_command
    assert "${nextRelease.gitTag}" in prepare_command
    assert {"path": "dist/lunchmoney-app.mcpb"} in github_assets
    assert {"path": "dist/mcp-registry/server.json"} in github_assets
    assert "plugins/lunchmoney-mcp/.mcp.json" in next(
        options["assets"]
        for options in plugin_options
        if "assets" in options and "pyproject.toml" in options["assets"]
    )
    assert "mcp-publisher login github-oidc" in publish_command
    assert "mcp-publisher publish dist/mcp-registry/server.json" in publish_command
    assert "releases/latest" not in publish_command
    assert "v1.8.1" in publish_command
    assert "sha256sum --check --status" in publish_command
