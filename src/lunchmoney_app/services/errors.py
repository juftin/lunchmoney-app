"""Transport-neutral service errors."""


class StatefulModeRequired(RuntimeError):
    """Signal that an operation requires durable application state."""

    code = "stateful_mode_required"
    """Stable machine-readable error code."""

    message = "This operation requires stateful persistence mode."
    """Safe user-facing error message."""

    def __init__(self) -> None:
        """Initialize the error with its stable public message."""
        super().__init__(self.message)

    def as_dict(self) -> dict[str, str]:
        """Return the stable transport-neutral error payload."""
        return {"code": self.code, "message": self.message}


__all__ = ["StatefulModeRequired"]
