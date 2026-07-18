"""Private, capability-protected Streamable HTTP transport for MCP."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import secrets
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import anyio
import httpx
import uvicorn
from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.server.transport_security import TransportSecuritySettings
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from bring_shopping.exceptions import ConfigurationError
from bring_shopping.mcp_server import create_server
from bring_shopping.service import BringShoppingService

LOGGER = logging.getLogger("bring_shopping.http")
CAPABILITY_PATTERN = re.compile(r"[0-9a-f]{64}")
DEFAULT_MAX_BODY_BYTES = 1_048_576
DEFAULT_RATE_PER_MINUTE = 120
DEFAULT_RATE_BURST = 30
DEFAULT_MAX_CONCURRENCY = 4


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environ.get(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ConfigurationError(f"{name} must be an integer") from error
    if value <= 0:
        raise ConfigurationError(f"{name} must be greater than zero")
    return value


@dataclass(frozen=True, slots=True)
class HttpSettings:
    """Security and resource limits for the private HTTP listener."""

    capability: str
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES
    rate_per_minute: int = DEFAULT_RATE_PER_MINUTE
    rate_burst: int = DEFAULT_RATE_BURST
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY

    @property
    def public_path(self) -> str:
        return f"/{self.capability}/mcp"

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> HttpSettings:
        if environ is None:
            load_dotenv(dotenv_path=Path.cwd() / ".env")
            environ = os.environ
        values = environ
        capability = values.get("MCP_CAPABILITY", "").strip()
        if CAPABILITY_PATTERN.fullmatch(capability) is None:
            raise ConfigurationError("MCP_CAPABILITY must be exactly 64 lowercase hex characters")
        return cls(
            capability=capability,
            max_body_bytes=_positive_int(values, "MCP_HTTP_MAX_BODY_BYTES", DEFAULT_MAX_BODY_BYTES),
            rate_per_minute=_positive_int(
                values, "MCP_HTTP_RATE_PER_MINUTE", DEFAULT_RATE_PER_MINUTE
            ),
            rate_burst=_positive_int(values, "MCP_HTTP_RATE_BURST", DEFAULT_RATE_BURST),
            max_concurrency=_positive_int(
                values, "MCP_HTTP_MAX_CONCURRENCY", DEFAULT_MAX_CONCURRENCY
            ),
        )


class ProtectedMcpApp:
    """Expose exactly one secret MCP path and apply bounded in-memory limits."""

    def __init__(self, app: ASGIApp, settings: HttpSettings) -> None:
        self._app = app
        self._settings = settings
        self._tokens = float(settings.rate_burst)
        self._last_refill = time.monotonic()
        self._active = 0
        self._state_lock = asyncio.Lock()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = str(uuid4())
        started = time.monotonic()
        status = 500
        route = "not_found"
        admitted = False

        async def tracked_send(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message["status"])
            await send(message)

        try:
            path = str(scope.get("path", ""))
            if not secrets.compare_digest(path, self._settings.public_path):
                status = 404
                await self._respond(tracked_send, 404, b"Not found")
                return
            route = "mcp"

            content_length = self._content_length(scope)
            if content_length is not None and content_length > self._settings.max_body_bytes:
                status = 413
                await self._respond(tracked_send, 413, b"Request too large")
                return

            if not await self._admit():
                status = 429
                await self._respond(tracked_send, 429, b"Request limit reached")
                return
            admitted = True

            body = await self._read_body(receive)
            if body is None:
                status = 413
                await self._respond(tracked_send, 413, b"Request too large")
                return

            delivered = False

            async def replay_body() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return {"type": "http.disconnect"}

            inner_scope = dict(scope)
            inner_scope["path"] = "/mcp"
            inner_scope["raw_path"] = b"/mcp"
            inner_scope["headers"] = self._loopback_headers(scope)
            await self._app(inner_scope, replay_body, tracked_send)
        except Exception as error:  # pragma: no cover - defensive transport boundary
            LOGGER.error(
                "request_id=%s route=%s status=500 error=%s",
                request_id,
                route,
                type(error).__name__,
            )
            if status == 500:
                await self._respond(send, 500, b"Internal server error")
        finally:
            if admitted:
                await self._release()
            duration_ms = round((time.monotonic() - started) * 1000)
            LOGGER.info(
                "request_id=%s route=%s status=%d duration_ms=%d",
                request_id,
                route,
                status,
                duration_ms,
            )

    @staticmethod
    def _content_length(scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    @staticmethod
    def _loopback_headers(scope: Scope) -> list[tuple[bytes, bytes]]:
        headers = [
            (name, value) for name, value in scope.get("headers", []) if name.lower() != b"host"
        ]
        headers.append((b"host", b"127.0.0.1:8000"))
        return headers

    async def _read_body(self, receive: Receive) -> bytes | None:
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return b""
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self._settings.max_body_bytes:
                return None
            chunks.append(chunk)
            if not message.get("more_body", False):
                return b"".join(chunks)

    async def _admit(self) -> bool:
        async with self._state_lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            refill_rate = self._settings.rate_per_minute / 60
            self._tokens = min(
                float(self._settings.rate_burst), self._tokens + elapsed * refill_rate
            )
            self._last_refill = now
            if self._tokens < 1 or self._active >= self._settings.max_concurrency:
                return False
            self._tokens -= 1
            self._active += 1
            return True

    async def _release(self) -> None:
        async with self._state_lock:
            self._active -= 1

    @staticmethod
    async def _respond(send: Send, status: int, body: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"text/plain; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": body})


def create_http_app(
    settings: HttpSettings, service: BringShoppingService | None = None
) -> ProtectedMcpApp:
    """Build the private stateless JSON Streamable HTTP application."""
    transport_security = TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["127.0.0.1:*", "localhost:*"],
        allowed_origins=["http://127.0.0.1:*", "http://localhost:*"],
    )
    server = create_server(
        service,
        json_response=True,
        stateless_http=True,
        transport_security=transport_security,
    )
    return ProtectedMcpApp(server.streamable_http_app(), settings)


async def _smoke(settings: HttpSettings) -> None:
    url = f"http://127.0.0.1:8000{settings.public_path}"
    timeout = httpx.Timeout(20, read=30)
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with streamable_http_client(url, http_client=client) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=timedelta(seconds=30),
            ) as session:
                await session.initialize()
                tools = await session.list_tools()
                if len(tools.tools) != 5:
                    raise RuntimeError("MCP tool inventory is incomplete")


def _quiet_smoke_loggers() -> None:
    """Prevent the secret capability URL from appearing in client request logs."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("mcp.client.streamable_http").setLevel(logging.WARNING)


def smoke_main() -> None:
    """Initialize MCP over loopback without printing capability data."""
    _quiet_smoke_loggers()
    anyio.run(_smoke, HttpSettings.from_env())
    print("MCP initialization succeeded; 5 tools are available.")


def main() -> None:
    """Run HTTP on loopback for the colocated Tailscale proxy only."""
    settings = HttpSettings.from_env()
    app = create_http_app(settings)
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        access_log=False,
        log_level="info",
        proxy_headers=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
