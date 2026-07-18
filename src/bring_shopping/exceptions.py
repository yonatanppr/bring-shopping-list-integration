"""Application-specific exceptions with safe, operator-facing messages."""


class BringIntegrationError(Exception):
    """Base class for errors raised before calling or interpreting Bring."""


class ConfigurationError(BringIntegrationError):
    """Raised when required environment configuration is invalid."""


class ListSelectionError(BringIntegrationError):
    """Raised when a shopping list cannot be selected unambiguously."""


class InvalidItemError(BringIntegrationError):
    """Raised when an item mutation has invalid input."""


class ItemSelectionError(BringIntegrationError):
    """Raised when an item cannot be selected unambiguously."""
