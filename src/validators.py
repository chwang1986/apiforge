"""ApiForge advanced parameter validation.

Provides user-friendly constraint types for tool function parameters.
Use with Annotated type hints in your tool signatures.

Usage:
    from typing import Annotated
    from src.validators import PositiveInt, EmailStr, LengthStr, RangeFloat

    @forge.tool
    def create_user(
        name: LengthStr(2, 50),
        age: PositiveInt,
        email: EmailStr,
        score: RangeFloat(0.0, 100.0),
    ) -> dict:
        '''Create a user with validated fields.'''
        return {"name": name, "age": age, "email": email, "score": score}
"""

from __future__ import annotations

import re
from typing import Annotated, Any, TypeVar

from pydantic import AfterValidator

T = TypeVar("T")


# ============================================================
# Internal validation helpers (defined BEFORE use)
# ============================================================

def _check_positive(value: Any, type_name: str) -> Any:
    if value <= 0:
        raise ValueError(f"Must be a positive {type_name} (got {value})")
    return value


def _check_non_negative(value: Any, type_name: str) -> Any:
    if value < 0:
        raise ValueError(f"Must be a non-negative {type_name} (got {value})")
    return value


def _check_length(value: str, min_len: int, max_len: int) -> str:
    length = len(value)
    if length < min_len or length > max_len:
        raise ValueError(f"String length must be between {min_len} and {max_len} (got {length})")
    return value


def _check_range(value: Any, min_val: Any, max_val: Any, type_name: str) -> Any:
    if value < min_val or value > max_val:
        raise ValueError(f"{type_name.capitalize()} must be between {min_val} and {max_val} (got {value})")
    return value


def _validate_email(value: str) -> str:
    pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    if not pattern.match(value):
        raise ValueError(f"Invalid email address: {value!r}")
    return value


def _validate_uuid(value: str) -> str:
    import uuid
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid UUID: {value!r}") from None
    return value


def _validate_url(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        raise ValueError(f"URL must start with http:// or https:// (got {value!r})")
    if " " in value:
        raise ValueError(f"URL must not contain spaces (got {value!r})")
    return value


def _check_pattern(value: str, compiled: re.Pattern, pattern: str) -> str:
    if not compiled.match(value):
        raise ValueError(f"String must match pattern {pattern!r} (got {value!r})")
    return value


def _check_one_of(value: Any, value_set: set, values: tuple) -> Any:
    if value not in value_set:
        raise ValueError(f"Must be one of {list(values)} (got {value!r})")
    return value


# ============================================================
# Pre-built constraint types (use directly as annotations)
# ============================================================

PositiveInt = Annotated[int, AfterValidator(lambda v: _check_positive(v, "int"))]
PositiveFloat = Annotated[float, AfterValidator(lambda v: _check_positive(v, "float"))]
NonNegativeInt = Annotated[int, AfterValidator(lambda v: _check_non_negative(v, "int"))]

EmailStr = Annotated[str, AfterValidator(_validate_email)]
UUIDStr = Annotated[str, AfterValidator(_validate_uuid)]
UrlStr = Annotated[str, AfterValidator(_validate_url)]


# ============================================================
# Factory functions for custom constraints
# ============================================================

def LengthStr(min_len: int = 1, max_len: int = 10_000) -> Any:
    """Create a string type constrained to [min_len, max_len] characters.

    Usage:
        name: LengthStr(2, 50)
    """
    return Annotated[
        str,
        AfterValidator(lambda v, _min=min_len, _max=max_len: _check_length(v, _min, _max)),
    ]


def RangeInt(min_val: int, max_val: int) -> Any:
    """Create an int type constrained to [min_val, max_val].

    Usage:
        port: RangeInt(1, 65535)
    """
    return Annotated[
        int,
        AfterValidator(lambda v, _min=min_val, _max=max_val: _check_range(v, _min, _max, "int")),
    ]


def RangeFloat(min_val: float, max_val: float) -> Any:
    """Create a float type constrained to [min_val, max_val].

    Usage:
        score: RangeFloat(0.0, 100.0)
    """
    return Annotated[
        float,
        AfterValidator(lambda v, _min=min_val, _max=max_val: _check_range(v, _min, _max, "float")),
    ]


def PatternStr(pattern: str, flags: int = 0) -> Any:
    """Create a string type that must fully match a regex pattern.

    Usage:
        code: PatternStr(r"^[A-Z]{3}-\\d{4}$")  # e.g. "ABC-1234"
    """
    compiled = re.compile(pattern, flags)
    return Annotated[
        str,
        AfterValidator(lambda v, _re=compiled, _pat=pattern: _check_pattern(v, _re, _pat)),
    ]


def OneOf(*values: Any) -> Any:
    """Create a type that must be one of the given values.

    Usage:
        status: OneOf("active", "inactive", "suspended")
        level: OneOf(1, 2, 3, 4, 5)
    """
    value_set = set(values)
    return Annotated[
        Any,
        AfterValidator(lambda v, _set=value_set, _vals=values: _check_one_of(v, _set, _vals)),
    ]
