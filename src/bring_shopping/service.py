"""Typed service boundary around the unofficial Bring API client."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Protocol

import aiohttp
from bring_api import Bring
from bring_api.types import BringItemsResponse, BringListResponse

from bring_shopping.exceptions import InvalidItemError, ItemSelectionError, ListSelectionError
from bring_shopping.models import ShoppingItem, ShoppingList
from bring_shopping.settings import BringSettings


class BringApi(Protocol):
    """Subset of the vendor client used by the application."""

    async def login(self) -> object: ...

    async def load_lists(self) -> BringListResponse: ...

    async def get_list(self, list_uuid: str) -> BringItemsResponse: ...

    async def save_item(
        self,
        list_uuid: str,
        item_name: str,
        specification: str = "",
        item_uuid: str | None = None,
    ) -> None: ...

    async def complete_item(
        self,
        list_uuid: str,
        item_name: str,
        specification: str = "",
        item_uuid: str | None = None,
    ) -> None: ...

    async def remove_item(
        self,
        list_uuid: str,
        item_name: str,
        item_uuid: str | None = None,
    ) -> None: ...


class BringShoppingService:
    """Expose deterministic list and item operations to the CLI and MCP servers."""

    def __init__(
        self,
        api: BringApi,
        *,
        default_list_uuid: str | None = None,
        default_list_name: str | None = None,
    ) -> None:
        self._api = api
        self._default_list_uuid = default_list_uuid
        self._default_list_name = default_list_name

    async def list_lists(self) -> list[ShoppingList]:
        """Return all lists available to the authenticated account."""
        response = await self._api.load_lists()
        return [
            ShoppingList(uuid=item.listUuid, name=item.name, theme=item.theme)
            for item in response.lists
        ]

    async def resolve_list(self, list_uuid: str | None = None) -> ShoppingList:
        """Resolve an explicit or configured list without arbitrary first-list behavior."""
        lists = await self.list_lists()
        requested_uuid = list_uuid or self._default_list_uuid
        if requested_uuid:
            for shopping_list in lists:
                if shopping_list.uuid == requested_uuid:
                    return shopping_list
            raise ListSelectionError(f"No accessible Bring list has UUID {requested_uuid!r}")

        if self._default_list_name:
            requested_name = self._default_list_name.casefold()
            matches = [item for item in lists if item.name.casefold() == requested_name]
            if len(matches) == 1:
                return matches[0]
            if not matches:
                raise ListSelectionError(
                    f"No accessible Bring list is named {self._default_list_name!r}"
                )
            raise ListSelectionError(
                f"More than one Bring list is named {self._default_list_name!r}; use its UUID"
            )

        if len(lists) == 1:
            return lists[0]
        if not lists:
            raise ListSelectionError("The Bring account has no accessible shopping lists")

        choices = ", ".join(f"{item.name} ({item.uuid})" for item in lists)
        raise ListSelectionError(
            "Multiple Bring lists are available. Set BRING_LIST_UUID or pass --list-uuid. "
            f"Choices: {choices}"
        )

    async def get_items(self, *, list_uuid: str | None = None) -> list[ShoppingItem]:
        """Return items currently waiting to be purchased from the selected list."""
        shopping_list = await self.resolve_list(list_uuid)
        return await self._get_purchase_items(shopping_list.uuid)

    async def _get_purchase_items(self, list_uuid: str) -> list[ShoppingItem]:
        response = await self._api.get_list(list_uuid)
        return [
            ShoppingItem(
                uuid=item.uuid,
                name=item.itemId,
                specification=item.specification,
            )
            for item in response.items.purchase
        ]

    async def add_item(
        self,
        name: str,
        *,
        specification: str = "",
        item_uuid: str | None = None,
        list_uuid: str | None = None,
    ) -> ShoppingList:
        """Add an item to the selected list and return that list."""
        clean_name = _require_item_name(name)
        shopping_list = await self.resolve_list(list_uuid)
        await self._api.save_item(
            shopping_list.uuid,
            clean_name,
            specification.strip(),
            item_uuid,
        )
        return shopping_list

    async def complete_item(
        self,
        name: str,
        *,
        specification: str = "",
        item_uuid: str | None = None,
        list_uuid: str | None = None,
    ) -> ShoppingList:
        """Move a matching item to Bring's recently used items."""
        clean_name = _require_item_name(name)
        shopping_list = await self.resolve_list(list_uuid)
        clean_specification = specification.strip()
        if item_uuid is None:
            selected = await self._select_purchase_item(
                shopping_list.uuid,
                clean_name,
                clean_specification,
            )
            clean_name = selected.name
            clean_specification = selected.specification
            item_uuid = selected.uuid
        await self._api.complete_item(
            shopping_list.uuid,
            clean_name,
            clean_specification,
            item_uuid,
        )
        return shopping_list

    async def remove_item(
        self,
        name: str,
        *,
        item_uuid: str | None = None,
        list_uuid: str | None = None,
    ) -> ShoppingList:
        """Permanently remove a matching item from the selected list."""
        clean_name = _require_item_name(name)
        shopping_list = await self.resolve_list(list_uuid)
        if item_uuid is None:
            selected = await self._select_purchase_item(shopping_list.uuid, clean_name)
            clean_name = selected.name
            item_uuid = selected.uuid
        await self._api.remove_item(shopping_list.uuid, clean_name, item_uuid)
        return shopping_list

    async def _select_purchase_item(
        self,
        list_uuid: str,
        name: str,
        specification: str = "",
    ) -> ShoppingItem:
        items = await self._get_purchase_items(list_uuid)
        requested_name = name.casefold()
        matches = [item for item in items if item.name.casefold() == requested_name]
        if specification:
            requested_specification = specification.casefold()
            matches = [
                item for item in matches if item.specification.casefold() == requested_specification
            ]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ItemSelectionError(f"No purchase item matches {name!r} in the selected list")
        raise ItemSelectionError(
            f"More than one purchase item matches {name!r}; provide an item UUID"
        )


def _require_item_name(name: str) -> str:
    clean_name = name.strip()
    if not clean_name:
        raise InvalidItemError("Item name must not be empty")
    return clean_name


@asynccontextmanager
async def connect_bring(settings: BringSettings) -> AsyncIterator[BringShoppingService]:
    """Authenticate once and close the shared HTTP session on exit."""
    timeout = aiohttp.ClientTimeout(total=settings.request_timeout_seconds)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        api = Bring(session, settings.email, settings.password)
        await api.login()
        yield BringShoppingService(
            api,
            default_list_uuid=settings.list_uuid,
            default_list_name=settings.list_name,
        )
