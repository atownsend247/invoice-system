class AppError(Exception):
    """Base for every error a core service raises."""


class NotFound(AppError):
    pass


class ValidationFailed(AppError):
    pass


class Duplicate(AppError):
    pass


class InvalidTransition(AppError):
    """Raised when an entity's status can't move the requested way."""
