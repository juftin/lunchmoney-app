"""Tests for installed package metadata."""

from importlib.metadata import version

from lunchmoney_app.__about__ import __application__, __version__


def test_package_metadata_matches_project_configuration() -> None:
    """Expose the configured distribution name and installed version."""
    assert __application__ == "lunchmoney-app"
    assert __version__ == version(__application__)
