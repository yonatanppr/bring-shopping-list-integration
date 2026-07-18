"""Command-line acceptance interface for the Bring integration."""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from bring_api.exceptions import BringException

from bring_shopping.exceptions import BringIntegrationError
from bring_shopping.models import ShoppingItem, ShoppingList
from bring_shopping.service import BringShoppingService, connect_bring
from bring_shopping.settings import BringSettings


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(prog="bring-shopping")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("doctor", help="authenticate and report accessible lists")
    commands.add_parser("lists", help="show accessible shopping lists")

    items = commands.add_parser("items", help="show items waiting to be purchased")
    _add_list_selector(items)

    add = commands.add_parser("add", help="add an item")
    add.add_argument("item")
    add.add_argument("--spec", default="", help="quantity or other item details")
    _add_list_selector(add)

    complete = commands.add_parser("complete", help="mark an item complete")
    complete.add_argument("item")
    complete.add_argument("--spec", default="", help="specification used to disambiguate")
    complete.add_argument("--item-uuid", help="stable item identifier")
    _add_list_selector(complete)

    remove = commands.add_parser("remove", help="permanently remove an item")
    remove.add_argument("item")
    remove.add_argument("--item-uuid", help="stable item identifier")
    _add_list_selector(remove)
    return parser


def _add_list_selector(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--list-uuid", help="override BRING_LIST_UUID for this command")


async def _run(args: argparse.Namespace) -> Any:
    settings = BringSettings.from_env()
    async with connect_bring(settings) as service:
        if args.command in {"doctor", "lists"}:
            lists = await service.list_lists()
            if args.command == "doctor":
                return {"status": "ok", "list_count": len(lists), "lists": lists}
            return lists
        return await _run_list_command(service, args)


async def _run_list_command(service: BringShoppingService, args: argparse.Namespace) -> Any:
    list_uuid: str | None = args.list_uuid
    if args.command == "items":
        shopping_list = await service.resolve_list(list_uuid)
        items = await service.get_items(list_uuid=shopping_list.uuid)
        return {"list": shopping_list, "items": items}
    if args.command == "add":
        shopping_list = await service.add_item(
            args.item,
            specification=args.spec,
            list_uuid=list_uuid,
        )
        return _mutation_result("added", args.item, shopping_list)
    if args.command == "complete":
        shopping_list = await service.complete_item(
            args.item,
            specification=args.spec,
            item_uuid=args.item_uuid,
            list_uuid=list_uuid,
        )
        return _mutation_result("completed", args.item, shopping_list)
    if args.command == "remove":
        shopping_list = await service.remove_item(
            args.item,
            item_uuid=args.item_uuid,
            list_uuid=list_uuid,
        )
        return _mutation_result("removed", args.item, shopping_list)
    raise AssertionError(f"Unhandled command: {args.command}")


def _mutation_result(action: str, item: str, shopping_list: ShoppingList) -> dict[str, Any]:
    return {"status": "ok", "action": action, "item": item.strip(), "list": shopping_list}


def _jsonable(value: Any) -> Any:
    if isinstance(value, (ShoppingItem, ShoppingList)):
        return asdict(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _print_human(value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, ShoppingList):
                print(f"{item.name}\t{item.uuid}")
            else:
                print(item)
        return
    if isinstance(value, dict) and "items" in value:
        shopping_list = value["list"]
        print(f"{shopping_list.name} ({shopping_list.uuid})")
        for item in value["items"]:
            details = f" [{item.specification}]" if item.specification else ""
            print(f"- {item.name}{details}\t{item.uuid}")
        return
    print(json.dumps(_jsonable(value), indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> None:
    """Run the CLI and map expected integration failures to exit status 2."""
    args = build_parser().parse_args(argv)
    try:
        result = asyncio.run(_run(args))
    except (BringIntegrationError, BringException) as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    if args.json:
        print(json.dumps(_jsonable(result), indent=2, sort_keys=True))
    else:
        _print_human(result)


if __name__ == "__main__":
    main()
