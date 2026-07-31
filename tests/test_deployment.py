"""Regression tests for production deployment assets."""

from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).parents[1]
"""Repository root containing production deployment files."""


def test_container_uses_gunicorn_with_maintained_uvicorn_worker() -> None:
    """Serve the ASGI app with the supported production worker integration."""
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()

    assert 'CMD ["gunicorn", "lunchmoney_mcp.app:app"' in dockerfile
    assert '"--worker-class", "uvicorn_worker.GunicornWorker"' in dockerfile


def test_production_server_dependencies_are_declared() -> None:
    """Install the Gunicorn runtime and maintained worker package in releases."""
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()

    assert '"gunicorn>=23.0.0,<24"' in pyproject
    assert '"uvicorn-worker>=0.4.0,<1"' in pyproject
