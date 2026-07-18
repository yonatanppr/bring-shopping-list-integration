"""Tests for the capability-protected Streamable HTTP transport."""

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any, TypeVar, cast

import httpx
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from starlette.applications import Starlette
from starlette.types import Message, Scope

from bring_shopping.exceptions import ConfigurationError
from bring_shopping.http_server import (
    HttpSettings,
    ProtectedMcpApp,
    _quiet_smoke_loggers,
    create_http_app,
)
from bring_shopping.service import BringShoppingService
from tests.test_mcp_server import StatefulBringApi

T = TypeVar("T")
CAPABILITY = "a" * 64


def run(coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


def settings(**overrides: Any) -> HttpSettings:
    values: dict[str, Any] = {"capability": CAPABILITY}
    values.update(overrides)
    return HttpSettings(
        capability=values["capability"],
        max_body_bytes=values.get("max_body_bytes", 1_048_576),
        rate_per_minute=values.get("rate_per_minute", 120),
        rate_burst=values.get("rate_burst", 30),
        max_concurrency=values.get("max_concurrency", 4),
    )


def test_http_settings_require_a_256_bit_capability_and_positive_limits() -> None:
    parsed = HttpSettings.from_env(
        {
            "MCP_CAPABILITY": CAPABILITY,
            "MCP_HTTP_MAX_BODY_BYTES": "2048",
            "MCP_HTTP_RATE_PER_MINUTE": "60",
            "MCP_HTTP_RATE_BURST": "5",
            "MCP_HTTP_MAX_CONCURRENCY": "2",
        }
    )
    assert parsed.public_path == f"/{CAPABILITY}/mcp"
    assert parsed.max_body_bytes == 2048

    with pytest.raises(ConfigurationError, match="64 lowercase hex"):
        HttpSettings.from_env({"MCP_CAPABILITY": "secret"})
    with pytest.raises(ConfigurationError, match="must be an integer"):
        HttpSettings.from_env(
            {
                "MCP_CAPABILITY": CAPABILITY,
                "MCP_HTTP_RATE_BURST": "many",
            }
        )
    with pytest.raises(ConfigurationError, match="greater than zero"):
        HttpSettings.from_env(
            {
                "MCP_CAPABILITY": CAPABILITY,
                "MCP_HTTP_MAX_CONCURRENCY": "0",
            }
        )


async def _request(app: Any, path: str, body: bytes = b"", more: bytes = b"") -> list[Message]:
    messages = [
        {"type": "http.request", "body": body, "more_body": bool(more)},
        {"type": "http.request", "body": more, "more_body": False},
    ]
    sent: list[Message] = []

    async def receive() -> Message:
        return messages.pop(0)

    async def send(message: Message) -> None:
        sent.append(message)

    scope: Scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [],
        "client": ("127.0.0.1", 1),
        "server": ("127.0.0.1", 8000),
        "state": {},
    }
    await app(scope, receive, send)
    return sent


def test_unknown_and_oversized_paths_are_rejected_without_reaching_mcp() -> None:
    calls = 0

    async def inner(scope: Scope, receive: Any, send: Any) -> None:
        nonlocal calls
        calls += 1

    app = ProtectedMcpApp(inner, settings(max_body_bytes=3))
    unknown = run(_request(app, "/mcp"))
    oversized = run(_request(app, f"/{CAPABILITY}/mcp", b"ab", b"cd"))

    assert unknown[0]["status"] == 404
    assert oversized[0]["status"] == 413
    assert calls == 0


def test_rate_burst_is_enforced() -> None:
    async def inner(scope: Scope, receive: Any, send: Any) -> None:
        await receive()
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    app = ProtectedMcpApp(inner, settings(rate_burst=1, rate_per_minute=1))
    first = run(_request(app, f"/{CAPABILITY}/mcp"))
    second = run(_request(app, f"/{CAPABILITY}/mcp"))
    assert first[0]["status"] == 204
    assert second[0]["status"] == 429


async def _exercise_mcp_over_http() -> None:
    service = BringShoppingService(StatefulBringApi(), default_list_uuid="list-1")
    app = create_http_app(settings(rate_burst=10), service)
    # The SDK-owned Starlette lifespan must run in this in-memory test.
    inner = cast(Starlette, app._app)
    transport = httpx.ASGITransport(app=app)
    async with inner.router.lifespan_context(inner):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            async with streamable_http_client(
                f"http://test/{CAPABILITY}/mcp", http_client=client
            ) as streams:
                read_stream, write_stream, _ = streams
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    assert len(tools.tools) == 5
                    result = await session.call_tool("bring_get_items", {"limit": 1})
                    assert result.isError is False
                    assert result.structuredContent is not None
                    assert result.structuredContent["items"][0]["name"] == "Milk"


def test_stateless_json_mcp_works_through_the_capability_path() -> None:
    run(_exercise_mcp_over_http())


def test_smoke_client_loggers_do_not_emit_capability_urls() -> None:
    httpx_logger = logging.getLogger("httpx")
    mcp_logger = logging.getLogger("mcp.client.streamable_http")
    prior_levels = (httpx_logger.level, mcp_logger.level)
    try:
        httpx_logger.setLevel(logging.INFO)
        mcp_logger.setLevel(logging.INFO)
        _quiet_smoke_loggers()
        assert httpx_logger.level == logging.WARNING
        assert mcp_logger.level == logging.WARNING
    finally:
        httpx_logger.setLevel(prior_levels[0])
        mcp_logger.setLevel(prior_levels[1])
