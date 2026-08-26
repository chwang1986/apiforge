"""ApiForge routing utilities.

Provides helper functions for organizing tool routes into groups.
Use this for advanced routing scenarios beyond the basic @forge.tool decorator.
"""

from __future__ import annotations

import inspect
from typing import Any, Callable, get_type_hints

from fastapi import APIRouter
from pydantic import BaseModel, create_model


def create_tool_router(
    prefix: str = "/tools",
    tags: list[str] | None = None,
) -> APIRouter:
    """Create a dedicated APIRouter for tool endpoints.

    Args:
        prefix: URL prefix for the router.
        tags: OpenAPI tags for grouping in docs.

    Returns:
        A configured APIRouter instance.
    """
    return APIRouter(prefix=prefix, tags=tags or ["tools"])


def _build_request_model(func: Callable) -> type[BaseModel]:
    """Dynamically create a Pydantic model from function signature."""
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


def register_tool(
    router: APIRouter,
    func: Callable,
    path: str | None = None,
    tags: list[str] | None = None,
) -> Callable:
    """Register a function as a POST endpoint on the given router.

    Builds a Pydantic request model from the function's type hints,
    consistent with the @forge.tool decorator behavior.

    Args:
        router: The target APIRouter.
        func: The tool function (must have type hints on parameters).
        path: Override path (defaults to /{func.__name__}).
        tags: OpenAPI tags for this endpoint.

    Returns:
        The original function (unmodified).
    """
    endpoint_path = path or f"/{func.__name__}"
    doc = func.__doc__ or func.__name__
    request_model = _build_request_model(func)

    def _make_handler(model_cls: type[BaseModel], tool_func: Callable) -> Callable:
        async def handler(payload: model_cls) -> Any:  # noqa: ANN001
            return tool_func(**payload.model_dump())

        handler.__name__ = func.__name__
        handler.__doc__ = doc
        handler.__annotations__ = {"payload": model_cls, "return": Any}
        return handler

    handler = _make_handler(request_model, func)

    router.add_api_route(
        path=endpoint_path,
        endpoint=handler,
        methods=["POST"],
        name=func.__name__,
        description=doc,
        tags=tags or ["tools"],
    )
    return func
