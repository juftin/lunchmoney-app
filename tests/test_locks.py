"""Tests for process and distributed lock abstractions."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from lunchmoney_app.locks import (
    FileLock,
    Lock,
    LockFile,
    LockTimeoutError,
    Redis,
    RedisLock,
    get_migration_lock,
)


def test_lock_abc_subclassing() -> None:
    """Verify Lock is an abstract base class that cannot be instantiated directly."""
    with pytest.raises(TypeError):
        Lock()  # type: ignore[abstract]


def test_lock_file_acquire_release(tmp_path: Path) -> None:
    """Acquire and release a file lock using context manager and explicit methods."""
    lock_path = str(tmp_path / "test.lock")
    lock1 = LockFile(lock_path)

    assert not lock1.is_locked()
    with lock1:
        assert lock1.is_locked()

    assert not lock1.is_locked()


def test_lock_file_contention(tmp_path: Path) -> None:
    """Raise LockTimeoutError when attempting to acquire a held file lock."""
    lock_path = str(tmp_path / "contention.lock")
    lock1 = LockFile(lock_path, timeout=0)
    lock2 = FileLock(lock_path, timeout=0)

    assert lock1.acquire()
    assert lock1.is_locked()

    assert not lock2.acquire(blocking=False)
    with pytest.raises(LockTimeoutError):
        with lock2:
            pass

    lock1.release()
    assert not lock1.is_locked()
    assert lock2.acquire()
    lock2.release()


def test_redis_lock_acquire_release() -> None:
    """Acquire and release a Redis lock using mocked Redis client."""
    mock_redis = MagicMock()
    mock_inner_lock = MagicMock()
    mock_inner_lock.acquire.return_value = True
    mock_inner_lock.locked.return_value = True
    mock_redis.lock.return_value = mock_inner_lock

    lock = Redis(client=mock_redis, name="migration_lock", expire=30)
    assert lock.acquire() is True
    assert lock.is_locked() is True

    lock.release()
    mock_inner_lock.release.assert_called_once()


def test_redis_lock_renews_owned_lease() -> None:
    """Extend the owned Redis lease before its expiration can permit overlap."""
    mock_redis = MagicMock()
    mock_inner_lock = MagicMock()
    mock_inner_lock.extend.return_value = True
    mock_redis.lock.return_value = mock_inner_lock

    lock = Redis(client=mock_redis, name="long_sync", expire=60)

    mock_redis.lock.assert_called_once_with(
        name="long_sync", timeout=60, thread_local=False
    )
    assert lock.renewal_interval == 20
    assert lock.renew() is True
    mock_inner_lock.extend.assert_called_once_with(60, replace_ttl=True)


def test_redis_lock_reports_lost_lease() -> None:
    """Report ownership loss when Redis rejects renewal after lease expiry."""
    mock_redis = MagicMock()
    mock_inner_lock = MagicMock()
    mock_inner_lock.extend.side_effect = __import__(
        "redis"
    ).exceptions.LockNotOwnedError
    mock_redis.lock.return_value = mock_inner_lock

    lock = Redis(client=mock_redis, name="expired_sync")

    assert lock.renew() is False


def test_redis_lock_contention() -> None:
    """Raise LockTimeoutError when Redis lock acquisition fails."""
    mock_redis = MagicMock()
    mock_inner_lock = MagicMock()
    mock_inner_lock.acquire.return_value = False
    mock_redis.lock.return_value = mock_inner_lock

    lock = RedisLock(client=mock_redis, name="contended_lock")
    assert not lock.acquire(blocking=False)

    with pytest.raises(LockTimeoutError):
        with lock:
            pass


def test_get_migration_lock_default_file_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Return LockFile instance when LUNCHMONEY_REDIS_URL is not set."""
    monkeypatch.delenv("LUNCHMONEY_REDIS_URL", raising=False)

    lock = get_migration_lock()
    assert isinstance(lock, LockFile)


def test_get_migration_lock_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return Redis lock instance when LUNCHMONEY_REDIS_URL is set."""
    import redis

    monkeypatch.setenv("LUNCHMONEY_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(redis.Redis, "from_url", lambda url: MagicMock())

    lock = get_migration_lock()
    assert isinstance(lock, Redis)
