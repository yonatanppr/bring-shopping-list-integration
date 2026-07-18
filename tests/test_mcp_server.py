"""Protocol-level tests for the local MCP server."""

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

from bring_api.types import (
    BringItemsResponse,
    BringList,
    BringListResponse,
    BringPurchase,
    Items,
    Status,
)
from mcp.shared.memory import create_connected_server_and_client_session

from bring_shopping.mcp_server import create_server
from bring_shopping.service import BringShoppingService

T = TypeVar("T")


def run(coroutine: Coroutine[Any, Any, T]) -> T:
    return asyncio.run(coroutine)


class StatefulBringApi:
    """Small stateful Bring implementation used through the full MCP protocol."""

    def __init__(self) -> None:
        self.shopping_list = BringList(listUuid="list-1", name="Groceries", theme="default")
        self.purchase = [BringPurchase(uuid="item-1", itemId="Milk", specification="2 liters")]
        self.calls: list[tuple[object, ...]] = []

    async def login(self) -> object:
        return object()

    async def load_lists(self) -> BringListResponse:
        return BringListResponse(lists=[self.shopping_list])

    async def get_list(self, list_uuid: str) -> BringItemsResponse:
        self.calls.append(("get", list_uuid))
        return BringItemsResponse(
            uuid=list_uuid,
            status=Status.REGISTERED,
            items=Items(purchase=self.purchase, recently=[]),
        )

    async def save_item(
        self,
        list_uuid: str,
        item_name: str,
        specification: str = "",
        item_uuid: str | None = None,
    ) -> None:
        assert item_uuid is not None
        self.calls.append(("save", list_uuid, item_name, specification, item_uuid))
        self.purchase.append(
            BringPurchase(uuid=item_uuid, itemId=item_name, specification=specification)
        )

    async def complete_item(
        self,
        list_uuid: str,
        item_name: str,
        specification: str = "",
        item_uuid: str | None = None,
    ) -> None:
        self.calls.append(("complete", list_uuid, item_name, specification, item_uuid))
        self.purchase = [item for item in self.purchase if item.uuid != item_uuid]

    async def remove_item(
        self,
        list_uuid: str,
        item_name: str,
        item_uuid: str | None = None,
    ) -> None:
        self.calls.append(("remove", list_uuid, item_name, item_uuid))
        self.purchase = [item for item in self.purchase if item.uuid != item_uuid]


def make_server(api: StatefulBringApi) -> Any:
    service = BringShoppingService(api, default_list_uuid="list-1")
    return create_server(service)


async def _inspect_and_read(api: StatefulBringApi) -> None:
    async with create_connected_server_and_client_session(make_server(api)) as session:
        tools = await session.list_tools()
        assert {tool.name for tool in tools.tools} == {
            "bring_add_items",
            "bring_complete_items",
            "bring_get_items",
            "bring_list_lists",
            "bring_remove_items",
        }
        remove_tool = next(tool for tool in tools.tools if tool.name == "bring_remove_items")
        assert remove_tool.annotations is not None
        assert remove_tool.annotations.destructiveHint is True

        result = await session.call_tool("bring_get_items", {"limit": 1})
        assert result.isError is False
        assert result.structuredContent is not None
        assert result.structuredContent["shopping_list"]["name"] == "Groceries"
        assert result.structuredContent["items"][0]["name"] == "Milk"
        assert result.structuredContent["total_count"] == 1
        assert result.structuredContent["truncated"] is False


def test_server_exposes_expected_tools_and_structured_read_results() -> None:
    run(_inspect_and_read(StatefulBringApi()))


async def _add_and_remove(api: StatefulBringApi) -> None:
    async with create_connected_server_and_client_session(make_server(api)) as session:
        added = await session.call_tool(
            "bring_add_items",
            {"items": [{"name": "Bread", "specification": "one loaf"}]},
        )
        assert added.isError is False
        assert added.structuredContent is not None
        receipt = added.structuredContent
        assert receipt["action"] == "added"
        assert isinstance(receipt["request_id"], str)
        assert receipt["items"][0]["name"] == "Bread"
        item_uuid = receipt["items"][0]["item_uuid"]
        assert isinstance(item_uuid, str)

        refused = await session.call_tool(
            "bring_remove_items",
            {
                "items": [{"name": "Bread", "item_uuid": item_uuid}],
                "confirm": False,
            },
        )
        assert refused.isError is True
        assert not any(call[0] == "remove" for call in api.calls)

        removed = await session.call_tool(
            "bring_remove_items",
            {
                "items": [{"name": "Bread", "item_uuid": item_uuid}],
                "confirm": True,
            },
        )
        assert removed.isError is False
        assert removed.structuredContent is not None
        assert removed.structuredContent["action"] == "removed"
        assert any(call[0] == "remove" for call in api.calls)


def test_add_returns_uuid_and_remove_requires_confirmation() -> None:
    run(_add_and_remove(StatefulBringApi()))


async def _complete_by_unique_name(api: StatefulBringApi) -> None:
    async with create_connected_server_and_client_session(make_server(api)) as session:
        result = await session.call_tool(
            "bring_complete_items",
            {"items": [{"name": "milk"}]},
        )
        assert result.isError is False
        assert any(
            call == ("complete", "list-1", "Milk", "2 liters", "item-1") for call in api.calls
        )


def test_complete_resolves_a_unique_name_before_mutating() -> None:
    run(_complete_by_unique_name(StatefulBringApi()))
