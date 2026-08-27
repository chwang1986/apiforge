"""ApiForge core server module.

Provides the ApiForge class for quickly creating and running API tool services.
"""

from __future__ import annotations

from typing import Any, Callable

import uvicorn
from fastapi import FastAPI

from src._internal import (
    build_body_model,
    build_request_model,
    extract_path_params,
    is_streaming_tool,
    is_upload_tool,
    make_get_handler,
    make_handler,
    make_path_handler,
    make_streaming_handler,
    make_upload_handler,
)
from src._version import __version__
from src.errors import register_http_error_handlers, ToolError, ValidationError
from src.health import HealthRegistry, install_health_checks
from src.middleware.auth import enable_api_key_auth
from src.middleware.cors import enable_cors
from src.middleware.logging import enable_request_logging
from src.middleware.rate_limit import enable_rate_limiting
from src.middleware.compression import enable_compression
from src.middleware.request_id import enable_request_id
from src.middleware.size_limit import enable_size_limit
from src.middleware.security import enable_security_headers


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
        envelope: bool = False,
        log_requests: bool = False,
        cors_origins: list[str] | None = None,
        rate_limit: dict[str, int] | None = None,
        api_keys: dict[str, str] | None = None,
        max_body_bytes: int | None = None,
        compress: bool = False,
        security_headers: bool = False,
    ) -> None:
        self.name = name
        self.description = description
        self.version = version
        self.envelope = envelope
        self.log_requests = log_requests
        self.rate_limit = rate_limit
        self.app: FastAPI = self._create_app()
        self._register_health_endpoint()
        register_http_error_handlers(self.app)
        self.health_registry = HealthRegistry()
        if self.log_requests:
            enable_request_logging(self.app)
        if cors_origins is not None:
            enable_cors(self.app, origins=cors_origins)
        if rate_limit is not None:
            enable_rate_limiting(
                self.app,
                requests_per_window=rate_limit.get("requests", 100),
                window_seconds=rate_limit.get("window_seconds", 60),
            )
        if api_keys is not None:
            enable_api_key_auth(self.app, api_keys=api_keys)
        enable_request_id(self.app)
        if max_body_bytes is not None:
            enable_size_limit(self.app, max_bytes=max_body_bytes)
        if compress:
            enable_compression(self.app)
        if security_headers:
            enable_security_headers(self.app)
        install_health_checks(self.app, self.health_registry)

    def health_check(self, name: str) -> Callable:
        """Decorator to register a dependency health check.

        Usage:
            forge = ApiForge(name="MyService")

            @forge.health_check("database")
            async def check_db():
                await db.execute("SELECT 1")

        Check results appear at GET /health/detail
        """
        return self.health_registry.check(name)

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

    def tool(
        self,
        func: Callable | None = None,
        *,
        method: str = "POST",
        path: str | None = None,
    ) -> Callable:
        """Decorator to register a function as an API tool endpoint.

        Args:
            func: The tool function to register (or None for parameterized use).
            method: HTTP method ("POST" or "GET").
            path: Custom URL path. Use {param} for path parameters.
                  e.g. path="/tools/users/{user_id}"

        Usage:
            @forge.tool
            def add(a: int, b: int) -> int: ...

            @forge.tool(method="GET")
            def search(query: str, limit: int = 10) -> list: ...

            @forge.tool(method="GET", path="/tools/users/{user_id}")
            def get_user(user_id: int) -> dict: ...
        """
        def register(f: Callable) -> Callable:
            tool_name = f.__name__
            route_path = path or f"/tools/{tool_name}"
            doc = (f.__doc__ or tool_name).strip().split("\n")[0]
            path_params = extract_path_params(route_path)

            if is_upload_tool(f):
                # File upload: register the function directly (FastAPI handles UploadFile)
                handler = f
            elif is_streaming_tool(f):
                # Streaming (SSE) tool
                request_model = build_request_model(f)
                handler = make_streaming_handler(request_model, f, tool_name, doc)
            elif path_params:
                # Path parameter tool
                body_model = build_body_model(f, path_params=path_params)
                handler = make_path_handler(
                    body_model, f, tool_name, doc,
                    path_params=path_params,
                    is_get=(method.upper() == "GET"),
                    envelope=self.envelope,
                )
            elif method.upper() == "GET":
                request_model = build_request_model(f)
                handler = make_get_handler(request_model, f, tool_name, doc, envelope=self.envelope)
            else:
                request_model = build_request_model(f)
                handler = make_handler(request_model, f, tool_name, doc, envelope=self.envelope)

            self.app.add_api_route(
                path=route_path,
                endpoint=handler,
                methods=[method.upper()],
                name=tool_name,
                description=doc,
                tags=["tools"],
            )
            return f

        if func is not None:
            return register(func)
        return register

    def ws(self, func: Callable | None = None, *, path: str | None = None) -> Callable:
        """Decorator to register a function as a WebSocket endpoint.

        Args:
            func: The WebSocket handler function (receives WebSocket as first arg).
            path: Custom URL path. Default: /ws/{func_name}

        Usage:
            @forge.ws
            async def chat(websocket: WebSocket):
                await websocket.accept()
                data = await websocket.receive_text()
                await websocket.send_text(f"Echo: {data}")
        """
        def register(f: Callable) -> Callable:
            tool_name = f.__name__
            route_path = path or f"/ws/{tool_name}"
            self.app.websocket(route_path)(f)
            return f

        if func is not None:
            return register(func)
        return register

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
