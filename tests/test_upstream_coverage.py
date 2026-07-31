"""Tests for the machine-readable Lunch Money endpoint coverage manifest."""

import asyncio
import importlib
import inspect
import json
import re
from pathlib import Path
from typing import Any

import lunchmoney

from lunchmoney_mcp.app.main import fastapi_app
from lunchmoney_mcp.mcp import mcp

PROJECT_ROOT = Path(__file__).resolve().parents[1]
"""Repository root used to load reviewed compatibility artifacts."""
SERIALIZER_PATTERN = re.compile(
    r"method='(?P<method>[A-Z]+)'.*?resource_path='(?P<path>[^']+)'", re.DOTALL
)
"""Generated OpenAPI-client serializer fields that identify an operation."""
API_ATTRIBUTES = {
    "budgets": lunchmoney.BudgetsApi,
    "categories": lunchmoney.CategoriesApi,
    "manual_accounts": lunchmoney.ManualAccountsApi,
    "me": lunchmoney.MeApi,
    "plaid": lunchmoney.PlaidAccountsApi,
    "recurring_items": lunchmoney.RecurringItemsApi,
    "summary": lunchmoney.SummaryApi,
    "tags": lunchmoney.TagsApi,
    "transactions": lunchmoney.TransactionsApi,
    "transactions_bulk": lunchmoney.TransactionsBulkApi,
    "transactions_files": lunchmoney.TransactionsFilesApi,
    "transactions_group": lunchmoney.TransactionsGroupApi,
    "transactions_split": lunchmoney.TransactionsSplitApi,
}
"""LunchableClient properties and their generated API classes."""


def load_manifest() -> dict[str, Any]:
    """Load the reviewed endpoint coverage manifest."""
    return json.loads((PROJECT_ROOT / "docs" / "upstream-coverage.json").read_text())


def generated_operations() -> set[tuple[str, str, str]]:
    """Return generated-client method, verb, and path triples."""
    operations: set[tuple[str, str, str]] = set()
    for attribute, api_class in API_ATTRIBUTES.items():
        for method_name, method in inspect.getmembers(
            api_class, inspect.iscoroutinefunction
        ):
            if method_name.startswith("_") or method_name.endswith(
                ("_with_http_info", "_without_preload_content")
            ):
                continue
            serializer = getattr(api_class, f"_{method_name}_serialize")
            match = SERIALIZER_PATTERN.search(inspect.getsource(serializer))
            assert match is not None
            operations.add(
                (f"{attribute}.{method_name}", match["method"], match["path"])
            )
    return operations


def test_coverage_manifest_matches_the_generated_client() -> None:
    """Require explicit coverage review for every generated upstream operation."""
    manifest = load_manifest()
    actual_operations = generated_operations()
    documented_operations = {
        (
            operation["upstream"]["client"],
            operation["upstream"]["method"],
            operation["upstream"]["path"],
        )
        for operation in manifest["operations"]
    }

    assert len(manifest["operations"]) == 39
    assert len(documented_operations) == len(manifest["operations"])
    assert documented_operations == actual_operations


def test_coverage_manifest_maps_every_operation_to_each_local_layer() -> None:
    """Require service, REST, and MCP registrations for every upstream operation."""
    manifest = load_manifest()
    openapi_paths = fastapi_app.openapi()["paths"]
    tool_names = {tool.name for tool in asyncio.run(mcp.list_tools())}

    for operation in manifest["operations"]:
        module_name, function_name = operation["service"].split(":", maxsplit=1)
        service = importlib.import_module(module_name)
        assert callable(getattr(service, function_name))

        route = operation["rest"]
        route_operation = openapi_paths[route["path"]][route["method"].lower()]
        assert route_operation["operationId"] == route["operation_id"]
        assert operation["mcp"] in tool_names
