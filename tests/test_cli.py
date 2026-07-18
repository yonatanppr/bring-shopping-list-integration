"""Acceptance tests for CLI parsing, dispatch, output, and error exits."""

import argparse
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

import pytest

from bring_shopping import cli
from bring_shopping.exceptions import InvalidItemError
from bring_shopping.models import ShoppingItem, ShoppingList
from bring_shopping.service import BringShoppingService
from bring_shopping.settings import BringSettings


class RecordingService:
    """CLI-facing service with deterministic responses and call recording."""

    def __init__(self) -> None:
        self.shopping_list = ShoppingList(uuid="list-1", name="Groceries", theme="default")
        self.items = [ShoppingItem(uuid="item-1", name="Milk", specification="2 liters")]
        self.calls: list[tuple[object, ...]] = []

    async def list_lists(self) -> list[ShoppingList]:
        self.calls.append(("lists",))
        return [self.shopping_list]

    async def resolve_list(self, list_uuid: str | None = None) -> ShoppingList:
        self.calls.append(("resolve", list_uuid))
        return self.shopping_list

    async def get_items(self, *, list_uuid: str | None = None) -> list[ShoppingItem]:
        self.calls.append(("items", list_uuid))
        return self.items

    async def add_item(
        self,
        name: str,
        *,
        specification: str = "",
        item_uuid: str | None = None,
        list_uuid: str | None = None,
    ) -> ShoppingList:
        self.calls.append(("add", name, specification, item_uuid, list_uuid))
        return self.shopping_list

    async def complete_item(
        self,
        name: str,
        *,
        specification: str = "",
        item_uuid: str | None = None,
        list_uuid: str | None = None,
    ) -> ShoppingList:
        self.calls.append(("complete", name, specification, item_uuid, list_uuid))
        return self.shopping_list

    async def remove_item(
        self,
        name: str,
        *,
        item_uuid: str | None = None,
        list_uuid: str | None = None,
    ) -> ShoppingList:
        self.calls.append(("remove", name, item_uuid, list_uuid))
        return self.shopping_list


def as_service(service: RecordingService) -> BringShoppingService:
    return cast(BringShoppingService, service)


def test_parser_accepts_global_json_and_list_selector() -> None:
    args = cli.build_parser().parse_args(
        ["--json", "add", "Milk", "--spec", "2 liters", "--list-uuid", "list-1"]
    )

    assert args.json is True
    assert args.command == "add"
    assert args.item == "Milk"
    assert args.spec == "2 liters"
    assert args.list_uuid == "list-1"


def test_list_command_dispatches_every_operation() -> None:
    service = RecordingService()

    items = asyncio.run(
        cli._run_list_command(
            as_service(service),
            argparse.Namespace(command="items", list_uuid="list-1"),
        )
    )
    added = asyncio.run(
        cli._run_list_command(
            as_service(service),
            argparse.Namespace(
                command="add",
                item="Bread",
                spec="one loaf",
                list_uuid="list-1",
            ),
        )
    )
    completed = asyncio.run(
        cli._run_list_command(
            as_service(service),
            argparse.Namespace(
                command="complete",
                item="Milk",
                spec="2 liters",
                item_uuid="item-1",
                list_uuid="list-1",
            ),
        )
    )
    removed = asyncio.run(
        cli._run_list_command(
            as_service(service),
            argparse.Namespace(
                command="remove",
                item="Milk",
                item_uuid="item-1",
                list_uuid="list-1",
            ),
        )
    )

    assert items == {"list": service.shopping_list, "items": service.items}
    assert added["action"] == "added"
    assert completed["action"] == "completed"
    assert removed["action"] == "removed"
    assert ("add", "Bread", "one loaf", None, "list-1") in service.calls
    assert ("complete", "Milk", "2 liters", "item-1", "list-1") in service.calls
    assert ("remove", "Milk", "item-1", "list-1") in service.calls


def test_list_command_rejects_unknown_dispatch() -> None:
    with pytest.raises(AssertionError, match="Unhandled command"):
        asyncio.run(
            cli._run_list_command(
                as_service(RecordingService()),
                argparse.Namespace(command="unknown", list_uuid=None),
            )
        )


def test_run_handles_doctor_lists_and_list_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    service = RecordingService()

    @asynccontextmanager
    async def fake_connect(_: object) -> AsyncIterator[BringShoppingService]:
        yield as_service(service)

    monkeypatch.setattr(BringSettings, "from_env", lambda: object())
    monkeypatch.setattr(cli, "connect_bring", fake_connect)

    doctor = asyncio.run(cli._run(argparse.Namespace(command="doctor")))
    lists = asyncio.run(cli._run(argparse.Namespace(command="lists")))
    added = asyncio.run(
        cli._run(
            argparse.Namespace(
                command="add",
                item="Bread",
                spec="",
                list_uuid=None,
            )
        )
    )

    assert doctor["status"] == "ok"
    assert doctor["list_count"] == 1
    assert lists == [service.shopping_list]
    assert added["action"] == "added"


def test_main_emits_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fake_run(_: argparse.Namespace) -> list[ShoppingList]:
        return [ShoppingList(uuid="list-1", name="Groceries", theme="default")]

    monkeypatch.setattr(cli, "_run", fake_run)

    cli.main(["--json", "lists"])

    assert '"name": "Groceries"' in capsys.readouterr().out


def test_main_maps_expected_errors_to_exit_two(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    async def fail(_: argparse.Namespace) -> None:
        raise InvalidItemError("invalid item")

    monkeypatch.setattr(cli, "_run", fail)

    with pytest.raises(SystemExit) as exit_info:
        cli.main(["lists"])

    assert exit_info.value.code == 2
    assert capsys.readouterr().err == "error: invalid item\n"


def test_human_output_formats_lists_items_and_fallback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    shopping_list = ShoppingList(uuid="list-1", name="Groceries", theme="default")
    item = ShoppingItem(uuid="item-1", name="Milk", specification="2 liters")

    cli._print_human([shopping_list])
    cli._print_human({"list": shopping_list, "items": [item]})
    cli._print_human({"status": "ok"})

    output = capsys.readouterr().out
    assert "Groceries\tlist-1" in output
    assert "Milk [2 liters]\titem-1" in output
    assert '"status": "ok"' in output
