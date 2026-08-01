"""Portable datetime storage helpers that retain source API shape."""

from datetime import datetime, timedelta, timezone
from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


UTC = timezone.utc
# Canonical UTC timezone compatible with all supported Python versions.


def datetime_offset_minutes(value: datetime | None) -> int | None:
    """Return the source UTC offset, using ``None`` for naive datetimes."""
    if value is None or value.tzinfo is None:
        return None
    offset = value.utcoffset()
    if offset is None:
        return None
    return int(offset.total_seconds() / 60)


def restore_datetime_shape(
    value: datetime | None,
    *,
    offset_minutes: int | None,
) -> datetime | None:
    """Restore a generated model's naive or offset-aware datetime shape."""
    if value is None:
        return None
    if offset_minutes is None:
        return value.replace(tzinfo=None)
    return value.astimezone(timezone(timedelta(minutes=offset_minutes)))


class UTCDateTime(TypeDecorator[datetime]):
    """Store native timestamps in UTC across SQLite and PostgreSQL."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        """Normalize values to UTC for native database storage and querying."""
        del dialect
        if value is None:
            return value
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(
        self,
        value: datetime | None,
        dialect: Dialect,
    ) -> datetime | None:
        """Restore the UTC marker omitted by SQLite's datetime adapter."""
        del dialect
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
