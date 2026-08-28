"""Lunch Money MCP package."""

import sys

from lunchmoney_app.__about__ import __application__, __version__

if sys.platform == "emscripten":
    __all__ = ["__application__", "__version__"]
else:
    from lunchmoney_app.app import app
    from lunchmoney_app.client import LunchMoneyApp, SyncSummary
    from lunchmoney_app.config import (
        RuntimeSettings,
        SecretSettings,
        get_secret_settings,
        get_settings,
    )
    from lunchmoney_app.database import DEFAULT_DATABASE_URL, LunchMoneyDatabase
    from lunchmoney_app.locks import (
        FileLock,
        Lock,
        LockError,
        LockFile,
        LockTimeoutError,
        Redis,
        RedisLock,
    )
    from lunchmoney_app.schemas import (
        AccountInfo,
        AccountsSummary,
        CategoryInfo,
        CategorySpending,
        ChildCategorySpending,
        GroupedSpendingResponse,
        RootResponse,
        SyncDetails,
        SyncResponse,
        SyncResult,
        TagInfo,
        TransactionInfo,
        UserInfo,
    )
    from lunchmoney_app.services import fetch_category_spending

    __all__ = [
        "DEFAULT_DATABASE_URL",
        "AccountInfo",
        "AccountsSummary",
        "__application__",
        "__version__",
        "CategoryInfo",
        "CategorySpending",
        "ChildCategorySpending",
        "FileLock",
        "GroupedSpendingResponse",
        "Lock",
        "LockError",
        "LockFile",
        "LockTimeoutError",
        "LunchMoneyApp",
        "LunchMoneyDatabase",
        "Redis",
        "RedisLock",
        "RootResponse",
        "RuntimeSettings",
        "SecretSettings",
        "SyncDetails",
        "SyncResponse",
        "SyncResult",
        "SyncSummary",
        "TagInfo",
        "TransactionInfo",
        "UserInfo",
        "app",
        "fetch_category_spending",
        "get_settings",
        "get_secret_settings",
    ]
