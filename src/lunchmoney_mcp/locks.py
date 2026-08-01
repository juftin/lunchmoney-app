"""Lock abstractions for process and distributed synchronization."""

from abc import ABC, abstractmethod
from types import TracebackType
from typing_extensions import Self

from filelock import FileLock as PyFileLock, Timeout as FileLockTimeout
import redis


class LockError(Exception):
    """Base exception for process and distributed lock errors."""


class LockTimeoutError(LockError):
    """Raised when acquiring a lock times out or fails to acquire within timeout limits."""


class Lock(ABC):
    """Abstract base class for process and distributed locks."""

    @abstractmethod
    def acquire(self, blocking: bool = True, timeout: float | int = -1) -> bool:
        """Acquire the lock.

        Parameters
        ----------
        blocking : bool
            Whether to wait until the lock is acquired. Default is True.
        timeout : float | int
            Maximum time in seconds to wait if blocking. Default is -1 (indefinite).

        Returns
        -------
        bool
            True if the lock was successfully acquired, False otherwise.
        """

    @abstractmethod
    def release(self) -> None:
        """Release the held lock."""

    @abstractmethod
    def is_locked(self) -> bool:
        """Check if the lock is currently held by any process.

        Returns
        -------
        bool
            True if the lock is currently held, False otherwise.
        """

    def __enter__(self) -> Self:
        """Context manager entry acquiring the lock.

        Returns
        -------
        Self
            The acquired Lock instance.

        Raises
        ------
        LockTimeoutError
            If acquiring the lock fails or times out.
        """
        if not self.acquire():
            raise LockTimeoutError("Failed to acquire lock")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """Context manager exit releasing the held lock.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type if an exception occurred within context.
        exc_val : BaseException | None
            Exception instance if an exception occurred within context.
        exc_tb : TracebackType | None
            Traceback if an exception occurred within context.
        """
        self.release()


class LockFile(Lock):
    """File-based lock implementation wrapping filelock.FileLock.

    Parameters
    ----------
    path : str
        File system path to the lock file.
    timeout : float | int
        Default acquisition timeout in seconds. Default is 0.
    """

    def __init__(self, path: str, timeout: float | int = 0) -> None:
        self.path = path
        """Path to the lock file."""
        self.default_timeout = timeout
        """Default acquisition timeout in seconds."""
        self._lock = PyFileLock(lock_file=path, timeout=timeout)

    def acquire(self, blocking: bool = True, timeout: float | int = -1) -> bool:
        """Acquire the file lock.

        Parameters
        ----------
        blocking : bool
            Whether to block waiting for lock release. Default is True.
        timeout : float | int
            Timeout in seconds. Default is -1.

        Returns
        -------
        bool
            True if acquired, False if timed out.
        """
        effective_timeout = (
            timeout if timeout >= 0 else (self.default_timeout if blocking else 0)
        )
        try:
            self._lock.acquire(timeout=effective_timeout, poll_interval=0.05)
            return True
        except FileLockTimeout:
            return False

    def release(self) -> None:
        """Release the file lock."""
        if self._lock.is_locked:
            self._lock.release()

    def is_locked(self) -> bool:
        """Check if the file lock is held.

        Returns
        -------
        bool
            True if file is currently locked.
        """
        return self._lock.is_locked


class Redis(Lock):
    """Distributed lock implementation backed by Redis.

    Parameters
    ----------
    client : redis.Redis
        Connected Redis client instance.
    name : str
        Name key identifying the distributed lock in Redis.
    expire : float | int | None
        Expiration lifetime of the lock in seconds. Default is 60.
    """

    def __init__(
        self,
        client: redis.Redis,
        name: str,
        expire: float | int | None = 60,
    ) -> None:
        self.client = client
        """Redis client connection."""
        self.name = name
        """Lock key name in Redis."""
        self.expire = expire
        """Expiration time in seconds."""
        self._lock = client.lock(name=name, timeout=expire)

    def acquire(self, blocking: bool = True, timeout: float | int = -1) -> bool:
        """Acquire the Redis distributed lock.

        Parameters
        ----------
        blocking : bool
            Whether to block until acquired. Default is True.
        timeout : float | int
            Blocking timeout in seconds. Default is -1.

        Returns
        -------
        bool
            True if acquired, False otherwise.
        """
        blocking_timeout: float | None = float(timeout) if timeout >= 0 else None
        return bool(
            self._lock.acquire(blocking=blocking, blocking_timeout=blocking_timeout)
        )

    def release(self) -> None:
        """Release the Redis lock if held by current worker."""
        if self._lock.locked():
            try:
                self._lock.release()
            except redis.exceptions.LockNotOwnedError:
                pass

    def is_locked(self) -> bool:
        """Check if the Redis lock is held.

        Returns
        -------
        bool
            True if lock key is currently active in Redis.
        """
        return self._lock.locked()


def get_migration_lock(
    name: str = "lunchmoney_migration",
    path: str = ".lunchmoney_migration.lock",
    timeout: float | int = 0,
) -> Lock:
    """Construct a migration lock instance appropriate for runtime environment.

    Uses Redis if redis_url is configured in environment or Settings,
    otherwise defaults to LockFile.

    Parameters
    ----------
    name : str
        Name key for Redis distributed lock. Default is 'lunchmoney_migration'.
    path : str
        File system path for fallback LockFile. Default is '.lunchmoney_migration.lock'.
    timeout : float | int
        Acquisition timeout in seconds. Default is 0.

    Returns
    -------
    Lock
        Instantiated Redis or LockFile instance.
    """
    from lunchmoney_mcp.config import SecretSettings

    redis_url = SecretSettings().redis_url
    if redis_url:
        client = redis.Redis.from_url(redis_url)
        return Redis(client=client, name=name)
    return LockFile(path=path, timeout=timeout)


FileLock = LockFile
# Alias for LockFile.
RedisLock = Redis
# Alias for Redis.

__all__ = [
    "FileLock",
    "Lock",
    "LockError",
    "LockFile",
    "LockTimeoutError",
    "Redis",
    "RedisLock",
    "get_migration_lock",
]
