class OnchainError(Exception):
    """Base onchain domain error."""


class OnchainConfigurationError(OnchainError):
    """Raised when provider configuration is invalid."""


class OnchainStateError(OnchainError):
    """Raised when requested wallet state is invalid."""
