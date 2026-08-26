"""ApiForge core server module.

Provides the ApiForge class for quickly creating and running API tool services.
"""

import inspect
from typing import Any, Callable, get_type_hints

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel, create_model

from src import __version__


class ApiForge:
    """A lightweight wrapper around FastAPI for exposing tool APIs.

    Usage:
        forge = ApiForge(name="MyTools")

        @forge.tool
        def echo(message: str) -> str:
            '''Echo the input message back.'''
            return message

        forge.run(host="0.0.0.0", port=8000)
    """

    def __init__(
        self,
        name: str = "ApiForge",
        description: str = "API tool service",
        version: str = __version__,
    ) -> None:
        self.name = name
        self.description = description
        self.version = version
        self.app: FastAPI = self._create_app()
        self._register_health_endpoint()

    def _create_app(self) -> FastAPI:
        """Create and configure the FastAPI application."""
        app = FastAPI(
            title=self.name,
            description=self.description,
            version=self.version,
            openapi_url="/api/openapi.json",
            docs_url="/api/docs",
            redoc_url="/api/redoc",
        )
        return app

    def _register_health_endpoint(self) -> None:
        """Register the built-in health check endpoint."""

        @self.app.get("/health", tags=["system"])
        async def health() -> dict[str, str]:
            """Service health check."""
            return {
                "status": "ok",
                "service": self.name,
                "version": self.version,
            }

    def _build_request_model(self, func: Callable) -> type[BaseModel]:
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

    def tool(self, func: Callable) -> Callable:
        """Decorator to register a function as an API tool endpoint.

        Automatically builds a request schema from the function's type hints.

        Args:
            func: The tool function to register.

        Returns:
            The original function (unmodified).
        """
        tool_name = func.__name__
        path = f"/tools/{tool_name}"
        doc = func.__doc__ or tool_name
        request_model = self._build_request_model(func)

        def _make_handler(model_cls: type[BaseModel], tool_func: Callable) -> Callable:
            async def handler(payload: model_cls) -> Any:  # noqa: ANN001
                return tool_func(**payload.model_dump())

            handler.__name__ = tool_name
            handler.__doc__ = doc
            handler.__annotations__ = {"payload": model_cls, "return": Any}
            return handler

        handler = _make_handler(request_model, func)

        self.app.add_api_route(
            path=path,
            endpoint=handler,
            methods=["POST"],
            name=tool_name,
            description=doc,
            tags=["tools"],
        )
        return func

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        reload: bool = False,
    ) -> None:
        """Start the API server.

        Args:
            host: Bind address.
            port: Bind port.
            reload: Enable auto-reload (development only, requires string import path).
        """
        if reload:
            # reload 模式需要字符串导入路径，此处提示用户改用 uvicorn CLI
            raise ValueError(
                "reload=True 需要字符串导入路径。"
                "请使用: uvicorn src.server:app --reload"
            )
        uvicorn.run(
            self.app,
            host=host,
            port=port,
        )
