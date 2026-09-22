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


class Conflict(AppError):
    """Raised when a request can't be completed because of the resource's
    current state, distinct from InvalidTransition (which is specifically
    about a Quote/Invoice's own status field) - e.g. deleting a Registrar
    that's still referenced by at least one Domain (see RegistrarService)."""
