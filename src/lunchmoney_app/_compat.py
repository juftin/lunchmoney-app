"""Compatibility helpers for supported Python runtimes."""

from enum import Enum


class StrEnum(str, Enum):
    """Provide the ``enum.StrEnum`` behavior needed by this project on Python 3.10."""

    def __str__(self) -> str:
        """Return the member value, matching Python's native ``StrEnum``."""
        return str(self.value)
