"""ApiForge unified error handling.

Provides structured error responses for tool execution failures,
validation errors, and HTTP-level errors (404, 405).

Error response format:
    {
        "error": {
            "code": "TOOL_EXECUTION_FAILED",
            "message": "Something went wrong",
            "tool": "add",
            "request_id": "abc-123"
        }
    }
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

# --- Error codes ---

ERR_TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
ERR_VALIDATION_FAILED = "VALIDATION_FAILED"
ERR_NOT_FOUND = "NOT_FOUND"
ERR_METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
ERR_INTERNAL = "INTERNAL_ERROR"


class ToolError(Exception):
    """Base exception for ApiForge tool errors.

    Users can raise this in their tool functions to control
    the error response code and message.

    Usage:
        @forge.tool
        def divide(a: float, b: float) -> float:
            if b == 0:
                raise ToolError("Division by zero", code="DIVISION_BY_ZERO")
            return a / b
    """

    def __init__(
        self,
        message: str = "Tool execution failed",
        code: str = ERR_TOOL_EXECUTION_FAILED,
        status_code: int = 400,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class ValidationError(ToolError):
    """Raised when input validation fails in a custom way."""

    def __init__(self, message: str = "Validation failed", field: str | None = None) -> None:
        self.field = field
        super().__init__(message=message, code=ERR_VALIDATION_FAILED, status_code=422)


def make_error_response(
    code: str,
    message: str,
    status_code: int = 500,
    tool: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a structured error dict."""
    error: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if tool:
        error["tool"] = tool
    if request_id:
        error["request_id"] = request_id
    return {"error": error}


def handle_tool_exception(exc: Exception, tool_name: str | None = None, request_id: str | None = None) -> tuple[int, dict[str, Any]]:
    """Convert an exception to (status_code, error_dict) for the handler wrapper."""
    if isinstance(exc, ToolError):
        return exc.status_code, make_error_response(exc.code, exc.message, exc.status_code, tool_name, request_id)

    # Generic unhandled exception
    return 500, make_error_response(ERR_INTERNAL, str(exc), 500, tool_name, request_id)


def register_http_error_handlers(app: FastAPI) -> None:
    """Register handlers for HTTP-level errors (404, 405, etc.).

    These are raised by the router before reaching our handler,
    so we need exception handlers (not try/except in handler).
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Reformat standard HTTP errors into our envelope."""
        if exc.status_code == 404:
            code = ERR_NOT_FOUND
        elif exc.status_code == 405:
            code = ERR_METHOD_NOT_ALLOWED
        else:
            code = "HTTP_ERROR"

        return JSONResponse(
            status_code=exc.status_code,
            content=make_error_response(code, str(exc.detail), exc.status_code),
        )
