"""Regression tests for production deployment assets."""

from pathlib import Path


PROJECT_ROOT: Path = Path(__file__).parents[1]
"""Repository root containing production deployment files."""


def test_container_uses_gunicorn_with_maintained_uvicorn_worker() -> None:
    """Serve the ASGI app with the supported production worker integration."""
    dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
    gunicorn_config = (PROJECT_ROOT / "gunicorn.conf.py").read_text()

    assert 'CMD ["gunicorn", "lunchmoney_mcp.app:app"]' in dockerfile
    assert '"uvicorn_worker.UvicornWorker"' in gunicorn_config
    assert "USER lunchmoney:lunchmoney" in dockerfile
    assert "apt-get update" in dockerfile
    assert "apt-get upgrade --yes" in dockerfile
    assert "rm -rf /var/lib/apt/lists/*" in dockerfile


def test_compose_keeps_data_services_private_and_hardens_app_processes() -> None:
    """Expose only loopback HTTP and restrict application container privileges."""
    compose = (PROJECT_ROOT / "docker-compose.yaml").read_text()

    assert '"127.0.0.1:8000:8000"' in compose
    assert '"5432:5432"' not in compose
    assert '"6379:6379"' not in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "http://127.0.0.1:8000/health" in compose
    assert '"X-API-Key": os.environ["LUNCHMONEY_MCP_API_KEY"]' in compose
    assert "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB" in compose
    assert "LUNCHMONEY_REDIS_URL: redis://redis:6379/0" in compose
    assert "LUNCHMONEY_ALLOWED_HOSTS" in compose
    assert "LUNCHMONEY_TRUSTED_PROXY_IPS" in compose
    assert "LUNCHMONEY_CORS_ALLOWED_ORIGINS" in compose


def test_ci_scans_release_artifacts_and_smoke_tests_compose() -> None:
    """Keep security scans and a production liveness/readiness check in CI."""
    workflow = (PROJECT_ROOT / ".github/workflows/security.yaml").read_text()

    assert "run: task security" in workflow
    assert "aquasecurity/trivy-action@v0.36.0" in workflow
    assert "scanners: secret,misconfig" in workflow
    assert "docker compose up --build --detach --wait" in workflow
    assert "X-API-Key: ${LUNCHMONEY_MCP_API_KEY}" in workflow
    assert "http://127.0.0.1:8000/health" in workflow
    assert "http://127.0.0.1:8000/ready" in workflow


def test_security_task_audits_locked_production_dependencies() -> None:
    """Keep project-specific audit tasks in the flattened taskfile include."""
    taskfile = (PROJECT_ROOT / "Taskfile.yaml").read_text()
    project_taskfile = (PROJECT_ROOT / "tasks/ProjectTaskfile.yaml").read_text()

    assert "taskfile: ./tasks/ProjectTaskfile.yaml" in taskfile
    assert "flatten: true" in taskfile
    assert "security:" in project_taskfile
    assert (
        "uv audit --preview-features audit --locked --no-group dev" in project_taskfile
    )


def test_ci_matrix_covers_supported_versions_and_defaults_locally_to_python_313() -> (
    None
):
    """Keep unified CI coverage aligned with supported runtimes and local defaults."""
    taskfile = (PROJECT_ROOT / "Taskfile.yaml").read_text()
    workflow = (PROJECT_ROOT / ".github/workflows/ci.yaml").read_text()
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()

    assert (PROJECT_ROOT / ".python-version").read_text().strip() == "3.13"
    assert 'requires-python = ">=3.10"' in pyproject
    assert 'PYTHON: ["3.10", "3.11", "3.12", "3.13", "3.14"]' in taskfile
    for version in ("3.10", "3.11", "3.12", "3.13", "3.14"):
        assert f'python: "{version}"' in workflow


def test_project_tasks_keep_integration_checks_opt_in_and_on_ci() -> None:
    """Run external mock-service checks only through their explicit task and workflow."""
    project_taskfile = (PROJECT_ROOT / "tasks/ProjectTaskfile.yaml").read_text()
    workflow = (PROJECT_ROOT / ".github/workflows/upstream-contract.yaml").read_text()

    assert "test:unit:" in project_taskfile
    assert '-m "not integration"' in project_taskfile
    assert "test:integration:" in project_taskfile
    assert "RUN_LUNCHMONEY_CONTRACT_TESTS=1" in project_taskfile
    assert "run: task contract" in workflow


def test_production_server_dependencies_are_declared() -> None:
    """Install the Gunicorn runtime and maintained worker package in releases."""
    pyproject = (PROJECT_ROOT / "pyproject.toml").read_text()

    assert '"gunicorn>=23.0.0,<24"' in pyproject
    assert '"uvicorn-worker>=0.4.0,<1"' in pyproject
