class DomainError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int = 400,
        code: str | None = None,
        extra: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code
        self.extra = extra or {}


class NotFoundError(DomainError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message, 404, code=code)


class ConflictError(DomainError):
    def __init__(self, message: str, code: str | None = None, extra: dict | None = None) -> None:
        super().__init__(message, 409, code=code, extra=extra)


class ValidationConflictError(DomainError):
    def __init__(self, message: str, code: str | None = None, extra: dict | None = None) -> None:
        super().__init__(message, 422, code=code, extra=extra)


class ForbiddenError(DomainError):
    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message, 403, code=code)


class RateLimitError(DomainError):
    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message, 429, code="RATE_LIMITED", extra={"retry_after": retry_after})
