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


from src.response import elapsed_ms, measure_start, wrap_response


def make_handler(
    model_cls: type[BaseModel],
    tool_func: Callable,
    tool_name: str,
    doc: str,
    envelope: bool = False,
) -> Callable:
    """Create an async FastAPI handler that dispatches to *tool_func*.

    Supports both sync and async tool functions.
    Catches exceptions and returns structured error responses.
    Optionally wraps success responses in a standard envelope.
    """

    async def handler(request: Request, payload: model_cls) -> Any:  # noqa: ANN001
        request_id = request.headers.get("X-Request-ID")
        start = measure_start()
        try:
            result = tool_func(**payload.model_dump())
            if inspect.isawaitable(result):
                result = await result
            if envelope:
                return wrap_response(
                    data=result,
                    tool=tool_name,
                    request_id=request_id,
                    elapsed_ms=elapsed_ms(start),
                )
            return result
        except Exception as exc:
            status_code, error_body = handle_tool_exception(exc, tool_name, request_id)
            return JSONResponse(status_code=status_code, content=error_body)

    handler.__name__ = tool_name
    handler.__doc__ = doc
    handler.__annotations__ = {"request": Request, "payload": model_cls, "return": Any}
    return handler


def _coerce_value(raw: str, field_type: Any) -> Any:
    """Coerce a raw string value to the target type (query or path)."""
    if field_type is int:
        return int(raw)
    if field_type is float:
        return float(raw)
    if field_type is bool:
        return raw.lower() in ("1", "true", "yes", "on")
    return raw


def extract_path_params(path: str) -> list[str]:
    """Extract parameter names from a path template.

    e.g. "/tools/users/{user_id}/posts/{post_id}" → ["user_id", "post_id"]
    """
    import re
    return re.findall(r"\{(\w+)\}", path)


def build_body_model(func: Callable, path_params: list[str] | None = None) -> type[BaseModel]:
    """Build a Pydantic model excluding path parameters.

    Args:
        func: The tool function.
        path_params: Parameter names that are in the URL path (excluded from body).

    Returns:
        Pydantic model with only non-path fields.
    """
    hints = get_type_hints(func, include_extras=True)
    sig = inspect.signature(func)
    path_set = set(path_params or [])

    fields: dict[str, Any] = {}
    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls") or param_name in path_set:
            continue
        field_type = hints.get(param_name, Any)
        if param.default is inspect.Parameter.empty:
            fields[param_name] = (field_type, ...)
        else:
            fields[param_name] = (field_type, param.default)

    model_name = f"{func.__name__.capitalize()}Body"
    return create_model(model_name, **fields)


def make_path_handler(
    model_cls: type[BaseModel],
    tool_func: Callable,
    tool_name: str,
    doc: str,
    path_params: list[str],
    is_get: bool = False,
    envelope: bool = False,
) -> Callable:
    """Create a handler that reads params from URL path + body/query.

    Uses request.path_params (auto-populated by FastAPI from {param} in route).

    Args:
        model_cls: Pydantic model for non-path params (empty if all in path).
        tool_func: The tool function.
        tool_name: Tool name.
        doc: Docstring.
        path_params: Parameter names in the URL path.
        is_get: If True, non-path params come from query string.
        envelope: Wrap response in envelope.
    """
    fields = model_cls.model_fields if model_cls else {}

    async def handler(request: Request) -> Any:
        request_id = request.headers.get("X-Request-ID")
        start = measure_start()
        try:
            kwargs: dict[str, Any] = {}

            # 1) Path params (from request.path_params, auto-filled by FastAPI)
            for p in path_params:
                if p in request.path_params:
                    raw = request.path_params[p]
                    hints = get_type_hints(tool_func, include_extras=True)
                    field_type = hints.get(p, str)
                    kwargs[p] = _coerce_value(raw, field_type)

            # 2) Body or query params
            if is_get:
                for field_name, field_info in fields.items():
                    if field_name in request.query_params:
                        kwargs[field_name] = _coerce_value(
                            request.query_params[field_name], field_info.annotation
                        )
                    elif not field_info.is_required():
                        kwargs[field_name] = field_info.default
            else:
                # POST: read JSON body
                body = await request.json()
                for field_name, field_info in fields.items():
                    if field_name in body:
                        kwargs[field_name] = body[field_name]
                    elif not field_info.is_required():
                        kwargs[field_name] = field_info.default

            # 3) Call tool
            result = tool_func(**kwargs)
            if inspect.isawaitable(result):
                result = await result

            if envelope:
                return wrap_response(
                    data=result, tool=tool_name,
                    request_id=request_id, elapsed_ms=elapsed_ms(start),
                )
            return result

        except Exception as exc:
            status_code, error_body = handle_tool_exception(exc, tool_name, request_id)
            return JSONResponse(status_code=status_code, content=error_body)

    handler.__name__ = tool_name
    handler.__doc__ = doc
    handler.__annotations__ = {"request": Request, "return": Any}
    return handler


def make_get_handler(
    model_cls: type[BaseModel],
    tool_func: Callable,
    tool_name: str,
    doc: str,
    envelope: bool = False,
) -> Callable:
    """Create a GET handler where parameters come from query string."""
    fields = model_cls.model_fields

    async def handler(request: Request) -> Any:
        request_id = request.headers.get("X-Request-ID")
        start = measure_start()
        try:
            kwargs: dict[str, Any] = {}
            for field_name, field_info in fields.items():
                if field_name in request.query_params:
                    kwargs[field_name] = _coerce_value(
                        request.query_params[field_name], field_info.annotation
                    )
                elif not field_info.is_required():
                    kwargs[field_name] = field_info.default

            missing = [
                fn for fn, fi in fields.items()
                if fi.is_required() and fn not in request.query_params
            ]
            if missing:
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "VALIDATION_FAILED",
                            "message": f"Missing required query parameters: {', '.join(missing)}",
                            "tool": tool_name,
                            "request_id": request_id,
                        }
                    },
                )

            result = tool_func(**kwargs)
            if inspect.isawaitable(result):
                result = await result
            if envelope:
                return wrap_response(
                    data=result, tool=tool_name,
                    request_id=request_id, elapsed_ms=elapsed_ms(start),
                )
            return result
        except Exception as exc:
            status_code, error_body = handle_tool_exception(exc, tool_name, request_id)
            return JSONResponse(status_code=status_code, content=error_body)

    handler.__name__ = tool_name
    handler.__doc__ = doc
    return handler
