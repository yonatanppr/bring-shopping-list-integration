"""Unit tests for list selection and mutation mapping."""

import asyncio
from collections.abc import Coroutine
from typing import Any, TypeVar

import pytest
from bring_api.types import (
    BringItemsResponse,
    BringList,
    BringListResponse,
    BringPurchase,
    Items,
    Status,
)

from bring_shopping.exceptions import InvalidItemError, ItemSelectionError, ListSelectionError
from bring_shopping.service import BringShoppingService

T = TypeVar("T")


def run(coroutine: Coroutine[Any, Any, T]) -> T:
    """Run one service coroutine without an async pytest plugin."""
    return asyncio.run(coroutine)


class FakeBringApi:
    """In-memory implementation of the vendor subset used by the service."""

    def __init__(self, lists: list[BringList]) -> None:
        self.lists = lists
        self.calls: list[tuple[object, ...]] = []
        self.purchase = [BringPurchase(uuid="item-1", itemId="Milk", specification="2 liters")]

    async def login(self) -> object:
        return object()

    async def load_lists(self) -> BringListResponse:
        return BringListResponse(lists=self.lists)

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
        self.calls.append(("save", list_uuid, item_name, specification, item_uuid))

    async def complete_item(
        self,
        list_uuid: str,
        item_name: str,
        specification: str = "",
        item_uuid: str | None = None,
    ) -> None:
        self.calls.append(("complete", list_uuid, item_name, specification, item_uuid))

    async def remove_item(
        self,
        list_uuid: str,
        item_name: str,
        item_uuid: str | None = None,
    ) -> None:
        self.calls.append(("remove", list_uuid, item_name, item_uuid))


def make_list(uuid: str = "list-1", name: str = "Groceries") -> BringList:
    return BringList(listUuid=uuid, name=name, theme="default")


def test_single_list_is_selected_and_purchase_items_are_mapped() -> None:
    api = FakeBringApi([make_list()])
    service = BringShoppingService(api)

    items = run(service.get_items())

    assert items[0].uuid == "item-1"
    assert items[0].name == "Milk"
    assert items[0].specification == "2 liters"
    assert api.calls == [("get", "list-1")]


def test_multiple_lists_require_an_explicit_default() -> None:
    service = BringShoppingService(FakeBringApi([make_list(), make_list("list-2", "Hardware")]))

    with pytest.raises(ListSelectionError, match="Multiple Bring lists"):
        run(service.resolve_list())


def test_configured_list_name_is_case_insensitive() -> None:
    service = BringShoppingService(
        FakeBringApi([make_list(), make_list("list-2", "Hardware")]),
        default_list_name="hardware",
    )

    assert run(service.resolve_list()).uuid == "list-2"


def test_add_normalizes_input_and_targets_configured_uuid() -> None:
    api = FakeBringApi([make_list(), make_list("list-2", "Hardware")])
    service = BringShoppingService(api, default_list_uuid="list-2")

    selected = run(
        service.add_item(
            "  Screws  ",
            specification="  box of 50 ",
            item_uuid="item-2",
        )
    )

    assert selected.uuid == "list-2"
    assert api.calls == [("save", "list-2", "Screws", "box of 50", "item-2")]


def test_complete_and_remove_forward_item_uuid() -> None:
    api = FakeBringApi([make_list()])
    service = BringShoppingService(api)

    run(service.complete_item("Milk", item_uuid="item-1"))
    run(service.remove_item("Milk", item_uuid="item-1"))

    assert api.calls == [
        ("complete", "list-1", "Milk", "", "item-1"),
        ("remove", "list-1", "Milk", "item-1"),
    ]


def test_name_only_complete_resolves_a_unique_purchase_item() -> None:
    api = FakeBringApi([make_list()])
    service = BringShoppingService(api)

    run(service.complete_item("milk"))

    assert api.calls == [
        ("get", "list-1"),
        ("complete", "list-1", "Milk", "2 liters", "item-1"),
    ]


def test_name_only_remove_rejects_duplicate_purchase_items() -> None:
    api = FakeBringApi([make_list()])
    api.purchase.append(BringPurchase(uuid="item-2", itemId="Milk", specification="1 liter"))
    service = BringShoppingService(api)

    with pytest.raises(ItemSelectionError, match="provide an item UUID"):
        run(service.remove_item("Milk"))

    assert api.calls == [("get", "list-1")]


def test_name_only_mutation_rejects_missing_purchase_item() -> None:
    api = FakeBringApi([make_list()])
    service = BringShoppingService(api)

    with pytest.raises(ItemSelectionError, match="No purchase item"):
        run(service.complete_item("Bread"))

    assert api.calls == [("get", "list-1")]


def test_empty_item_name_is_rejected_before_list_lookup() -> None:
    api = FakeBringApi([make_list()])
    service = BringShoppingService(api)

    with pytest.raises(InvalidItemError, match="must not be empty"):
        run(service.add_item("  "))

    assert api.calls == []
