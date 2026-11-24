"""Domain errors that map to clean HTTP responses."""


class AppError(Exception):
    status_code = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class LLMError(AppError):
    """The upstream LLM provider failed after retries and fallback."""

    status_code = 502


class InvalidInputError(AppError):
    status_code = 422


class PayloadTooLargeError(AppError):
    status_code = 413
