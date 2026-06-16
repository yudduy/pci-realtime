"""Typed errors for agent-facing PCI service calls."""

from __future__ import annotations


class ServiceError(Exception):
    """Base class for clean service failures."""

    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    @property
    def code(self) -> str:
        return type(self).__name__


class BadRequest(ServiceError):
    """Invalid user or agent input."""

    exit_code = 9


class SupabaseUnavailable(ServiceError):
    """Registry credentials or connectivity are unavailable."""

    exit_code = 4


class UpstreamUnavailable(ServiceError):
    """An upstream registry/source dependency failed."""

    exit_code = 4


class UpstreamTimeout(ServiceError):
    """An upstream dependency exceeded its time budget."""

    exit_code = 5


class RateLimited(ServiceError):
    """An upstream dependency returned a rate limit."""

    exit_code = 6


class ScoringUnavailable(ServiceError):
    """Evidence could not be scored and therefore was not promoted."""

    exit_code = 7
