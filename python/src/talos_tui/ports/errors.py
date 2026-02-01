"""TUI Errors."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional

ErrorKind = Literal[
    "NETWORK",
    "TIMEOUT",
    "AUTH",
    "INCOMPATIBLE",
    "BAD_RESPONSE",
    "PAYLOAD_TOO_LARGE",
    "CANCELLED",
    "NOT_READY",
    "CONTRACT",
    "RATE_LIMIT",
    "UNKNOWN",
]


@dataclass(frozen=True)
class TuiError(Exception):
    """Base class for TUI-specific errors."""

    kind: ErrorKind
    message: str
    status_code: Optional[int] = None
    retryable: bool = False
    detail: Optional[str] = None

    def __str__(self) -> str:
        base = f"[{self.kind}] {self.message}"
        if self.status_code is not None:
            base += f" (status={self.status_code})"
        return base
