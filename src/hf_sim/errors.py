"""Shared exception types for HF_Sim."""


class HFSimError(Exception):
    """Base exception for simulator errors."""


class IntegrationError(HFSimError):
    """Raised when an IF-level contract cannot be satisfied."""

