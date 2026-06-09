"""Domain error hierarchy for helpdesk-ai.

All errors that bubble up through the API layer must be one of these classes.
Generic Python exceptions must never be re-raised to FastAPI handlers.
"""


class HelpdeskError(Exception):
    """Base class for all domain errors."""

    http_status: int = 500
    code: str = "internal_error"

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class AuthError(HelpdeskError):
    http_status = 401
    code = "auth_error"


class ForbiddenError(HelpdeskError):
    http_status = 403
    code = "forbidden"


class NotFoundError(HelpdeskError):
    http_status = 404
    code = "not_found"


class ConflictError(HelpdeskError):
    http_status = 409
    code = "conflict"


class ValidationError(HelpdeskError):
    http_status = 422
    code = "validation_error"


class RateLimitError(HelpdeskError):
    http_status = 429
    code = "rate_limit"


class LLMError(HelpdeskError):
    http_status = 502
    code = "llm_error"
