"""Application error types and error handler re-exporting platform_api.contracts.errors."""

from typing import Any, cast

from fastapi import Request
from fastapi.responses import JSONResponse

from platform_api.contracts.errors import ErrorCode, ErrorDetail


class ApplicationError(Exception):
    def __init__(
        self,
        code: str | ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.message = message
        self.details = details or {}


async def application_error_handler(request: Request, exc: Exception) -> JSONResponse:
    error = cast(ApplicationError, exc)
    request_id = getattr(request.state, "request_id", "unknown")
    fallback = ErrorCode.INTERNAL_FAILURE
    err_code = ErrorCode(error.code) if error.code in ErrorCode._value2member_map_ else fallback
    detail = ErrorDetail(
        code=err_code,
        message=error.message,
        details=error.details,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=400,
        content={"error": detail.model_dump(mode="json")},
    )


__all__ = ["ApplicationError", "ErrorCode", "ErrorDetail", "application_error_handler"]
