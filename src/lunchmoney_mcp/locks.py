"""
Lock abstractions for process and distributed synchronization.
"""

from abc import ABC, abstractmethod
from types import TracebackType
from typing import Self

from filelock import FileLock as PyFileLock, Timeout as FileLockTimeout
import redis


class LockError(Exception):
    """Base exception for lock errors."""


class LockTimeoutError(LockError):
    """Raised when acquiring a lock times out or fails."""


class Lock(ABC):
    """Abstract base class for process and distributed locks."""

    @abstractmethod
    def acquire(self, blocking: bool = True, timeout: float | int = -1) -> bool:
        """
        Acquire the lock.

        Parameters
        ----------
        blocking: bool
            Whether to wait until the lock is acquired.
        timeout: float | int
            Maximum time in seconds to wait if blocking.

        Returns
        -------
        bool
            True if acquired, False otherwise.
        """

    @abstractmethod
    def release(self) -> None:
        """Release the lock."""

    @abstractmethod
    def is_locked(self) -> bool:
        """Return True if the lock is currently held."""

    def __enter__(self) -> Self:
        if not self.acquire():
            raise LockTimeoutError("Failed to acquire lock")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.release()


class LockFile(Lock):
    """File-based lock implementation wrapping filelock."""

    def __init__(self, path: str, timeout: float | int = 0) -> None:
        self.path = path
        self.default_timeout = timeout
        self._lock = PyFileLock(lock_file=path, timeout=timeout)

    def acquire(self, blocking: bool = True, timeout: float | int = -1) -> bool:
        effective_timeout = (
            timeout if timeout >= 0 else (self.default_timeout if blocking else 0)
        )
        try:
            self._lock.acquire(timeout=effective_timeout, poll_interval=0.05)
            return True
        except FileLockTimeout:
            return False

    def release(self) -> None:
        if self._lock.is_locked:
            self._lock.release()

    def is_locked(self) -> bool:
        return self._lock.is_locked


class Redis(Lock):
    """Distributed lock implementation backed by Redis."""

    def __init__(
        self,
        client: redis.Redis,
        name: str,
        expire: float | int | None = 60,
    ) -> None:
        self.client = client
        self.name = name
        self.expire = expire
        self._lock = client.lock(name=name, timeout=expire)

    def acquire(self, blocking: bool = True, timeout: float | int = -1) -> bool:
        blocking_timeout: float | None = float(timeout) if timeout >= 0 else None
        return bool(
            self._lock.acquire(blocking=blocking, blocking_timeout=blocking_timeout)
        )

    def release(self) -> None:
        if self._lock.locked():
            try:
                self._lock.release()
            except redis.exceptions.LockNotOwnedError:
                pass

    def is_locked(self) -> bool:
        return self._lock.locked()


# Aliases for convenience
FileLock = LockFile
RedisLock = Redis

__all__ = [
    "FileLock",
    "Lock",
    "LockError",
    "LockFile",
    "LockTimeoutError",
    "Redis",
    "RedisLock",
]
