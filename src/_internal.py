"""Shared internal utilities for ApiForge.

Contains the request-model builder and handler factory used by both
server.py and router.py to avoid code duplication.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, get_type_hints

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, create_model

from src.errors import ERR_VALIDATION_FAILED, ToolError, handle_tool_exception


def build_request_model(func: Callable) -> type[BaseModel]:
    """Dynamically create a Pydantic model from function signature.

    Args:
        func: The tool function to inspect.

    Returns:
        A Pydantic BaseModel class with fields matching the function params.
    """
    hints = get_type_hints(func, include_extras=True)
    sig = inspect.signature(func)

    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue
        field_type = hints.get(param_name, Any)
        if param.default is inspect.Parameter.empty:
            fields[param_name] = (field_type, ...)
        else:
            fields[param_name] = (field_type, param.default)

    model_name = f"{func.__name__.capitalize()}Request"
    return create_model(model_name, **fields)


def make_handler(
    model_cls: type[BaseModel],
    tool_func: Callable,
    tool_name: str,
    doc: str,
) -> Callable:
    """Create an async FastAPI handler that dispatches to *tool_func*.

    Supports both sync and async tool functions.
    Catches exceptions and returns structured error responses.
    """

    async def handler(request: Request, payload: model_cls) -> Any:  # noqa: ANN001
        request_id = request.headers.get("X-Request-ID")
        try:
            result = tool_func(**payload.model_dump())
            if inspect.isawaitable(result):
                result = await result
            return result
        except Exception as exc:
            status_code, error_body = handle_tool_exception(exc, tool_name, request_id)
            return JSONResponse(status_code=status_code, content=error_body)

    handler.__name__ = tool_name
    handler.__doc__ = doc
    handler.__annotations__ = {"request": Request, "payload": model_cls, "return": Any}
    return handler
