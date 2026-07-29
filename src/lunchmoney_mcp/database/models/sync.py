"""SQLModel record for incremental synchronization watermarks."""

from builtins import type as builtin_type
from datetime import UTC, datetime
from typing import Any, ClassVar, cast

from sqlmodel import Field, SQLModel

from lunchmoney_mcp.database.models._datetime import UTCDateTime


class SyncMetadata(SQLModel, table=True):
    """Persist the latest successful synchronization time for one domain."""

    __tablename__: ClassVar[str] = "sync_metadata"

    domain: str = Field(primary_key=True)
    """Synchronization domain uniquely identified by this watermark."""
    last_synced_at: datetime = Field(sa_type=cast(builtin_type[Any], UTCDateTime()))
    """UTC timestamp of the domain's latest successful synchronization."""

    def model_post_init(self, context: Any, /) -> None:
        """Normalize synchronization watermarks after SQLModel construction."""
        del context
        if self.last_synced_at.tzinfo is None:
            self.last_synced_at = self.last_synced_at.replace(tzinfo=UTC)
        else:
            self.last_synced_at = self.last_synced_at.astimezone(UTC)
