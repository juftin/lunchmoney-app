"""Shared structural contracts and operation-local memoization."""

import asyncio
import copy
from collections.abc import Callable, Coroutine
from typing import Hashable, TypeVar

ValueT = TypeVar("ValueT")


class OperationMemo:
    """Coalesce equivalent reads within one operation only."""

    def __init__(self) -> None:
        """Create an empty operation-local task map."""
        self._tasks: dict[Hashable, asyncio.Task[object]] = {}
        self._closed = False

    async def get_or_create(
        self,
        key: Hashable,
        loader: Callable[[], Coroutine[object, object, ValueT]],
    ) -> ValueT:
        """Return a copied value while coalescing concurrent equivalent loads."""
        if self._closed:
            msg = "The operation memo is no longer active"
            raise RuntimeError(msg)
        task = self._tasks.get(key)
        if task is None:
            task = asyncio.create_task(loader())
            self._tasks[key] = task
        try:
            value = await task
        except BaseException:
            if self._tasks.get(key) is task:
                self._tasks.pop(key, None)
            raise
        return copy.deepcopy(value)  # type: ignore[return-value]

    def invalidate(self, *prefixes: str) -> None:
        """Discard memoized entries whose first key component matches a prefix."""
        if self._closed:
            msg = "The operation memo is no longer active"
            raise RuntimeError(msg)
        for key in tuple(self._tasks):
            namespace = key[0] if isinstance(key, tuple) and key else key
            if isinstance(namespace, str) and any(
                namespace.startswith(prefix) for prefix in prefixes
            ):
                task = self._tasks.pop(key)
                if not task.done():
                    task.cancel()

    def clear(self) -> None:
        """Release every operation-local value and cancel unfinished loads."""
        for task in self._tasks.values():
            if not task.done():
                task.cancel()
        self._tasks.clear()
        self._closed = True


__all__ = [
    "OperationMemo",
]
