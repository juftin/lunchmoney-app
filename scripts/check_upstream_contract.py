"""Snapshot and verify the pinned Lunch Money OpenAPI/client contract."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import inspect
import io
import json
import re
import tarfile
import tomllib
import urllib.request
from enum import Enum
from pathlib import Path
from typing import Any

import lunchmoney
import lunchmoney.models
import yaml
from pydantic import BaseModel

PROJECT_ROOT = Path(__file__).resolve().parents[1]
"""Repository root used to find the pin and reviewed snapshot."""
SNAPSHOT_PATH = PROJECT_ROOT / "docs" / "upstream-contract.json"
"""Reviewed representation of the upstream spec and generated client."""
SERIALIZER_PATTERN = re.compile(
    r"method='(?P<method>[A-Z]+)'.*?resource_path='(?P<path>[^']+)'", re.DOTALL
)
"""Generated OpenAPI-client serializer fields that identify an operation."""


def load_configuration() -> dict[str, str]:
    """Return the pinned Lunch Money client and specification versions."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as project_file:
        project = tomllib.load(project_file)
    return project["tool"]["lunchmoney_contract"]


def download_specification(version: str) -> dict[str, Any]:
    """Download the exact OpenAPI specification package selected for review.

    Parameters
    ----------
    version
        Version of ``@lunch-money/v2-api-spec`` to retrieve from npm.
    """
    url = (
        "https://registry.npmjs.org/@lunch-money/v2-api-spec/-/"
        f"v2-api-spec-{version}.tgz"
    )
    with urllib.request.urlopen(url=url, timeout=30) as response:
        archive = response.read()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as package:
        spec_member = next(
            member
            for member in package.getmembers()
            if member.name.endswith("lunch-money-api-v2.yaml")
        )
        spec_file = package.extractfile(spec_member)
        if spec_file is None:
            msg = "The pinned OpenAPI package did not contain its YAML specification."
            raise RuntimeError(msg)
        return yaml.safe_load(spec_file)


def extract_specification_contract(specification: dict[str, Any]) -> dict[str, Any]:
    """Normalize paths, schemas, and enum values from an OpenAPI document."""
    operations = [
        {
            "method": method.upper(),
            "operation_id": operation.get("operationId"),
            "path": path,
        }
        for path, path_item in specification["paths"].items()
        for method, operation in path_item.items()
        if method.lower() in {"delete", "get", "patch", "post", "put"}
    ]
    schemas: dict[str, Any] = specification["components"]["schemas"]
    enums = {
        name: schema["enum"] for name, schema in schemas.items() if "enum" in schema
    }
    return {
        "openapi_version": specification["info"]["version"],
        "operations": sorted(
            operations, key=lambda item: (item["path"], item["method"])
        ),
        "schemas": fingerprint_schemas(schemas),
        "enums": enums,
    }


def extract_generated_operations() -> list[dict[str, str]]:
    """Return endpoint identities emitted by the installed generated client."""
    operations: list[dict[str, str]] = []
    for api_name, api_class in inspect.getmembers(lunchmoney, inspect.isclass):
        if not api_name.endswith("Api"):
            continue
        for method_name, method in inspect.getmembers(
            api_class, inspect.iscoroutinefunction
        ):
            if method_name.startswith("_") or method_name.endswith(
                ("_with_http_info", "_without_preload_content")
            ):
                continue
            serializer = getattr(api_class, f"_{method_name}_serialize")
            match = SERIALIZER_PATTERN.search(inspect.getsource(serializer))
            if match is None:
                msg = f"Could not find the endpoint metadata for {api_name}.{method_name}."
                raise RuntimeError(msg)
            operations.append(
                {
                    "api": api_name,
                    "method": match["method"],
                    "name": method_name,
                    "path": match["path"],
                }
            )
    return sorted(operations, key=lambda item: (item["path"], item["method"]))


def fingerprint_schemas(schemas: dict[str, Any]) -> dict[str, str]:
    """Return stable hashes that expose individual schema changes in a diff."""
    return {
        name: hashlib.sha256(
            json.dumps(schema, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        for name, schema in schemas.items()
    }


def extract_generated_models() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return normalized Pydantic schemas and enums from the installed client."""
    models: dict[str, Any] = {}
    enums: dict[str, list[str]] = {}
    for name, candidate in inspect.getmembers(lunchmoney.models, inspect.isclass):
        if candidate.__module__.startswith("lunchmoney.models") and issubclass(
            candidate, BaseModel
        ):
            models[name] = candidate.model_json_schema()
        if (
            candidate.__module__.startswith("lunchmoney.models")
            and issubclass(candidate, Enum)
            and candidate is not Enum
        ):
            enums[name] = [member.value for member in candidate]
    return fingerprint_schemas(models), enums


def build_contract() -> dict[str, Any]:
    """Build the complete, deterministic contract from the pinned inputs."""
    configuration = load_configuration()
    if (
        importlib.metadata.version(configuration["client_package"])
        != configuration["client_version"]
    ):
        msg = "Installed Lunch Money client does not match the reviewed version pin."
        raise RuntimeError(msg)
    specification = extract_specification_contract(
        download_specification(version=configuration["openapi_spec_version"])
    )
    models, enums = extract_generated_models()
    contract = {
        "client": {
            "package": configuration["client_package"],
            "version": lunchmoney.__version__,
            "operations": extract_generated_operations(),
            "models": models,
            "enums": enums,
        },
        "specification": {
            "package": configuration["openapi_spec_package"],
            "version": configuration["openapi_spec_version"],
            **specification,
        },
    }
    validate_client_against_spec(contract=contract)
    return contract


def validate_client_against_spec(contract: dict[str, Any]) -> None:
    """Ensure the generated client still represents every reviewed spec surface."""
    spec_operations = {
        (operation["method"], operation["path"])
        for operation in contract["specification"]["operations"]
    }
    client_operations = {
        (operation["method"], operation["path"])
        for operation in contract["client"]["operations"]
    }
    if client_operations != spec_operations:
        msg = "Generated client endpoints differ from the pinned OpenAPI specification."
        raise RuntimeError(msg)

    missing_models = (
        {name[:1].upper() + name[1:] for name in contract["specification"]["schemas"]}
        - set(contract["client"]["models"])
        - set(contract["client"]["enums"])
    )
    if missing_models:
        msg = "Generated client is missing schema types: " + ", ".join(
            sorted(missing_models)
        )
        raise RuntimeError(msg)

    for name, values in contract["specification"]["enums"].items():
        client_values = contract["client"]["enums"].get(name[:1].upper() + name[1:])
        if client_values != values:
            msg = f"Generated client enum differs from the spec: {name}."
            raise RuntimeError(msg)


def parse_arguments() -> argparse.Namespace:
    """Parse the explicit snapshot-refresh option."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="write the reviewed contract snapshot after validating it",
    )
    return parser.parse_args()


def main() -> None:
    """Verify or explicitly refresh the pinned upstream contract snapshot."""
    arguments = parse_arguments()
    current_contract = build_contract()
    rendered_contract = json.dumps(current_contract, indent=2, sort_keys=True) + "\n"
    if arguments.write:
        SNAPSHOT_PATH.write_text(rendered_contract)
        return
    if not SNAPSHOT_PATH.exists() or SNAPSHOT_PATH.read_text() != rendered_contract:
        msg = "Pinned upstream contract changed; review it and run `task upstream:refresh`."
        raise RuntimeError(msg)


if __name__ == "__main__":
    main()
