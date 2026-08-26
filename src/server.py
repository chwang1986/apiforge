"""ApiForge core server module.

Provides the ApiForge class for quickly creating and running API tool services.
"""

from __future__ import annotations

from typing import Any, Callable

import uvicorn
from fastapi import FastAPI

from src._internal import build_request_model, make_handler
from src._version import __version__
from src.errors import register_http_error_handlers, ToolError, ValidationError


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
        register_http_error_handlers(self.app)

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

    def tool(self, func: Callable) -> Callable:
        """Decorator to register a function as an API tool endpoint.

        Automatically builds a request schema from the function's type hints.
        Supports both sync and async tool functions.

        Args:
            func: The tool function to register.

        Returns:
            The original function (unmodified).
        """
        tool_name = func.__name__
        path = f"/tools/{tool_name}"
        doc = (func.__doc__ or tool_name).strip().split("\n")[0]
        request_model = build_request_model(func)
        handler = make_handler(request_model, func, tool_name, doc)

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
