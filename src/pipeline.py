"""ApiForge tool pipelines.

Chain multiple functions into a sequential pipeline where each step's
output becomes the next step's input.

Usage:
    forge = ApiForge(name="Pipeline Demo")

    def clean(text: str) -> str:
        return text.strip().lower()

    def shout(text: str) -> str:
        return text.upper() + "!"

    @forge.pipeline(steps=[clean, shout])
    def transform(text: str) -> str:
        '''Transform text through clean → shout.'''
        ...  # body signature is used for the request schema

    # POST /tools/transform {"text": "  hello  "} → "HELLO!"
"""

from __future__ import annotations

import inspect
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src._internal import build_request_model
from src.errors import handle_tool_exception
from src.response import elapsed_ms, measure_start, wrap_response


class Pipeline:
    """A sequential chain of processing steps.

    Args:
        steps: List of sync or async callables. Each takes one arg, returns one value.
        name: Pipeline name (for error reporting).
    """

    def __init__(self, steps: list[Callable], name: str = "pipeline") -> None:
        if not steps:
            raise ValueError("Pipeline requires at least one step")
        self.steps = steps
        self.name = name

    async def execute(self, data: Any) -> Any:
        """Run data through all steps sequentially.

        Args:
            data: Input to the first step.

        Returns:
            Output of the last step.

        Raises:
            Exception: Propagated from any failing step.
        """
        for step in self.steps:
            result = step(data)
            if inspect.isawaitable(result):
                result = await result
            data = result
        return data

    def __len__(self) -> int:
        return len(self.steps)


def make_pipeline_handler(
    pipeline: Pipeline,
    input_model: type[BaseModel],
    input_key: str,
    tool_name: str,
    doc: str,
    envelope: bool = False,
) -> Callable:
    """Create a FastAPI handler that runs the pipeline.

    Args:
        pipeline: The Pipeline instance.
        input_model: Pydantic model for the request body.
        input_key: The body field name that feeds the pipeline.
        tool_name: Name for error reporting.
        doc: Docstring.
        envelope: Wrap result in response envelope.
    """

    async def handler(request: Request, payload: input_model) -> Any:  # noqa: ANN001
        request_id = request.headers.get("X-Request-ID")
        start = measure_start()
        try:
            result = await pipeline.execute(payload.model_dump()[input_key])
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
    handler.__annotations__ = {"request": Request, "payload": input_model, "return": Any}
    return handler


def build_pipeline_input_model(input_types: list[type] | None = None) -> type[BaseModel]:
    """Build a simple input model with a single 'input' field.

    Args:
        input_types: Accepted types (for documentation). Defaults to Any.

    Returns:
        A Pydantic model with one field: input.
    """
    from pydantic import create_model
    from typing import Any as _Any

    field_type = input_types[0] if input_types else _Any
    return create_model("PipelineInput", input=(field_type, ...))
