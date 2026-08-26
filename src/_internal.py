"""Shared internal utilities for ApiForge.

Contains the request-model builder and handler factory used by both
server.py and router.py to avoid code duplication.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, get_type_hints

from pydantic import BaseModel, create_model


def build_request_model(func: Callable) -> type[BaseModel]:
    """Dynamically create a Pydantic model from function signature.

    Args:
        func: The tool function to inspect.

    Returns:
        A Pydantic BaseModel class with fields matching the function params.
    """
    hints = get_type_hints(func)
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


def make_handler(model_cls: type[BaseModel], tool_func: Callable, tool_name: str, doc: str) -> Callable:
    """Create an async FastAPI handler that dispatches to *tool_func*.

    Supports both sync and async tool functions.
    """

    async def handler(payload: model_cls) -> Any:  # noqa: ANN001
        result = tool_func(**payload.model_dump())
        if inspect.isawaitable(result):
            result = await result
        return result

    handler.__name__ = tool_name
    handler.__doc__ = doc
    handler.__annotations__ = {"payload": model_cls, "return": Any}
    return handler
