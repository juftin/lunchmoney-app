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


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create command-line parsing for version synchronization."""
    parser = argparse.ArgumentParser(
        description="Synchronize distributable MCP manifest versions."
    )
    parser.add_argument("version", help="Semantic release version without a v prefix.")
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


def _versions(document: dict[str, Any]) -> list[str]:
    """Collect every release-coupled version within one manifest.

    Parameters
    ----------
    document : dict[str, typing.Any]
        Parsed distribution manifest.

    Returns
    -------
    list[str]
        Top-level and nested package versions that must match the release.
    """
    versions = [document["version"]]
    if "plugins" in document:
        versions.extend(plugin["version"] for plugin in document["plugins"])
    if "packages" in document:
        versions.extend(
            package["version"]
            for package in document["packages"]
            if "version" in package
        )
    return versions


def _set_versions(document: dict[str, Any], version: str) -> None:
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
    if "packages" in document:
        for package in document["packages"]:
            if "version" in package:
                package["version"] = version


def synchronize_versions(
    *,
    version: str,
    check: bool,
    manifest_paths: Sequence[Path] = MANIFEST_PATHS,
) -> list[Path]:
    """Synchronize or validate every distributable manifest version.

    Parameters
    ----------
    version : str
        Semantic release version without a v prefix.
    check : bool
        Whether to validate manifests without modifying them.
    manifest_paths : collections.abc.Sequence[pathlib.Path]
        Manifests to synchronize. Defaults to every versioned distribution
        manifest in the repository.

    Returns
    -------
    list[pathlib.Path]
        Manifests that differed from the requested version.
    """
    mismatched_paths: list[Path] = []
    for path in manifest_paths:
        document = _load_manifest(path)
        if set(_versions(document)) == {version}:
            continue
        mismatched_paths.append(path)
        if not check:
            _set_versions(document, version)
            path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return mismatched_paths


def main() -> None:
    """Synchronize manifests or report every version mismatch."""
    arguments = _create_argument_parser().parse_args()
    mismatched_paths = synchronize_versions(
        version=arguments.version,
        check=arguments.check,
    )
    if arguments.check and mismatched_paths:
        relative_paths = [str(path.relative_to(ROOT)) for path in mismatched_paths]
        print("Version mismatch: " + ", ".join(relative_paths), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
