"""Opt-in contract test against a dedicated Bring shopping list."""

import asyncio
import os
from contextlib import suppress
from uuid import uuid4

import pytest
from bring_api.exceptions import BringException
from mcp.shared.memory import create_connected_server_and_client_session

from bring_shopping.mcp_server import create_server
from bring_shopping.models import ShoppingItem
from bring_shopping.service import BringShoppingService, connect_bring
from bring_shopping.settings import BringSettings

LIVE_TESTS_ENABLED = os.environ.get("BRING_RUN_LIVE_TESTS") == "1"
TEST_LIST_NAME = "Integration Test"

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not LIVE_TESTS_ENABLED,
        reason="set BRING_RUN_LIVE_TESTS=1 to run live Bring contract tests",
    ),
]


async def _wait_for_item(
    service: BringShoppingService,
    *,
    list_uuid: str,
    name: str,
    present: bool,
) -> ShoppingItem | None:
    for _ in range(10):
        items = await service.get_items(list_uuid=list_uuid)
        match = next((item for item in items if item.name == name), None)
        if (match is not None) is present:
            return match
        await asyncio.sleep(0.5)
    state = "appear in" if present else "leave"
    raise AssertionError(f"Timed out waiting for disposable item to {state} the test list")


async def _exercise_contract() -> None:
    settings = BringSettings.from_env()
    test_list_uuid = os.environ.get("BRING_TEST_LIST_UUID", "").strip()
    if not test_list_uuid:
        pytest.fail("BRING_TEST_LIST_UUID is required for live tests")
    if test_list_uuid == settings.list_uuid:
        pytest.fail("BRING_TEST_LIST_UUID must differ from BRING_LIST_UUID")

    token = uuid4().hex[:12]
    completed_name = f"Contract complete {token}"
    removed_name = f"Contract remove {token}"
    protocol_name = f"Contract protocol {token}"
    completed_uuid = str(uuid4())
    removed_uuid = str(uuid4())
    specification = "safe to delete"
    created: dict[str, str | None] = {
        completed_name: None,
        removed_name: None,
        protocol_name: None,
    }

    async with connect_bring(settings) as service:
        test_list = await service.resolve_list(test_list_uuid)
        if test_list.name != TEST_LIST_NAME:
            pytest.fail(f"Live tests require a list named {TEST_LIST_NAME!r}")

        default_list = await service.resolve_list()
        if default_list.uuid == test_list.uuid:
            pytest.fail("The live test list must not be the configured default list")

        try:
            await service.add_item(
                completed_name,
                specification=specification,
                item_uuid=completed_uuid,
                list_uuid=test_list.uuid,
            )
            completed_item = await _wait_for_item(
                service,
                list_uuid=test_list.uuid,
                name=completed_name,
                present=True,
            )
            assert completed_item is not None
            assert completed_item.specification == specification
            assert completed_item.uuid == completed_uuid
            created[completed_name] = completed_item.uuid

            await service.complete_item(
                completed_name,
                specification=specification,
                item_uuid=completed_item.uuid,
                list_uuid=test_list.uuid,
            )
            await _wait_for_item(
                service,
                list_uuid=test_list.uuid,
                name=completed_name,
                present=False,
            )

            await service.add_item(
                removed_name,
                specification=specification,
                item_uuid=removed_uuid,
                list_uuid=test_list.uuid,
            )
            removed_item = await _wait_for_item(
                service,
                list_uuid=test_list.uuid,
                name=removed_name,
                present=True,
            )
            assert removed_item is not None
            assert removed_item.uuid == removed_uuid
            created[removed_name] = removed_item.uuid

            await service.remove_item(
                removed_name,
                item_uuid=removed_item.uuid,
                list_uuid=test_list.uuid,
            )
            await _wait_for_item(
                service,
                list_uuid=test_list.uuid,
                name=removed_name,
                present=False,
            )

            async with create_connected_server_and_client_session(
                create_server(service)
            ) as session:
                added = await session.call_tool(
                    "bring_add_items",
                    {
                        "items": [
                            {
                                "name": protocol_name,
                                "specification": specification,
                            }
                        ],
                        "list_uuid": test_list.uuid,
                    },
                )
                assert added.isError is False
                assert added.structuredContent is not None
                protocol_uuid = added.structuredContent["items"][0]["item_uuid"]
                assert isinstance(protocol_uuid, str)
                created[protocol_name] = protocol_uuid

                current = await session.call_tool(
                    "bring_get_items",
                    {"list_uuid": test_list.uuid},
                )
                assert current.isError is False
                assert current.structuredContent is not None
                assert any(
                    item["uuid"] == protocol_uuid for item in current.structuredContent["items"]
                )

                completed = await session.call_tool(
                    "bring_complete_items",
                    {
                        "items": [
                            {
                                "name": protocol_name,
                                "specification": specification,
                                "item_uuid": protocol_uuid,
                            }
                        ],
                        "list_uuid": test_list.uuid,
                    },
                )
                assert completed.isError is False

                removed = await session.call_tool(
                    "bring_remove_items",
                    {
                        "items": [
                            {
                                "name": protocol_name,
                                "item_uuid": protocol_uuid,
                            }
                        ],
                        "confirm": True,
                        "list_uuid": test_list.uuid,
                    },
                )
                assert removed.isError is False
        finally:
            for item_name, item_uuid in created.items():
                with suppress(BringException):
                    await service.remove_item(
                        item_name,
                        item_uuid=item_uuid,
                        list_uuid=test_list.uuid,
                    )


def test_bring_add_read_complete_and_remove_contract() -> None:
    asyncio.run(_exercise_contract())
