"""Public response-shape contracts for collection REST and MCP interfaces."""

import inspect
from importlib import import_module
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from lunchmoney.models import (
    CategoryObject,
    ManualAccountObject,
    PlaidAccountObject,
    RecurringObject,
    TagObject,
    TransactionObject,
)
from starlette.testclient import TestClient

from database.factories import (
    category_object,
    manual_account_object,
    plaid_account_object,
    tag_object,
    transaction_object,
)
from lunchmoney_mcp.app.dependencies import get_database, get_lunchmoney_app
from lunchmoney_mcp.app.main import fastapi_app
from lunchmoney_mcp.schemas import AccountsSummary
from lunchmoney_mcp.mcp.tools.accounts import (
    list_accounts,
    list_manual_accounts,
    list_plaid_accounts,
)
from lunchmoney_mcp.mcp.tools.categories import list_categories
from lunchmoney_mcp.mcp.tools.recurring import list_recurring_items
from lunchmoney_mcp.mcp.tools.tags import list_tags
from lunchmoney_mcp.mcp.tools.transactions import list_transactions

accounts_router_module = import_module("lunchmoney_mcp.app.routers.accounts")
"""Accounts router module used for service delegation overrides."""
categories_router_module = import_module("lunchmoney_mcp.app.routers.categories")
"""Categories router module used for service delegation overrides."""
recurring_router_module = import_module("lunchmoney_mcp.app.routers.recurring")
"""Recurring-items router module used for service delegation overrides."""
tags_router_module = import_module("lunchmoney_mcp.app.routers.tags")
"""Tags router module used for service delegation overrides."""
transactions_router_module = import_module("lunchmoney_mcp.app.routers.transactions")
"""Transactions router module used for service delegation overrides."""


def _recurring_item() -> RecurringObject:
    """Create a complete synthetic recurring item for HTTP serialization tests."""
    return RecurringObject.model_validate(
        {
            "id": 81,
            "description": "Synthetic recurring item",
            "status": "reviewed",
            "transaction_criteria": {
                "start_date": None,
                "end_date": None,
                "granularity": "month",
                "quantity": 1,
                "anchor_date": "2026-01-01",
                "payee": "Synthetic subscription",
                "amount": "12.0000",
                "to_base": 12,
                "currency": "usd",
                "plaid_account_id": None,
                "manual_account_id": None,
            },
            "overrides": {"payee": None, "notes": None, "category_id": None},
            "matches": None,
            "created_by": 1,
            "created_at": "2026-01-01T12:00:00Z",
            "updated_at": "2026-01-01T12:00:00Z",
            "source": "manual",
        }
    )


def _collection_contract_app() -> FastAPI:
    """Build a lifespan-free app containing only collection endpoint routers."""
    app = FastAPI()
    app.include_router(categories_router_module.router)
    app.include_router(accounts_router_module.router)
    app.include_router(tags_router_module.router)
    app.include_router(recurring_router_module.router)
    app.include_router(transactions_router_module.router)
    app.dependency_overrides[get_database] = lambda: object()
    app.dependency_overrides[get_lunchmoney_app] = lambda: object()
    return app


def test_rest_collection_response_contracts_are_flat_arrays() -> None:
    """Publish direct collection endpoints as arrays of complete resource objects."""
    openapi = fastapi_app.openapi()
    expected_items = {
        "/categories": "CategoryObject",
        "/manual_accounts": "ManualAccountObject",
        "/plaid_accounts": "PlaidAccountObject",
        "/tags": "TagObject",
        "/recurring_items": "RecurringObject",
        "/transactions": "TransactionObject",
    }

    for path, item_schema in expected_items.items():
        schema = openapi["paths"][path]["get"]["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        assert schema["type"] == "array"
        assert schema["items"] == {"$ref": f"#/components/schemas/{item_schema}"}


def test_accounts_is_the_only_combined_collection_envelope() -> None:
    """Keep the shared accounts response as two named complete collections."""
    openapi = fastapi_app.openapi()
    schema = openapi["paths"]["/accounts"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert schema == {"$ref": "#/components/schemas/AccountsSummary"}

    properties = openapi["components"]["schemas"]["AccountsSummary"]["properties"]
    assert set(properties) == {"manual_accounts", "plaid_accounts"}
    assert properties["manual_accounts"]["type"] == "array"
    assert properties["plaid_accounts"]["type"] == "array"


def test_account_routes_match_upstream_paths_and_parameter_names() -> None:
    """Expose account operation paths and IDs with Lunch Money's exact spelling."""
    paths = fastapi_app.openapi()["paths"]

    for path in ("/manual_accounts/{id}", "/plaid_accounts/{id}"):
        assert path in paths
        for operation in paths[path].values():
            parameters = operation.get("parameters", [])
            path_parameter_names = [
                parameter["name"]
                for parameter in parameters
                if parameter["in"] == "path"
            ]
            assert path_parameter_names == ["id"]

    fetch_parameters = paths["/plaid_accounts/fetch"]["post"]["parameters"]
    assert "id" in {parameter["name"] for parameter in fetch_parameters}


def test_mcp_collection_tool_contracts_are_flat_arrays() -> None:
    """Advertise the same flattened collection shapes through MCP tools."""
    expected_annotations = {
        list_categories: list[CategoryObject],
        list_manual_accounts: list[ManualAccountObject],
        list_plaid_accounts: list[PlaidAccountObject],
        list_tags: list[TagObject],
        list_recurring_items: list[RecurringObject],
        list_transactions: list[TransactionObject],
    }

    for tool, annotation in expected_annotations.items():
        assert inspect.signature(tool).return_annotation == annotation

    assert (
        inspect.signature(list_accounts).return_annotation.__name__ == "AccountsSummary"
    )


def test_rest_collection_endpoints_serialize_their_runtime_contracts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Serialize direct collections as arrays and shared accounts as one object."""
    category = category_object()
    manual_account = manual_account_object()
    plaid_account = plaid_account_object()
    tag = tag_object()
    recurring_item = _recurring_item()
    transaction = transaction_object()
    accounts = AccountsSummary(
        manual_accounts=[manual_account],
        plaid_accounts=[plaid_account],
    )

    monkeypatch.setattr(
        categories_router_module,
        "fetch_categories",
        AsyncMock(return_value=[category]),
    )
    monkeypatch.setattr(
        accounts_router_module,
        "fetch_manual_accounts",
        AsyncMock(return_value=[manual_account]),
    )
    monkeypatch.setattr(
        accounts_router_module,
        "fetch_plaid_accounts",
        AsyncMock(return_value=[plaid_account]),
    )
    monkeypatch.setattr(
        accounts_router_module,
        "fetch_accounts",
        AsyncMock(return_value=accounts),
    )
    monkeypatch.setattr(tags_router_module, "fetch_tags", AsyncMock(return_value=[tag]))
    monkeypatch.setattr(
        recurring_router_module,
        "fetch_recurring_items",
        AsyncMock(return_value=[recurring_item]),
    )
    monkeypatch.setattr(
        transactions_router_module,
        "fetch_transactions",
        AsyncMock(return_value=[transaction]),
    )

    expected_collections = {
        "/categories": [category],
        "/manual_accounts": [manual_account],
        "/plaid_accounts": [plaid_account],
        "/tags": [tag],
        "/recurring_items": [recurring_item],
        "/transactions": [transaction],
    }
    app = _collection_contract_app()

    with TestClient(app, base_url="http://localhost") as client:
        for path, expected in expected_collections.items():
            response = client.get(path)
            assert response.status_code == 200
            assert response.json() == [
                item.model_dump(mode="json", by_alias=True) for item in expected
            ]

        accounts_response = client.get("/accounts")

    assert accounts_response.status_code == 200
    assert accounts_response.json() == accounts.model_dump(mode="json", by_alias=True)
