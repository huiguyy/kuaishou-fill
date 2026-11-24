"""Actionable, JSON-safe errors shared by both skills."""
from __future__ import annotations


class FillError(Exception):
    """An expected failure that can be returned without a traceback."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = 4,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code
        self.retryable = retryable

    def as_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
        }


def clean_error_message(exc: BaseException, *, limit: int = 500) -> str:
    """Keep diagnostics useful without dumping multiline pages or traces."""
    text = " ".join(str(exc).split())
    if not text:
        text = exc.__class__.__name__
    return text[:limit]
