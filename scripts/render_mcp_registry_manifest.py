"""Render MCP Registry metadata for one immutable GitHub release."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).parents[1]
"""Repository root containing the stable registry manifest source."""

SOURCE_MANIFEST = ROOT / "mcp-registry" / "server.json"
"""Stable registry metadata augmented with release-specific MCPB details."""


def _create_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for registry manifest rendering."""
    parser = argparse.ArgumentParser(
        description="Render release-specific MCP Registry metadata."
    )
    parser.add_argument("--version", required=True, help="Released package version.")
    parser.add_argument("--mcpb", required=True, type=Path, help="Built MCPB artifact.")
    parser.add_argument(
        "--mcpb-url",
        required=True,
        help="Immutable release URL for the MCPB artifact.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path for the rendered server.json file.",
    )
    return parser


def _sha256(file_path: Path) -> str:
    """Return the SHA-256 digest for a distributable artifact.

    Parameters
    ----------
    file_path : pathlib.Path
        Artifact whose integrity digest is required by MCP Registry clients.
    """
    digest = hashlib.sha256()
    with file_path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_manifest(
    *,
    version: str,
    mcpb_path: Path,
    mcpb_url: str,
) -> dict[str, Any]:
    """Render registry metadata pointing to one PyPI and MCPB release.

    Parameters
    ----------
    version : str
        Semantic version shared by the project, PyPI distribution, and release.
    mcpb_path : pathlib.Path
        Locally built MCPB artifact to checksum.
    mcpb_url : str
        Immutable GitHub release asset URL for the MCPB artifact.

    Returns
    -------
    dict[str, typing.Any]
        Publish-ready MCP Registry manifest.

    Raises
    ------
    FileNotFoundError
        If the MCPB artifact has not been built.
    """
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    manifest["version"] = version
    manifest["packages"][0]["version"] = version
    manifest["packages"].append(
        {
            "registryType": "mcpb",
            "identifier": mcpb_url,
            "fileSha256": _sha256(mcpb_path),
            "transport": {"type": "stdio"},
        }
    )
    return manifest


def main() -> None:
    """Render the versioned manifest requested on the command line."""
    arguments = _create_argument_parser().parse_args()
    manifest = render_manifest(
        version=arguments.version,
        mcpb_path=arguments.mcpb,
        mcpb_url=arguments.mcpb_url,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
