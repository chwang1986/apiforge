"""ApiForge request/response transformers.

Apply before/after transforms to tool inputs and outputs without
modifying the tool function itself.

Usage:
    def uppercase_params(kwargs: dict) -> dict:
        '''Uppercase all string params.'''
        return {k: v.upper() if isinstance(v, str) else v for k, v in kwargs.items()}

    def wrap_response(result: Any) -> dict:
        '''Wrap result in standard dict.'''
        return {"value": result}

    @forge.tool(before=uppercase_params, after=wrap_response)
    def process(text: str) -> str:
        '''Process text.'''
        return text.strip()

    # POST /tools/process {"text": "  hello  "}
    # 1. before transforms: {"text": "  HELLO  "}
    # 2. tool runs: "HELLO"
    # 3. after transforms: {"value": "HELLO"}
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable


def wrap_tool(
    func: Callable,
    before: Callable | None = None,
    after: Callable | None = None,
) -> Callable:
    """Wrap a tool function with before/after transforms.

    Args:
        func: The original tool function.
        before: Transform applied to kwargs before calling func.
               Signature: (kwargs: dict) -> dict
        after: Transform applied to result after calling func.
               Signature: (result: Any) -> Any

    Returns:
        A new function with the same signature as func.
    """
    if before is None and after is None:
        return func

    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapped(*args, **kwargs):
            if before is not None:
                kwargs = before(kwargs)
            result = await func(*args, **kwargs)
            if after is not None:
                result = after(result)
                if inspect.isawaitable(result):
                    result = await result
            return result
        return async_wrapped
    else:
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            if before is not None:
                kwargs = before(kwargs)
            result = func(*args, **kwargs)
            if after is not None:
                result = after(result)
                if inspect.isawaitable(result):
                    import asyncio
                    result = asyncio.get_event_loop().run_until_complete(result)
            return result
        return wrapped


def to_upper(kwargs: dict) -> dict:
    """Builtin: uppercase all string values in kwargs."""
    return {k: v.upper() if isinstance(v, str) else v for k, v in kwargs.items()}


def to_lower(kwargs: dict) -> dict:
    """Builtin: lowercase all string values in kwargs."""
    return {k: v.lower() if isinstance(v, str) else v for k, v in kwargs.items()}


def strip_strings(kwargs: dict) -> dict:
    """Builtin: strip whitespace from all string values."""
    return {k: v.strip() if isinstance(v, str) else v for k, v in kwargs.items()}


def wrap_in_key(key: str) -> Callable:
    """Builtin factory: wrap result in {"key": result}."""
    def transform(result: Any) -> dict:
        return {key: result}
    return transform


def identity(x: Any) -> Any:
    """Identity transform (no-op, for testing)."""
    return x
