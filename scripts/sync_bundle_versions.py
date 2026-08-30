"""Synchronize distributable MCP manifest versions with the package release."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
"""Repository root containing all release-versioned distribution manifests."""

MANIFEST_PATHS = (
    ROOT / ".claude-plugin/marketplace.json",
    ROOT / "gemini-extension.json",
    ROOT / "mcp-registry/server.json",
    ROOT / "mcpb/manifest.json",
    ROOT / "plugins/lunchmoney-mcp/.claude-plugin/plugin.json",
    ROOT / "plugins/lunchmoney-mcp/.codex-plugin/plugin.json",
)
"""JSON manifests whose versions are released alongside the Python package."""

PACKAGE_COMMAND_PATHS = (
    ROOT / "gemini-extension.json",
    ROOT / "plugins/lunchmoney-mcp/.mcp.json",
)
"""Manifests that launch the version-pinned PyPI distribution."""


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create command-line parsing for version synchronization."""
    parser = argparse.ArgumentParser(
        description="Synchronize distributable MCP manifest versions."
    )
    parser.add_argument("version", help="Semantic release version without a v prefix.")
    parser.add_argument(
        "--package-version",
        help=(
            "Canonical PEP 440 package version. Defaults to the semantic release "
            "version for stable releases."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail instead of writing when any manifest has a different version.",
    )
    return parser


def _load_manifest(path: Path) -> dict[str, Any]:
    """Load one versioned distribution manifest.

    Parameters
    ----------
    path : pathlib.Path
        JSON manifest to load.

    Returns
    -------
    dict[str, typing.Any]
        Parsed manifest object.
    """
    return json.loads(path.read_text(encoding="utf-8"))


def _metadata_versions(document: dict[str, Any]) -> list[str]:
    """Collect every release-coupled version within one manifest.

    Parameters
    ----------
    document : dict[str, typing.Any]
        Parsed distribution manifest.

    Returns
    -------
    list[str]
        Top-level and nested marketplace versions that must match the release.
    """
    versions = [document["version"]]
    if "plugins" in document:
        versions.extend(plugin["version"] for plugin in document["plugins"])
    return versions


def _package_versions(document: dict[str, Any]) -> list[str]:
    """Collect PyPI distribution versions from one manifest.

    Parameters
    ----------
    document : dict[str, typing.Any]
        Parsed distribution manifest.

    Returns
    -------
    list[str]
        PEP 440 package versions declared by the manifest.
    """
    return [
        package["version"]
        for package in document.get("packages", [])
        if package.get("registryType") == "pypi" and "version" in package
    ]


def _set_metadata_versions(document: dict[str, Any], version: str) -> None:
    """Apply one release version to every release-coupled metadata field.

    Parameters
    ----------
    document : dict[str, typing.Any]
        Parsed distribution manifest to update in place.
    version : str
        Semantic release version without a v prefix.
    """
    document["version"] = version
    if "plugins" in document:
        for plugin in document["plugins"]:
            plugin["version"] = version


def _set_package_versions(document: dict[str, Any], package_version: str) -> None:
    """Apply a PEP 440 version to PyPI package records in a manifest.

    Parameters
    ----------
    document : dict[str, typing.Any]
        Parsed distribution manifest to update in place.
    package_version : str
        Canonical version published to PyPI.
    """
    for package in document.get("packages", []):
        if package.get("registryType") == "pypi" and "version" in package:
            package["version"] = package_version


def _server_arguments(document: dict[str, Any]) -> list[str]:
    """Return the Lunch Money MCP server command arguments from a manifest.

    Parameters
    ----------
    document : dict[str, typing.Any]
        Parsed Claude/Codex or Gemini manifest.

    Returns
    -------
    list[str]
        Arguments passed to ``uvx``.
    """
    return document["mcpServers"]["lunchmoney"]["args"]


def _set_server_arguments(document: dict[str, Any], package_version: str) -> None:
    """Pin a client launch command to the package release it advertises.

    Parameters
    ----------
    document : dict[str, typing.Any]
        Parsed Claude/Codex or Gemini manifest to update in place.
    package_version : str
        Canonical version published to PyPI.
    """
    document["mcpServers"]["lunchmoney"]["args"] = [
        "--from",
        f"lunchmoney-app=={package_version}",
        "lunchmoney-app",
        "mcp",
    ]


def synchronize_versions(
    *,
    version: str,
    package_version: str | None = None,
    check: bool,
    manifest_paths: Sequence[Path] = MANIFEST_PATHS,
    package_command_paths: Sequence[Path] = PACKAGE_COMMAND_PATHS,
) -> list[Path]:
    """Synchronize or validate every distributable manifest version.

    Parameters
    ----------
    version : str
        Semantic release version without a v prefix.
    package_version : str | None
        Canonical PEP 440 Python package version. Defaults to ``version`` for
        stable releases.
    check : bool
        Whether to validate manifests without modifying them.
    manifest_paths : collections.abc.Sequence[pathlib.Path]
        Manifests to synchronize. Defaults to every versioned distribution
        manifest in the repository.
    package_command_paths : collections.abc.Sequence[pathlib.Path]
        Manifests whose ``uvx`` command must pin the Python package version.

    Returns
    -------
    list[pathlib.Path]
        Manifests that differed from the requested version.
    """
    resolved_package_version = package_version or version
    mismatched_paths: list[Path] = []
    for path in manifest_paths:
        document = _load_manifest(path)
        metadata_matches = set(_metadata_versions(document)) == {version}
        package_versions = _package_versions(document)
        packages_match = not package_versions or set(package_versions) == {
            resolved_package_version
        }
        if metadata_matches and packages_match:
            continue
        mismatched_paths.append(path)
        if not check:
            _set_metadata_versions(document, version)
            _set_package_versions(document, resolved_package_version)
            path.write_text(json.dumps(document, indent=4) + "\n", encoding="utf-8")

    expected_arguments = [
        "--from",
        f"lunchmoney-app=={resolved_package_version}",
        "lunchmoney-app",
        "mcp",
    ]
    for path in package_command_paths:
        document = _load_manifest(path)
        if _server_arguments(document) == expected_arguments:
            continue
        if path not in mismatched_paths:
            mismatched_paths.append(path)
        if not check:
            _set_server_arguments(document, resolved_package_version)
            path.write_text(json.dumps(document, indent=4) + "\n", encoding="utf-8")
    return mismatched_paths


def main() -> None:
    """Synchronize manifests or report every version mismatch."""
    arguments = _create_argument_parser().parse_args()
    mismatched_paths = synchronize_versions(
        version=arguments.version,
        package_version=arguments.package_version,
        check=arguments.check,
    )
    if arguments.check and mismatched_paths:
        relative_paths = [str(path.relative_to(ROOT)) for path in mismatched_paths]
        print("Version mismatch: " + ", ".join(relative_paths), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
