"""ApiForge routing utilities.

Provides helper functions for organizing tool routes into groups.
Use this for advanced routing scenarios beyond the basic @forge.tool decorator.
"""

from __future__ import annotations

from typing import Any, Callable

from fastapi import APIRouter

from src._internal import build_request_model, make_handler


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


def register_tool(
    router: APIRouter,
    func: Callable,
    path: str | None = None,
    tags: list[str] | None = None,
) -> Callable:
    """Register a function as a POST endpoint on the given router.

    Builds a Pydantic request model from the function's type hints,
    consistent with the @forge.tool decorator behavior.
    Supports both sync and async tool functions.

    Args:
        router: The target APIRouter.
        func: The tool function (must have type hints on parameters).
        path: Override path (defaults to /{func.__name__}).
        tags: OpenAPI tags for this endpoint.

    Returns:
        The original function (unmodified).
    """
    endpoint_path = path or f"/{func.__name__}"
    doc = (func.__doc__ or func.__name__).strip().split("\n")[0]
    request_model = build_request_model(func)
    handler = make_handler(request_model, func, func.__name__, doc)

    router.add_api_route(
        path=endpoint_path,
        endpoint=handler,
        methods=["POST"],
        name=func.__name__,
        description=doc,
        tags=tags or ["tools"],
    )
    return func
